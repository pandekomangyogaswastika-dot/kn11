"""Roll service (Fase 0.5) — Roll-as-SSOT inventory engine.

Implementasi fondasi KN_15:
- `inventory_rolls` = SSOT fisik (1 dokumen = 1 roll). Prefix `roll_`.
- `inventory_balances` = PROYEKSI yang di-rebuild dari rolls (key 3-bagian:
  product_id + warehouse_id + owner_entity_id), bucket DETAIL (KN_15 §3.4).
- Reservasi terjadi di LEVEL ROLL (atomic find_one_and_update available→reserved),
  owner-scoped (roll hanya boleh dijual entitas pemiliknya).

Catatan: alokasi penuh (configurable policy + mixed-lot confirmation UI +
inter-company transfer) adalah Fase 1. Di sini fondasi: owner-scoped + FEFO +
single-warehouse preference + split roll saat reservasi parsial.
"""
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from pymongo import ReturnDocument
from db import db
from core_utils import now_iso, new_id, DEFAULT_ENTITY_ID
from schemas import WAREHOUSE_PRIORITY

# ── Taksonomi status (KN_15 §3.4) ────────────────────────────────────────────
# Bucket FISIK di gudang (menyusun on_hand)
PHYSICAL_STATUS_TO_BUCKET = {
    "available": "available_qty",
    "reserved": "reserved_qty",
    "committed": "committed_qty",
    "picked": "picked_qty",
    "packed": "packed_qty",
    "hold": "hold_qty",            # F2 — soft hold / pending SO (fisik di gudang, tak tersedia)
    "wip": "wip_qty",             # F2 — work-in-progress (sedang diproses/produksi)
    "quarantine": "quarantine_qty",
    "blocked": "blocked_qty",
    "damaged": "damaged_qty",
}
# Bucket TRANSIT/PIPELINE (di luar gudang fisik)
TRANSIT_STATUS_TO_BUCKET = {
    "in_transit_inbound": "in_transit_inbound_qty",
    "in_transit_transfer": "in_transit_transfer_qty",
    "in_transit_intercompany": "in_transit_intercompany_qty",
    "in_transit_sales": "in_transit_sales_qty",
}
ALL_BUCKETS = list(PHYSICAL_STATUS_TO_BUCKET.values()) + list(TRANSIT_STATUS_TO_BUCKET.values())
# Status roll yang menahan reservasi sebuah order (untuk release)
ORDER_HELD_STATUSES = ["reserved", "committed", "picked", "packed", "in_transit_sales"]

MAX_AVAILABLE_ROLL_LEN = 150.0  # potong sintetis available jadi roll realistis


# ── Rebuild proyeksi balance dari rolls ──────────────────────────────────────

async def rebuild_balance(product_id: str, warehouse_id: str, owner_entity_id: str) -> Dict[str, Any]:
    """Hitung ulang satu segmen balance (product × warehouse × owner) dari rolls."""
    rolls = await db.inventory_rolls.find(
        {"product_id": product_id, "warehouse_id": warehouse_id, "owner_entity_id": owner_entity_id},
        {"_id": 0},
    ).to_list(10000)
    buckets = {b: 0.0 for b in ALL_BUCKETS}
    roll_counts = {b: 0 for b in ALL_BUCKETS}  # F2 (UoM SSOT) — jumlah roll per bucket
    for r in rolls:
        status = r.get("status")
        length = float(r.get("length_remaining", 0) or 0)
        bucket = PHYSICAL_STATUS_TO_BUCKET.get(status) or TRANSIT_STATUS_TO_BUCKET.get(status)
        if bucket:
            buckets[bucket] += length
            if length > 0:
                roll_counts[bucket] += 1
    physical = sum(buckets[b] for b in PHYSICAL_STATUS_TO_BUCKET.values())
    on_order = await _on_order_qty(product_id, warehouse_id, owner_entity_id)
    in_transit_total = sum(buckets[b] for b in TRANSIT_STATUS_TO_BUCKET.values())
    owned = physical + in_transit_total
    incoming = on_order + buckets["in_transit_inbound_qty"]
    atp = buckets["available_qty"] + incoming  # horizon penuh; reserved sudah keluar dari available
    # F2 (UoM SSOT) — jumlah roll fisik di gudang & roll yang tersedia dijual
    on_hand_roll_count = sum(roll_counts[b] for b in PHYSICAL_STATUS_TO_BUCKET.values())
    doc = {
        "product_id": product_id, "warehouse_id": warehouse_id, "owner_entity_id": owner_entity_id,
        **buckets,
        "on_hand_qty": round(physical, 2),
        "in_transit_qty": round(in_transit_total, 2),  # legacy alias (total transit)
        "on_order_qty": round(on_order, 2),
        "owned_qty": round(owned, 2),
        "incoming_qty": round(incoming, 2),
        "atp_qty": round(atp, 2),
        "roll_count": roll_counts["available_qty"],   # F2 — jumlah roll TERSEDIA (siap dijual)
        "on_hand_roll_count": on_hand_roll_count,       # F2 — jumlah roll fisik di gudang
        "roll_counts": roll_counts,                     # F2 — detail count per-bucket
        "updated_at": now_iso(),
    }
    # round bucket
    for b in ALL_BUCKETS:
        doc[b] = round(doc[b], 2)
    existing = await db.inventory_balances.find_one(
        {"product_id": product_id, "warehouse_id": warehouse_id, "owner_entity_id": owner_entity_id},
        {"_id": 0, "id": 1},
    )
    if existing:
        await db.inventory_balances.update_one(
            {"product_id": product_id, "warehouse_id": warehouse_id, "owner_entity_id": owner_entity_id},
            {"$set": doc},
        )
    else:
        doc["id"] = new_id("bal")
        await db.inventory_balances.insert_one(dict(doc))
    return doc


