"""F1a — Pricelist per-entitas (harga jual per-PT) dengan histori & tanggal efektif.

Model SILO multi-entity (F0): tiap entitas (PT/CV) boleh menetapkan harga jual
sendiri per produk. Bila entitas BELUM punya harga aktif untuk produk → fallback
ke harga global `products.price` (keputusan owner F1a-2a).

Koleksi: `entity_prices` (prefix `epr_`) — SCOPED via entity_id.
  {id, entity_id, product_id, sku, product_name, sell_price (per base unit),
   currency, valid_from (iso), valid_until (iso|""), is_listed, status (active|inactive),
   note, created_by, created_at, updated_at}

Resolusi (`resolve_sell_price`): di antara record aktif (status active, is_listed,
valid_from <= as_of, valid_until kosong / >= as_of) → ambil valid_from TERBESAR.
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso, safe_doc

PREFIX = "epr"


def _norm_dt(value: Optional[str], end_of_day: bool = False) -> str:
    """Normalisasi tanggal: 'YYYY-MM-DD' → awal/akhir hari UTC. Kosong → ''."""
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) == 10 and v.count("-") == 2:
        return f"{v}T23:59:59+00:00" if end_of_day else f"{v}T00:00:00+00:00"
    return v


def effective_status(r: Dict[str, Any], now: Optional[str] = None) -> str:
    now = now or now_iso()
    if r.get("status") == "inactive":
        return "inactive"
    vf = r.get("valid_from") or ""
    vu = r.get("valid_until") or ""
    if vf and vf > now:
        return "scheduled"
    if vu and vu < now:
        return "expired"
    return "current"


def decorate(r: Dict[str, Any]) -> Dict[str, Any]:
    if not r:
        return r
    st = effective_status(r)
    r["effective_status"] = st
    r["is_current"] = st == "current"
    return r


def _active_candidates(records: List[Dict[str, Any]], as_of: str) -> List[Dict[str, Any]]:
    out = []
    for r in records:
        if r.get("status") == "inactive" or not r.get("is_listed", True):
            continue
        vf = r.get("valid_from") or ""
        vu = r.get("valid_until") or ""
        if vf and vf > as_of:
            continue
        if vu and vu < as_of:
            continue
        out.append(r)
    return out


async def resolve_sell_price(entity_id: Optional[str], product_id: str,
                             product: Optional[Dict[str, Any]] = None,
                             as_of: Optional[str] = None) -> Dict[str, Any]:
    """Harga jual efektif (per base unit) untuk (entity, product). Fallback global."""
    as_of = as_of or now_iso()
    fallback = float((product or {}).get("price", 0) or 0)
    if not entity_id or entity_id == "all":
        return {"price": fallback, "source": "global", "record_id": None}
    recs = await db.entity_prices.find(
        {"entity_id": entity_id, "product_id": product_id, "status": "active"}, {"_id": 0}).to_list(300)
    cand = _active_candidates(recs, as_of)
    if not cand:
        return {"price": fallback, "source": "global", "record_id": None}
    best = max(cand, key=lambda r: r.get("valid_from") or "")
    return {"price": round(float(best["sell_price"]), 2), "source": "entity",
            "record_id": best["id"], "valid_until": best.get("valid_until", "")}


async def resolve_many(entity_id: Optional[str], product_ids: List[str],
                       products_map: Optional[Dict[str, Any]] = None,
                       as_of: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Batch resolve harga jual efektif untuk banyak produk (1 query)."""
    as_of = as_of or now_iso()
    products_map = products_map or {}
    ids = list(dict.fromkeys(product_ids))
    base = {pid: float((products_map.get(pid) or {}).get("price", 0) or 0) for pid in ids}
    if not entity_id or entity_id == "all":
        return {pid: {"price": base.get(pid, 0.0), "source": "global", "record_id": None} for pid in ids}
    recs = await db.entity_prices.find(
        {"entity_id": entity_id, "product_id": {"$in": ids}, "status": "active"}, {"_id": 0}).to_list(10000)
    by_pid: Dict[str, List[Dict[str, Any]]] = {}
    for r in _active_candidates(recs, as_of):
        by_pid.setdefault(r["product_id"], []).append(r)
    out: Dict[str, Dict[str, Any]] = {}
    for pid in ids:
        cand = by_pid.get(pid)
        if cand:
            best = max(cand, key=lambda r: r.get("valid_from") or "")
            out[pid] = {"price": round(float(best["sell_price"]), 2), "source": "entity", "record_id": best["id"]}
        else:
            out[pid] = {"price": base.get(pid, 0.0), "source": "global", "record_id": None}
    return out