async def _on_order_qty(product_id: str, warehouse_id: str, owner_entity_id: str) -> float:
    """Qty pipeline dari purchase_orders yang belum jadi roll (status belum receiving selesai)."""
    pos = await db.purchase_orders.find(
        {"warehouse_id": warehouse_id, "status": {"$in": ["pending", "created", "approved", "sent"]}},
        {"_id": 0, "items": 1, "entity_id": 1},
    ).to_list(500)
    total = 0.0
    for po in pos:
        if po.get("entity_id") and po.get("entity_id") != owner_entity_id:
            continue
        for it in po.get("items", []):
            if it.get("product_id") == product_id:
                total += float(it.get("quantity", it.get("qty", 0)) or 0)
    return total


async def rebuild_all_balances() -> int:
    """Drop semua balances lalu rebuild dari rolls (segmen unik)."""
    segments = await db.inventory_rolls.aggregate([
        {"$group": {"_id": {"p": "$product_id", "w": "$warehouse_id", "o": "$owner_entity_id"}}}
    ]).to_list(100000)
    await db.inventory_balances.delete_many({})
    for s in segments:
        k = s["_id"]
        await rebuild_balance(k["p"], k["w"], k["o"])
    return len(segments)


async def backfill_roll_counts() -> int:
    """F2 (UoM SSOT) — set `roll_count`/`on_hand_roll_count` pada balance yang ada,
    DIHITUNG dari rolls TANPA menyentuh qty bucket (additive + idempotent).
    Aman dipanggil di seed maupun sebagai migrasi terpisah."""
    balances = await db.inventory_balances.find(
        {}, {"_id": 0, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1}
    ).to_list(100000)
    updated = 0
    for b in balances:
        q = {"product_id": b["product_id"], "warehouse_id": b["warehouse_id"],
             "owner_entity_id": b["owner_entity_id"]}
        rolls = await db.inventory_rolls.find(
            q, {"_id": 0, "status": 1, "length_remaining": 1}
        ).to_list(10000)
        roll_counts = {bk: 0 for bk in ALL_BUCKETS}
        for r in rolls:
            length = float(r.get("length_remaining", 0) or 0)
            bucket = PHYSICAL_STATUS_TO_BUCKET.get(r.get("status")) or TRANSIT_STATUS_TO_BUCKET.get(r.get("status"))
            if bucket and length > 0:
                roll_counts[bucket] += 1
        on_hand_roll_count = sum(roll_counts[bk] for bk in PHYSICAL_STATUS_TO_BUCKET.values())
        await db.inventory_balances.update_one(q, {"$set": {
            "roll_count": roll_counts["available_qty"],
            "on_hand_roll_count": on_hand_roll_count,
            "roll_counts": roll_counts,
        }})
        updated += 1
    return updated


# ── Synthetic migration: balances lama → rolls (idempotent) ──────────────────

async def _lot_for_segment(product_id: str, warehouse_id: str) -> str:
    mv = await db.inventory_movements.find_one(
        {"product_id": product_id, "warehouse_id": warehouse_id, "lot": {"$nin": [None, ""]}},
        {"_id": 0, "lot": 1}, sort=[("timestamp", 1)],
    )
    return (mv or {}).get("lot") or "LOT-MIGRATED"


async def generate_rolls_from_balances(created_by: str = "seed") -> Dict[str, int]:
    """Generate inventory_rolls sintetis dari balances lama (KN_15 §11).

    Idempotent: skip bila inventory_rolls sudah berisi. Backfill owner_entity_id
    pada balances & movements, lalu rolls dibuat per bucket, balances di-rebuild.
    """
    if await db.inventory_rolls.count_documents({}) > 0:
        return {"rolls": 0, "skipped": 1}

    # 1) Backfill owner_entity_id pada movements lama (default entitas utama)
    await db.inventory_movements.update_many(
        {"owner_entity_id": {"$exists": False}}, {"$set": {"owner_entity_id": DEFAULT_ENTITY_ID}}
    )

    # 2) Map alokasi SO aktif per (product, warehouse) → list (order_id, qty)
    active_orders = await db.sales_orders.find(
        {"status": {"$in": ["reserved", "waiting_approval", "approved", "confirmed"]}},
        {"_id": 0, "id": 1, "entity_id": 1, "allocations": 1},
    ).to_list(2000)
    alloc_map: Dict[tuple, List[Dict[str, Any]]] = {}
    for o in active_orders:
        for a in o.get("allocations", []):
            key = (a.get("product_id"), a.get("warehouse_id"))
            alloc_map.setdefault(key, []).append({
                "order_id": o["id"],
                "owner": o.get("entity_id") or DEFAULT_ENTITY_ID,
                "qty": float(a.get("quantity", a.get("qty", 0)) or 0),
            })

    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    balances = await db.inventory_balances.find({}, {"_id": 0}).to_list(10000)
    roll_docs: List[Dict[str, Any]] = []
    seq = {"n": 0}

    def _make_roll(product_id, warehouse_id, owner, lot, length, status, reserved_ref=None, grade="A"):
        seq["n"] += 1
        prod = products.get(product_id, {})
        return {
            "id": new_id("roll"),
            "product_id": product_id,
            "owner_entity_id": owner,
            "ownership_type": "internal",
            "consignor_ref": None,
            "warehouse_id": warehouse_id,
            "bin_id": None,
            "lot": lot,
            "dye_lot": lot,
            "batch": lot.replace("LOT", "BATCH") if lot else "",
            "roll_no": f"RL-{seq['n']:05d}",
            "length_initial": round(float(length), 2),
            "length_remaining": round(float(length), 2),
            "unit": prod.get("base_unit", "meter"),
            "grade": prod.get("grade", grade),
            "status": status,
            "tracking_mode": "barcode",
            "earmarked_for": None,
            "secondary_measures": None,
            "location_type": "warehouse_bin",
            "reserved_ref": reserved_ref,
            "base_unit_cost": round(float(prod.get("harga_pokok") or 0), 4),
            "unit_cost": (round(float(prod.get("harga_pokok") or 0), 4) or None),
            "landed_cost_total": 0.0,
            "acquired": {"via": "initial", "ref_id": "seed", "date": now_iso()},
            "rfid_tag_id": None,
            "is_remnant": False,
            "created_at": now_iso(), "updated_at": now_iso(),
            "created_by": created_by, "created_by_name": "System Seed",
        }

    for b in balances:
        product_id = b.get("product_id")
        warehouse_id = b.get("warehouse_id")
        owner = b.get("owner_entity_id") or DEFAULT_ENTITY_ID
        lot = await _lot_for_segment(product_id, warehouse_id)
        reserved_qty = float(b.get("reserved_qty", 0) or 0)
        available_qty = float(b.get("available_qty", 0) or 0)
        blocked_qty = float(b.get("blocked_qty", 0) or 0)
        picked_qty = float(b.get("picked_qty", 0) or 0)

        # Reserved rolls — distribusi ke SO aktif (link reserved_ref) lalu sisa generik
        remaining_reserved = reserved_qty
        for alloc in alloc_map.get((product_id, warehouse_id), []):
            if remaining_reserved <= 0.01:
                break
            take = min(alloc["qty"], remaining_reserved)
            if take <= 0.01:
                continue
            roll_docs.append(_make_roll(
                product_id, warehouse_id, owner, lot, take, "reserved",
                reserved_ref={"type": "sales_order", "id": alloc["order_id"]},
            ))
            remaining_reserved -= take
        if remaining_reserved > 0.01:
            roll_docs.append(_make_roll(
                product_id, warehouse_id, owner, lot, remaining_reserved, "reserved",
                reserved_ref={"type": "seed", "id": "seed"},
            ))

        # Blocked / picked rolls (jika ada di seed)
        if blocked_qty > 0.01:
            roll_docs.append(_make_roll(product_id, warehouse_id, owner, lot, blocked_qty, "blocked"))
        if picked_qty > 0.01:
            roll_docs.append(_make_roll(product_id, warehouse_id, owner, lot, picked_qty, "picked"))

        # Available rolls — potong jadi roll realistis
        remaining_avail = available_qty
        while remaining_avail > 0.01:
            take = min(remaining_avail, MAX_AVAILABLE_ROLL_LEN)
            roll_docs.append(_make_roll(product_id, warehouse_id, owner, lot, take, "available"))
            remaining_avail -= take

    if roll_docs:
        await db.inventory_rolls.insert_many(roll_docs)

    n_segments = await rebuild_all_balances()
    return {"rolls": len(roll_docs), "segments": n_segments, "skipped": 0}


# ── Reservasi level-roll (owner-scoped, FEFO, single-warehouse preference) ────