async def create_price(data: Dict[str, Any], entity_id: str, actor_name: str) -> Dict[str, Any]:
    product = await db.products.find_one({"id": data.get("product_id")}, {"_id": 0})
    if not product:
        raise ValueError("Produk tidak ditemukan")
    price = round(float(data.get("sell_price") or 0), 2)
    if price <= 0:
        raise ValueError("Harga jual harus lebih dari 0")
    eid = (data.get("entity_id") or "").strip() or entity_id
    vfrom = _norm_dt(data.get("valid_from")) or now_iso()
    vuntil = _norm_dt(data.get("valid_until"), end_of_day=True)
    if vuntil and vuntil < vfrom:
        raise ValueError("Tanggal berakhir tidak boleh sebelum tanggal mulai")
    # Auto-close record open-ended yang masih berlaku agar timeline tidak overlap.
    existing = await db.entity_prices.find(
        {"entity_id": eid, "product_id": product["id"], "status": "active"}, {"_id": 0}).to_list(300)
    for r in existing:
        rf = r.get("valid_from") or ""
        ru = r.get("valid_until") or ""
        if rf < vfrom and (ru == "" or ru >= vfrom):
            await db.entity_prices.update_one(
                {"id": r["id"]}, {"$set": {"valid_until": vfrom, "updated_at": now_iso()}})
    doc = {
        "id": new_id(PREFIX), "entity_id": eid, "product_id": product["id"],
        "sku": product.get("sku", ""), "product_name": product.get("name", ""),
        "sell_price": price, "currency": "IDR",
        "valid_from": vfrom, "valid_until": vuntil,
        "is_listed": bool(data.get("is_listed", True)), "status": "active",
        "note": (data.get("note") or "").strip(),
        "created_by": actor_name, "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.entity_prices.insert_one(doc)
    return decorate(safe_doc(doc))


async def patch_price(price_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    rec = await db.entity_prices.find_one({"id": price_id}, {"_id": 0})
    if not rec:
        raise ValueError("Harga tidak ditemukan")
    upd: Dict[str, Any] = {}
    if data.get("sell_price") is not None:
        p = round(float(data["sell_price"]), 2)
        if p <= 0:
            raise ValueError("Harga jual harus lebih dari 0")
        upd["sell_price"] = p
    if data.get("valid_until") is not None:
        upd["valid_until"] = _norm_dt(str(data["valid_until"]), end_of_day=True)
    if data.get("is_listed") is not None:
        upd["is_listed"] = bool(data["is_listed"])
    if data.get("note") is not None:
        upd["note"] = (str(data["note"]) or "").strip()
    if not upd:
        raise ValueError("Tidak ada perubahan valid untuk disimpan")
    upd["updated_at"] = now_iso()
    await db.entity_prices.update_one({"id": price_id}, {"$set": upd})
    return decorate(safe_doc(await db.entity_prices.find_one({"id": price_id}, {"_id": 0})))


async def deactivate_price(price_id: str) -> Dict[str, Any]:
    rec = await db.entity_prices.find_one({"id": price_id}, {"_id": 0})
    if not rec:
        raise ValueError("Harga tidak ditemukan")
    await db.entity_prices.update_one(
        {"id": price_id}, {"$set": {"status": "inactive", "updated_at": now_iso()}})
    return {"deactivated": True, "id": price_id}


async def get_record(price_id: str) -> Optional[Dict[str, Any]]:
    return safe_doc(await db.entity_prices.find_one({"id": price_id}, {"_id": 0}))


async def list_records(scope: Dict[str, Any], product_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q = dict(scope or {})
    if product_id:
        q["product_id"] = product_id
    rows = await db.entity_prices.find(q, {"_id": 0}).sort(
        [("product_id", 1), ("valid_from", -1)]).to_list(5000)
    return [decorate(safe_doc(r)) for r in rows]


async def pricelist_grid(entity_id: str, search: str = "") -> List[Dict[str, Any]]:
    """Satu baris per produk: harga global + harga entitas current (bila ada)."""
    products = await db.products.find({"status": {"$ne": "inactive"}}, {"_id": 0}).to_list(1000)
    if search:
        s = search.lower()
        products = [p for p in products
                    if s in f"{p.get('name','')}{p.get('sku','')}{p.get('category','')}".lower()]
    pids = [p["id"] for p in products]
    pmap = {p["id"]: p for p in products}
    resolved = await resolve_many(entity_id, pids, pmap)
    rows = []
    for p in products:
        r = resolved.get(p["id"], {})
        glob = float(p.get("price", 0) or 0)
        rows.append({
            "product_id": p["id"], "sku": p.get("sku", ""), "product_name": p.get("name", ""),
            "category": p.get("category", ""), "base_unit": p.get("base_unit", "meter"),
            "global_price": glob,
            "effective_price": r.get("price", glob),
            "price_source": r.get("source", "global"),
            "has_entity_price": r.get("source") == "entity",
        })
    rows.sort(key=lambda x: (x["category"], x["product_name"]))
    return rows