async def _reserve_single_roll(roll_id: str, order_id: str) -> Optional[Dict[str, Any]]:
    return await db.inventory_rolls.find_one_and_update(
        {"id": roll_id, "status": "available"},
        {"$set": {"status": "reserved", "reserved_ref": {"type": "sales_order", "id": order_id},
                  "earmarked_for": None, "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER,
    )


async def _split_roll(roll: Dict[str, Any], take: float, order_id: str) -> Dict[str, Any]:
    """Pecah roll available: kurangi sisa parent, buat child roll reserved sebesar `take`."""
    parent_remaining = float(roll["length_remaining"]) - take
    await db.inventory_rolls.update_one(
        {"id": roll["id"]},
        {"$set": {"length_remaining": round(parent_remaining, 2),
                  "length_initial": round(float(roll["length_initial"]) - take, 2),
                  "updated_at": now_iso()}},
    )
    child = dict(roll)
    child.pop("_id", None)
    child.update({
        "id": new_id("roll"),
        "length_initial": round(take, 2),
        "length_remaining": round(take, 2),
        "status": "reserved",
        "reserved_ref": {"type": "sales_order", "id": order_id},
        "earmarked_for": None,
        "is_remnant": False,
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    await db.inventory_rolls.insert_one(dict(child))
    return child


# ── Policy-aware allocation planner (Sub-fase 1.7, KN_15 §6) ─────────────────

DEFAULT_ALLOCATION_POLICY: Dict[str, Any] = {
    "mode": "auto",
    "priority_order": ["owner", "lot", "location", "roll_efficiency"],
    "lot_mode": "prefer_single",
    "lot_selection": "fefo",
    "location_pref": "single_warehouse",
    "allow_intercompany": True,
    "allow_partial": True,
}


async def _available_rolls_for_order(product_id: str, owner_entity_id: str, order_id: str,
                                     customer_id: str = "") -> List[Dict[str, Any]]:
    """Roll available owner-scoped untuk dialokasikan ke `order_id`/`customer_id`.
    Menghormati EARMARK (pegging): roll yang di-earmark untuk demand LAIN dikecualikan;
    roll yang di-earmark untuk order/customer ini tetap masuk (diprioritaskan planner)."""
    rolls = await db.inventory_rolls.find(
        {"product_id": product_id, "owner_entity_id": owner_entity_id, "status": "available",
         "length_remaining": {"$gt": 0}}, {"_id": 0},
    ).to_list(10000)
    out = []
    for r in rolls:
        ear = r.get("earmarked_for")
        if ear and isinstance(ear, dict):
            etype, eid = ear.get("type"), ear.get("id")
            if etype == "order" and eid and eid != order_id:
                continue  # di-pegging untuk order lain
            if etype == "customer" and eid and eid != customer_id:
                continue  # di-pegging untuk customer lain
        out.append(r)
    return out


def _wh_rank_factory(warehouses: Dict[str, Any], city: str):
    priority = WAREHOUSE_PRIORITY.get(city, [city, "Jakarta", "Bandung", "Surabaya"])

    def rank(wid: str) -> int:
        c = warehouses.get(wid, {}).get("city", "")
        return priority.index(c) if c in priority else 99
    return rank


def _lot_age(rolls_in_lot: List[Dict[str, Any]]) -> str:
    return min((r.get("created_at", "") for r in rolls_in_lot), default="")


def _order_rolls_in_lot(rolls: List[Dict[str, Any]], wh_rank, location_pref: str) -> List[Dict[str, Any]]:
    """Urutkan roll dalam satu lot: roll yang di-pegging (untuk demand ini) dulu →
    location_pref → FEFO/roll-eff."""
    def key(r):
        earmarked_here = 0 if r.get("earmarked_for") else 1
        if location_pref == "fewest_splits":
            return (earmarked_here, -float(r["length_remaining"]), wh_rank(r["warehouse_id"]), r.get("created_at", ""))
        # single_warehouse & nearest_customer → cluster gudang prioritas dulu, FEFO, roll besar dulu
        return (earmarked_here, wh_rank(r["warehouse_id"]), r.get("created_at", ""), -float(r["length_remaining"]))
    return sorted(rolls, key=key)


def _lot_has_earmark(rolls_in_lot: List[Dict[str, Any]]) -> bool:
    return any(r.get("earmarked_for") for r in rolls_in_lot)


def _order_lots(lots: List[str], by_lot: Dict[str, List[Dict[str, Any]]],
                per_lot_available: Dict[str, float], lot_selection: str) -> List[str]:
    # Lot yang berisi roll di-pegging (untuk demand ini) selalu didahulukan.
    def peg_key(l):
        return 0 if _lot_has_earmark(by_lot[l]) else 1
    if lot_selection == "smallest_fit":
        return sorted(lots, key=lambda l: (peg_key(l), per_lot_available[l]))
    if lot_selection == "largest_fit":
        return sorted(lots, key=lambda l: (peg_key(l), -per_lot_available[l]))
    return sorted(lots, key=lambda l: (peg_key(l), _lot_age(by_lot[l])))  # fefo/fifo → lot tertua dulu


def _select_single_lot(lots_enough: List[str], by_lot, per_lot_available, lot_selection: str) -> str:
    # Bila ada lot pegged yang cukup, pilih dari situ dulu (pegging customer pakai stok-nya).
    pegged = [l for l in lots_enough if _lot_has_earmark(by_lot[l])]
    pool = pegged or lots_enough
    if lot_selection == "smallest_fit":
        return min(pool, key=lambda l: per_lot_available[l])
    if lot_selection == "largest_fit":
        return max(pool, key=lambda l: per_lot_available[l])
    return min(pool, key=lambda l: _lot_age(by_lot[l]))  # fefo/fifo


def _build_allocation_plan(rolls: List[Dict[str, Any]], quantity: float, city: str,
                           warehouses: Dict[str, Any], policy: Dict[str, Any],
                           order_id: str = "") -> Dict[str, Any]:
    """READ-ONLY: hasilkan urutan roll (`ordered_rolls`) + meta lot untuk 1 baris.
    Menerapkan R1/R2/R3/R4 + location_pref. Tidak memutasi DB."""
    lot_mode = policy.get("lot_mode", "prefer_single")
    lot_selection = policy.get("lot_selection", "fefo")
    location_pref = policy.get("location_pref", "single_warehouse")
    dye_strict = bool(policy.get("dye_lot_strict", False))
    wh_rank = _wh_rank_factory(warehouses, city)

    # P0-4 — bila dye_lot_strict: kelompokkan per DYE LOT aktual (tekstil) & paksa
    # lot tunggal (strict_single). Default: kelompokkan per `lot` generik (perilaku lama).
    if dye_strict:
        lot_mode = "strict_single"
        def _grp(r):
            return r.get("dye_lot") or r.get("lot") or "—"
    else:
        def _grp(r):
            return r.get("lot") or "—"

    by_lot: Dict[str, List[Dict[str, Any]]] = {}
    for r in rolls:
        by_lot.setdefault(_grp(r), []).append(r)
    per_lot_available = {lot: round(sum(float(x["length_remaining"]) for x in rs), 2)
                         for lot, rs in by_lot.items()}
    total_available = round(sum(per_lot_available.values()), 2)
    Q = round(float(quantity), 2)

    base = {"total_available": total_available, "lot_selection": lot_selection,
            "lot_mode_policy": lot_mode, "ordered_rolls": []}
    if Q <= 0.01 or total_available <= 0.01:
        return {**base, "reserved_qty": 0.0, "backorder_qty": round(max(Q, 0), 2),
                "lot_mode": "single", "lots_used": [], "requires_confirmation": False,
                "explanation": "Tidak ada stok tersedia." if total_available <= 0.01 else "Qty nol."}

    lots_enough = [lot for lot in by_lot if per_lot_available[lot] + 0.01 >= Q]
    ordered_rolls: List[Dict[str, Any]] = []

    if lots_enough:
        lot = _select_single_lot(lots_enough, by_lot, per_lot_available, lot_selection)
        ordered_rolls = _order_rolls_in_lot(by_lot[lot], wh_rank, location_pref)
        reason = f"Lot tunggal {lot} cukup (kebijakan {lot_selection.upper()})."
    elif lot_mode == "strict_single":
        best = max(by_lot, key=lambda l: per_lot_available[l])
        ordered_rolls = _order_rolls_in_lot(by_lot[best], wh_rank, location_pref)
        reason = (f"Kebijakan strict_single: hanya lot tunggal terbesar {best} "
                  f"({per_lot_available[best]}); sisa → backorder/shipment terpisah.")
    else:
        lots_ordered = _order_lots(list(by_lot.keys()), by_lot, per_lot_available, lot_selection)
        for lot in lots_ordered:
            ordered_rolls.extend(_order_rolls_in_lot(by_lot[lot], wh_rank, location_pref))
        reason = "Qty melebihi lot tunggal terbesar → pemenuhan lintas-lot (mixed)."

    # Simulasi konsumsi untuk tahu lot AKTUAL & qty terpenuhi (tanpa mutasi)
    effective = min(Q, total_available)
    consumed = 0.0
    lots_used: List[str] = []
    for r in ordered_rolls:
        if consumed + 0.01 >= effective:
            break
        rlen = float(r["length_remaining"])
        take = min(rlen, round(effective - consumed, 2))
        if take <= 0.01:
            continue
        consumed = round(consumed + take, 2)
        lt = r.get("lot") or "—"
        if lt not in lots_used:
            lots_used.append(lt)

    actual_lot_mode = "single" if len(lots_used) <= 1 else "mixed"
    requires_confirmation = (lot_mode == "prefer_single" and actual_lot_mode == "mixed")
    backorder = round(max(Q - consumed, 0.0), 2)
    if backorder > 0.01 and "backorder" not in reason:
        reason += f" Sisa {backorder} → backorder."
    if actual_lot_mode == "mixed":
        reason += f" Lot dipakai: {', '.join(lots_used)}."
    return {**base, "ordered_rolls": ordered_rolls, "reserved_qty": round(consumed, 2),
            "backorder_qty": backorder, "lot_mode": actual_lot_mode, "lots_used": lots_used,
            "requires_confirmation": requires_confirmation, "explanation": reason}


def _explain_allocation(qty: float, lots: List[str], wh: Dict[str, Any], owner: str,
                        order_lot_mode: str, policy: Dict[str, Any], plan: Dict[str, Any]) -> str:
    """CLARITY (KN_15 §6.0): kalimat penjelasan per sub-alokasi (per warehouse)."""
    lot_txt = lots[0] if len(lots) == 1 else (" + ".join(lots) if lots else "—")
    sel = policy.get("lot_selection", "fefo").upper()
    wh_name = wh.get("name", wh.get("id", "Gudang"))
    if len(lots) > 1:
        base = f"{qty} dari Lot {lot_txt} ({sel}) · {wh_name} — lintas-lot di gudang ini."
    else:
        base = f"{qty} dari Lot {lot_txt} ({sel}) · {wh_name} — lot tunggal."
    if order_lot_mode == "mixed" and len(lots) <= 1:
        base += " Bagian dari pemenuhan lintas-lot (baris mixed)."
    return base


async def preview_line_allocation(product_id: str, quantity: float, city: str,
                                  owner_entity_id: str, policy: Dict[str, Any],
                                  order_id: str = "", customer_id: str = "") -> Dict[str, Any]:
    """READ-ONLY: rencana alokasi 1 baris (tanpa reservasi) — untuk preview & konfirmasi mixed-lot."""
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    rolls = await _available_rolls_for_order(product_id, owner_entity_id, order_id, customer_id)
    pol = {**DEFAULT_ALLOCATION_POLICY, **(policy or {})}
    plan = _build_allocation_plan(rolls, quantity, city, warehouses, pol, order_id)
    return {
        "product_id": product_id,
        "requested_qty": round(float(quantity), 2),
        "reserved_qty": plan["reserved_qty"],
        "backorder_qty": plan["backorder_qty"],
        "lot_mode": plan["lot_mode"],
        "lots_used": plan["lots_used"],
        "requires_confirmation": plan["requires_confirmation"],
        "explanation": plan["explanation"],
        "total_available": plan["total_available"],
        "lot_selection": pol["lot_selection"],
        "lot_mode_policy": pol["lot_mode"],
        "dye_lot_strict": bool(pol.get("dye_lot_strict", False)),
    }


async def allocate_and_reserve_rolls(
    product_id: str, quantity: float, city: str, owner_entity_id: str, order_id: str,
    allow_partial: bool = False, policy: Optional[Dict[str, Any]] = None, customer_id: str = "",
) -> List[Dict[str, Any]]:
    """Reservasi roll owner-scoped untuk 1 baris order — POLICY-AWARE (Sub-fase 1.7).

    Menerapkan KN_15 §6 (R1 single-lot preference, R2 mixed-lot exception, R3 lot
    selection fefo/fifo/smallest/largest, R4 lot_mode prefer_single/strict_single/
    allow_mixed) + location_pref. Mengembalikan daftar alokasi per warehouse
    (kompatibel struktur SO lama) + `lot_mode` & `allocation_explanation` (CLARITY).

    Sub-fase 1.6 — Backorder:
      - `allow_partial=False` (default): bila stok < quantity → 409.
      - `allow_partial=True`: reservasi hanya sebesar stok TERSEDIA; sisa = backorder.
    """
    pol = {**DEFAULT_ALLOCATION_POLICY, **(policy or {})}
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}

    rolls = await _available_rolls_for_order(product_id, owner_entity_id, order_id, customer_id)
    plan = _build_allocation_plan(rolls, quantity, city, warehouses, pol)
    total_available = plan["total_available"]

    if total_available + 0.01 < quantity and not allow_partial:
        raise HTTPException(
            status_code=409,
            detail=f"Stok milik entitas tidak mencukupi (tersedia {round(total_available,2)} dari {quantity}). "
                   f"Aktifkan backorder untuk memesan sisa stok yang akan datang.",
        )

    effective_qty = round(min(quantity, total_available), 2)
    if effective_qty <= 0.01:
        return []  # full backorder (caller catat)

    remaining = effective_qty
    per_wh: Dict[str, Dict[str, Any]] = {}

    # Reservasi mengikuti URUTAN dari planner (R1/R2/R3 + location_pref).
    for roll in plan["ordered_rolls"]:
        if remaining <= 0.01:
            break
        rlen = float(roll["length_remaining"])
        wid = roll["warehouse_id"]
        bucket = per_wh.setdefault(wid, {"qty": 0.0, "rolls": [], "lots": set(), "dye_lots": set()})
        if rlen <= remaining + 0.01:
            reserved = await _reserve_single_roll(roll["id"], order_id)
            if not reserved:
                continue  # keburu diambil order lain → lewati
            take = float(reserved["length_remaining"])
            bucket["rolls"].append({"roll_id": reserved["id"], "roll_no": reserved.get("roll_no"),
                                    "lot": reserved.get("lot"), "dye_lot": reserved.get("dye_lot") or reserved.get("lot"),
                                    "length": take})
            bucket["lots"].add(reserved.get("lot"))
            bucket["dye_lots"].add(reserved.get("dye_lot") or reserved.get("lot"))
            bucket["qty"] += take
            remaining -= take
        else:
            child = await _split_roll(roll, remaining, order_id)
            bucket["rolls"].append({"roll_id": child["id"], "roll_no": child.get("roll_no"),
                                    "lot": child.get("lot"), "dye_lot": child.get("dye_lot") or child.get("lot"),
                                    "length": float(child["length_remaining"])})
            bucket["lots"].add(child.get("lot"))
            bucket["dye_lots"].add(child.get("dye_lot") or child.get("lot"))
            bucket["qty"] += float(child["length_remaining"])
            remaining = 0.0
            break

    if remaining > 0.01 and not allow_partial:
        await release_order_rolls(order_id)
        raise HTTPException(status_code=409, detail="Stok berubah saat reservasi. Silakan refresh katalog.")

    # Lot mode aktual = gabungan lot lintas-warehouse (mixed bila >1 lot dipakai)
    all_lots = sorted({lot for info in per_wh.values() for lot in info["lots"] if lot})
    order_lot_mode = "single" if len(all_lots) <= 1 else "mixed"

    allocations: List[Dict[str, Any]] = []
    for wid, info in per_wh.items():
        wh = warehouses.get(wid, {})
        lots = sorted(x for x in info["lots"] if x)
        dye_lots = sorted(x for x in info["dye_lots"] if x)
        explanation = _explain_allocation(round(info["qty"], 2), lots, wh, owner_entity_id,
                                          order_lot_mode, pol, plan)
        allocations.append({
            "id": new_id("alloc"),
            "product_id": product_id,
            "warehouse_id": wid,
            "warehouse_name": wh.get("name", wid),
            "warehouse_city": wh.get("city", ""),
            "owner_entity_id": owner_entity_id,
            "quantity": round(info["qty"], 2),
            "lot": lots[0] if len(lots) == 1 else None,
            "lots": lots,
            "dye_lot": dye_lots[0] if len(dye_lots) == 1 else None,
            "dye_lots": dye_lots,
            "lot_mode": "single" if len(lots) <= 1 else "mixed",
            "allocation_explanation": explanation,
            "policy_lot_selection": pol["lot_selection"],
            "dye_lot_strict": bool(pol.get("dye_lot_strict", False)),
            "rolls": info["rolls"],
            "status": "allocated",
        })
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": product_id, "warehouse_id": wid,
            "owner_entity_id": owner_entity_id, "movement_type": "reservation",
            "quantity": round(info["qty"], 2), "unit": wh.get("unit", "meter"),
            "lot": lots[0] if lots else "", "roll_id": ",".join(r["roll_id"] for r in info["rolls"]),
            "source_document": order_id, "timestamp": now_iso(),
        })
        await rebuild_balance(product_id, wid, owner_entity_id)
    return allocations


async def release_order_rolls(order_id: str) -> float:
    """Lepas semua roll yang ter-reserve untuk order tertentu → kembali available.
    Mengembalikan total qty yang dilepas. Rebuild balance segmen terdampak."""
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": order_id, "status": {"$in": ORDER_HELD_STATUSES}}, {"_id": 0},
    ).to_list(10000)
    if not held:
        return 0.0
    segments = set()
    total = 0.0
    for r in held:
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            {"$set": {"status": "available", "reserved_ref": None, "updated_at": now_iso()}},
        )
        total += float(r.get("length_remaining", 0) or 0)
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
            "owner_entity_id": r["owner_entity_id"], "movement_type": "release_reservation",
            "quantity": round(float(r.get("length_remaining", 0) or 0), 2), "unit": r.get("unit", "meter"),
            "lot": r.get("lot", ""), "roll_id": r["id"], "source_document": order_id, "timestamp": now_iso(),
        })
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return round(total, 2)


async def set_order_rolls_status(order_id: str, new_status: str) -> int:
    """Ubah status roll milik order (mis. reserved→committed saat approve)."""
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": order_id, "status": {"$in": ORDER_HELD_STATUSES}}, {"_id": 0},
    ).to_list(10000)
    segments = set()
    for r in held:
        await db.inventory_rolls.update_one(
            {"id": r["id"]}, {"$set": {"status": new_status, "updated_at": now_iso()}}
        )
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return len(held)


# ── Pengiriman (Sub-fase 1.8): committed → in_transit_sales (SSOT-safe) ───────

SHIPPABLE_STATUSES = ["committed", "packed", "picked", "reserved"]


async def ship_order_rolls(order_id: str, product_id: str, warehouse_id: str, qty: float) -> Dict[str, Any]:
    """Kirim (dispatch) `qty` dari roll milik order utk segmen product×warehouse:
    committed/picked/packed/reserved → in_transit_sales (FEFO, split bila parsial).
    SSOT-safe (KN_15 §10): TIDAK pernah $inc balance — on_hand turun otomatis karena
    in_transit_sales adalah bucket TRANSIT (bukan fisik). rebuild_balance dipanggil.
    Return: {shipped: float, rolls: [{roll_id, lot, length, unit}]}."""
    qty = round(float(qty), 2)
    if qty <= 0:
        return {"shipped": 0.0, "rolls": []}
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": order_id, "product_id": product_id, "warehouse_id": warehouse_id,
         "status": {"$in": SHIPPABLE_STATUSES}, "length_remaining": {"$gt": 0}}, {"_id": 0},
    ).to_list(10000)
    held.sort(key=lambda r: (r.get("created_at", ""), float(r.get("length_remaining", 0))))
    total_avail = sum(float(r["length_remaining"]) for r in held)
    if total_avail + 0.01 < qty:
        raise HTTPException(
            status_code=409,
            detail=f"Roll commit untuk order tak cukup dikirim (tersedia {round(total_avail,2)} dari {qty}).")
    remaining = qty
    shipped_rolls: List[Dict[str, Any]] = []
    segments = set()
    for roll in held:
        if remaining <= 0.01:
            break
        rlen = float(roll["length_remaining"])
        take = min(rlen, remaining)
        if take >= rlen - 0.01:
            await db.inventory_rolls.update_one(
                {"id": roll["id"]},
                {"$set": {"status": "in_transit_sales", "shipped_at": now_iso(), "updated_at": now_iso()}})
            ship_id, ship_len = roll["id"], rlen
        else:
            parent_remaining = rlen - take
            await db.inventory_rolls.update_one(
                {"id": roll["id"]},
                {"$set": {"length_remaining": round(parent_remaining, 2),
                          "length_initial": round(float(roll["length_initial"]) - take, 2),
                          "updated_at": now_iso()}})
            child = dict(roll); child.pop("_id", None)
            child.update({
                "id": new_id("roll"), "length_initial": round(take, 2),
                "length_remaining": round(take, 2), "status": "in_transit_sales",
                "shipped_at": now_iso(), "is_remnant": False,
                "created_at": now_iso(), "updated_at": now_iso()})
            await db.inventory_rolls.insert_one(dict(child))
            ship_id, ship_len = child["id"], take
        shipped_rolls.append({"roll_id": ship_id, "lot": roll.get("lot", ""),
                              "length": round(ship_len, 2), "unit": roll.get("unit", "meter")})
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": product_id, "warehouse_id": warehouse_id,
            "owner_entity_id": roll.get("owner_entity_id"), "movement_type": "outbound_ship",
            "quantity": -round(ship_len, 2), "unit": roll.get("unit", "meter"),
            "lot": roll.get("lot", ""), "roll_id": ship_id, "source_document": order_id,
            "timestamp": now_iso()})
        segments.add((product_id, warehouse_id, roll["owner_entity_id"]))
        remaining -= take
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return {"shipped": round(qty - max(remaining, 0), 2), "rolls": shipped_rolls}


async def deliver_order_rolls(order_id: str) -> int:
    """Tandai terkirim/diterima (done): roll in_transit_sales order → 'delivered' (terminal,
    keluar dari owned_qty). rebuild_balance segmen terdampak."""
    rolls = await db.inventory_rolls.find(
        {"reserved_ref.id": order_id, "status": "in_transit_sales"}, {"_id": 0},
    ).to_list(10000)
    segments = set()
    for r in rolls:
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            {"$set": {"status": "delivered", "delivered_at": now_iso(), "updated_at": now_iso()}})
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return len(rolls)


# ── Inter-company ownership transfer (Sub-fase 1.5, KN_15 §7 + D3) ────────────

def _split_roll_for_ref(roll: Dict[str, Any], take: float, ref: Dict[str, Any]) -> Dict[str, Any]:
    """Bangun child-roll reserved sebesar `take` dengan reserved_ref generik (mis. transfer).
    (Caller wajib meng-update parent length & insert child — lihat reserve_rolls_for_transfer.)"""
    child = dict(roll)
    child.pop("_id", None)
    child.update({
        "id": new_id("roll"),
        "length_initial": round(take, 2),
        "length_remaining": round(take, 2),
        "status": "reserved",
        "reserved_ref": ref,
        "is_remnant": False,
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    return child


async def reserve_rolls_for_transfer(
    product_id: str, source_entity_id: str, quantity: float, transfer_id: str
) -> List[Dict[str, Any]]:
    """Reservasi roll milik entitas SUMBER (B) untuk inter-company transfer (FEFO, split).
    Set status=reserved, reserved_ref={type:'transfer', id:transfer_id} agar B tak dobel-jual.
    Mengembalikan daftar roll yang direservasi. Raise 409 bila stok B tak cukup."""
    ref = {"type": "transfer", "id": transfer_id}
    rolls = await db.inventory_rolls.find(
        {"product_id": product_id, "owner_entity_id": source_entity_id, "status": "available",
         "length_remaining": {"$gt": 0}}, {"_id": 0},
    ).to_list(10000)
    # FEFO: lot tertua (created_at) dulu, roll besar dulu
    rolls.sort(key=lambda r: (r.get("created_at", ""), -float(r.get("length_remaining", 0))))

    total = sum(float(r["length_remaining"]) for r in rolls)
    if total + 0.01 < quantity:
        raise HTTPException(
            status_code=409,
            detail=f"Stok entitas sumber tidak cukup untuk transfer (tersedia {round(total,2)} dari {quantity}).",
        )

    remaining = quantity
    reserved: List[Dict[str, Any]] = []
    for roll in rolls:
        if remaining <= 0.01:
            break
        rlen = float(roll["length_remaining"])
        if rlen <= remaining + 0.01:
            updated = await db.inventory_rolls.find_one_and_update(
                {"id": roll["id"], "status": "available"},
                {"$set": {"status": "reserved", "reserved_ref": ref, "updated_at": now_iso()}},
                projection={"_id": 0}, return_document=ReturnDocument.AFTER,
            )
            if not updated:
                continue  # keburu diambil transaksi lain
            reserved.append(updated)
            remaining -= float(updated["length_remaining"])
        else:
            # roll lebih besar dari kebutuhan → split: kurangi parent, buat child reserved
            child = _split_roll_for_ref(roll, remaining, ref)
            parent_remaining = rlen - remaining
            await db.inventory_rolls.update_one(
                {"id": roll["id"]},
                {"$set": {"length_remaining": round(parent_remaining, 2),
                          "length_initial": round(float(roll["length_initial"]) - remaining, 2),
                          "updated_at": now_iso()}},
            )
            await db.inventory_rolls.insert_one(dict(child))
            reserved.append(child)
            remaining = 0.0
            break

    if remaining > 0.01:
        # race condition → rollback reservasi parsial
        await release_transfer_rolls(transfer_id)
        raise HTTPException(status_code=409, detail="Stok sumber berubah saat reservasi transfer. Coba lagi.")

    segments = {(r["product_id"], r["warehouse_id"], r["owner_entity_id"]) for r in reserved}
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return reserved


async def execute_ownership_transfer(transfer: Dict[str, Any]) -> Dict[str, Any]:
    """Pindahkan kepemilikan roll yang direservasi transfer dari source→dest (S3: SAAT APPROVE).
    owner_entity_id B→E, acquired.via='transfer', status kembali 'available' (kini milik E).
    Catat movement ownership_transfer_out (B) + ownership_transfer_in (E). Rebuild balance kedua segmen."""
    transfer_id = transfer["id"]
    src = transfer["source_entity_id"]
    dst = transfer["dest_entity_id"]
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": transfer_id, "reserved_ref.type": "transfer", "status": "reserved"},
        {"_id": 0},
    ).to_list(10000)
    segments = set()
    moved = 0.0
    for r in held:
        qty = float(r.get("length_remaining", 0) or 0)
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            {"$set": {"owner_entity_id": dst, "status": "available", "reserved_ref": None,
                      "acquired": {"via": "transfer", "ref_id": transfer_id, "date": now_iso()},
                      "updated_at": now_iso()}},
        )
        moved += qty
        base_mov = {
            "product_id": r["product_id"], "warehouse_id": r["warehouse_id"],
            "unit": r.get("unit", "meter"), "lot": r.get("lot", ""), "roll_id": r["id"],
            "from_owner_entity_id": src, "to_owner_entity_id": dst,
            "source_document": transfer.get("code", transfer_id), "timestamp": now_iso(),
        }
        await db.inventory_movements.insert_one({
            **base_mov, "id": new_id("mov"), "owner_entity_id": src,
            "movement_type": "ownership_transfer_out", "quantity": -round(qty, 2),
        })
        await db.inventory_movements.insert_one({
            **base_mov, "id": new_id("mov"), "owner_entity_id": dst,
            "movement_type": "ownership_transfer_in", "quantity": round(qty, 2),
        })
        segments.add((r["product_id"], r["warehouse_id"], src))
        segments.add((r["product_id"], r["warehouse_id"], dst))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return {"moved_qty": round(moved, 2), "rolls": len(held)}


async def release_transfer_rolls(transfer_id: str) -> float:
    """Lepas roll yang direservasi untuk transfer (reject/cancel) → kembali available milik sumber."""
    held = await db.inventory_rolls.find(
        {"reserved_ref.id": transfer_id, "reserved_ref.type": "transfer", "status": "reserved"},
        {"_id": 0},
    ).to_list(10000)
    segments = set()
    total = 0.0
    for r in held:
        await db.inventory_rolls.update_one(
            {"id": r["id"]},
            {"$set": {"status": "available", "reserved_ref": None, "updated_at": now_iso()}},
        )
        total += float(r.get("length_remaining", 0) or 0)
        segments.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
    for p, w, o in segments:
        await rebuild_balance(p, w, o)
    return round(total, 2)
