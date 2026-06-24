"""
Sub-fase 1.11 — Returns & Barang Sisa
Service: buat return, proses penyesuaian stok saat approved.

Alur:
  Sales/Admin buat Return (draft/pending) → attach bukti foto →
  Manager/Admin approve → stock_adjusted (rolls baru + rebuild_balance).
Jenis return: retur | bs (Barang Sisa) | penggantian
"""
import re
from typing import Any, Dict, List
from db import db
from core_utils import now_iso, new_id
from services.roll_service import rebuild_balance
from services import gl_service
from services.customer_service import order_payment_method, NON_AR_METHODS

# F3 — jenis retur/RMA yang valid (berbasis SO). komplain/garansi = aftersales.
VALID_RETURN_TYPES = {"retur", "bs", "penggantian", "komplain", "garansi"}


# ─── ID generator ───────────────────────────────────────────────────────────

async def next_return_number() -> str:
    """Generate SRET-XXXXX auto-increment."""
    last = await db.sales_returns.find_one(
        {"number": {"$regex": r"^SRET-"}},
        sort=[("number", -1)]
    )
    if last and last.get("number"):
        m = re.search(r"(\d+)$", last["number"])
        n = int(m.group(1)) + 1 if m else 1
    else:
        n = 1
    return f"SRET-{n:05d}"


async def next_credit_note_number() -> str:
    """F3 — Generate CN-XXXXX auto-increment (Credit Note / Nota Kredit)."""
    last = await db.credit_notes.find_one(
        {"number": {"$regex": r"^CN-"}}, sort=[("number", -1)])
    if last and last.get("number"):
        m = re.search(r"(\d+)$", last["number"])
        n = int(m.group(1)) + 1 if m else 1
    else:
        n = 1
    return f"CN-{n:05d}"


async def _create_credit_note_and_post_gl(ret: Dict[str, Any]) -> Dict[str, Any]:
    """F3 — buat Credit Note dari sales_return yang di-approve + posting GL reversal.
    Nilai retur diambil dari harga item SO asli; HPP dari avg unit_cost roll.
    Idempotent: bila return sudah punya credit_note_id, kembalikan yang ada."""
    if ret.get("credit_note_id"):
        existing = await db.credit_notes.find_one({"id": ret["credit_note_id"]}, {"_id": 0})
        if existing:
            return existing

    order = await db.sales_orders.find_one({"id": ret["order_id"]}, {"_id": 0}) or {}
    price_by_pid: Dict[str, float] = {}
    for it in order.get("items", []):
        price_by_pid[it.get("product_id")] = float(it.get("price", it.get("unit_price", 0)) or 0)

    eid = ret.get("entity_id", "")
    lines: List[Dict[str, Any]] = []
    net = 0.0
    cogs = 0.0
    for item in ret.get("items", []):
        pid = item.get("product_id")
        qty = float(item.get("quantity_returned", 0) or 0)
        if qty <= 0:
            continue
        unit_price = price_by_pid.get(pid, 0.0)
        line_net = round(qty * unit_price, 2)
        unit_cost = await gl_service._avg_unit_cost(pid, eid)
        net += line_net
        # COGS reversal hanya untuk barang yang benar-benar masuk stok kembali (condition ok)
        if item.get("condition", "ok") != "damaged":
            cogs += qty * unit_cost
        lines.append({"product_id": pid, "product_name": item.get("product_name", ""),
                      "quantity": round(qty, 2), "unit": item.get("unit", "meter"),
                      "unit_price": unit_price, "line_total": line_net,
                      "reason": item.get("reason", ""), "condition": item.get("condition", "ok")})

    net = round(net, 2)
    cogs = round(cogs, 2)
    ppn_rate = float(order.get("ppn_rate", 0) or 0)
    has_ppn = ppn_rate > 0 and net > 0
    ppn = round(net * ppn_rate, 2) if has_ppn else 0.0
    gross = round(net + ppn, 2)
    is_cash = order_payment_method(order) in NON_AR_METHODS

    cn_number = await next_credit_note_number()
    now = now_iso()
    cn = {
        "id": new_id("cn"), "number": cn_number,
        "return_id": ret["id"], "return_number": ret.get("number", ""),
        "order_id": ret["order_id"], "order_number": ret.get("order_number", ""),
        "customer_id": ret.get("customer_id"), "customer_name": ret.get("customer_name", ""),
        "entity_id": eid, "return_type": ret.get("return_type", "retur"),
        "lines": lines, "net_amount": net, "ppn_rate": ppn_rate, "ppn_amount": ppn,
        "gross_amount": gross, "cogs_amount": cogs,
        "settlement": "cash" if is_cash else "ar",   # refund tunai vs pengurang piutang
        "status": "posted", "created_by": ret.get("approved_by", "system"),
        "created_at": now, "updated_at": now,
    }
    await db.credit_notes.insert_one(dict(cn))

    je = None
    try:
        je = await gl_service.post_sales_return(
            ret, return_net=net, return_ppn=ppn, return_cogs=cogs,
            is_cash=is_cash, credit_note_number=cn_number)
    except Exception:  # noqa: BLE001 — GL best-effort, CN tetap tercatat
        je = None
    if je:
        await db.credit_notes.update_one({"id": cn["id"]}, {"$set": {"journal_entry_id": je.get("id")}})
        cn["journal_entry_id"] = je.get("id")

    await db.sales_returns.update_one(
        {"id": ret["id"]},
        {"$set": {"credit_note_id": cn["id"], "credit_note_number": cn_number,
                  "credit_note_amount": gross, "updated_at": now}})
    return cn


# ─── CREATE ─────────────────────────────────────────────────────────────────

async def create_return(
    order_id: str,
    return_type: str,
    items: List[Dict],
    notes: str,
    entity_id: str,
    created_by: str,
    submit_now: bool = False,
) -> Dict[str, Any]:
    """
    Buat dokumen sales_return.
    items: [{product_id, product_name, quantity_returned, unit, reason, condition}]
    """
    order = await db.sales_orders.find_one({"id": order_id})
    if not order:
        raise ValueError(f"Pesanan {order_id} tidak ditemukan")

    # F3 — validasi jenis retur (RMA): retur | bs | penggantian | komplain | garansi
    if return_type not in VALID_RETURN_TYPES:
        raise ValueError(
            f"Jenis retur '{return_type}' tidak valid. Pilihan: {', '.join(sorted(VALID_RETURN_TYPES))}")

    # Resolve entity from order bila tidak diberikan
    if not entity_id:
        entity_id = order.get("entity_id", "")

    number = await next_return_number()
    now = now_iso()
    status = "pending_approval" if submit_now else "draft"

    doc = {
        "id":           new_id("sret"),
        "number":       number,
        "order_id":     order_id,
        "order_number": order.get("number", order_id),
        "customer_id":  order.get("customer_id"),
        "customer_name":order.get("customer_name", ""),
        "entity_id":    entity_id,
        "return_type":  return_type,    # retur | bs | penggantian
        "status":       status,
        "items":        items,
        "notes":        notes,
        "attachments":  [],
        "stock_adjusted": False,
        "created_by":   created_by,
        "approved_by":  None,
        "approved_at":  None,
        "rejected_by":  None,
        "rejected_at":  None,
        "reject_reason":None,
        "created_at":   now,
        "updated_at":   now,
    }
    await db.sales_returns.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ─── APPROVE + STOCK ADJUST ─────────────────────────────────────────────────

async def approve_and_adjust_stock(
    return_id: str,
    approved_by: str,
    notes: str = "",
) -> Dict[str, Any]:
    """
    Approve return → tambah kembali stok (buat rolls baru) → rebuild balance.
    Idempotent: jika stock_adjusted sudah True, skip stock adjustment.
    """
    ret = await db.sales_returns.find_one({"id": return_id})
    if not ret:
        raise ValueError(f"Return {return_id} tidak ditemukan")
    if ret["status"] not in ("draft", "pending_approval"):
        raise ValueError(f"Return {ret['number']} sudah {ret['status']}, tidak bisa di-approve")

    now = now_iso()

    # Tentukan warehouse dari outbound task atau fallback
    warehouse_id = await _resolve_return_warehouse(ret["order_id"])

    # Buat rolls baru untuk setiap item (bila belum diproses)
    if not ret.get("stock_adjusted"):
        for item in ret.get("items", []):
            qty = float(item.get("quantity_returned", 0))
            if qty <= 0:
                continue
            product_id = item["product_id"]
            condition  = item.get("condition", "ok")   # ok | damaged (informational only)

            roll = {
                "id":             new_id("roll"),
                "product_id":     product_id,
                "warehouse_id":   warehouse_id,
                "owner_entity_id":ret["entity_id"],
                "roll_number":    f"RTN-{ret['number'][-5:]}-{product_id[-4:]}",
                "length":         round(qty, 2),
                "length_initial": round(qty, 2),
                "status":         "available",
                "origin_type":    "return",
                "origin_ref":     ret["id"],
                "condition":      condition,
                "earmarked_for":  None,
                "committed_to":   None,
                "reserved_ref":   None,
                "lot":            f"RTN-{ret['number']}",
                "acquired": {"via": "return", "ref_id": ret["id"], "date": now},
                "created_at":     now,
                "updated_at":     now,
            }
            await db.inventory_rolls.insert_one(roll)

            # Catat movement
            await db.inventory_movements.insert_one({
                "id":              new_id("mov"),
                "product_id":      product_id,
                "warehouse_id":    warehouse_id,
                "owner_entity_id": ret["entity_id"],
                "type":            "return_in",
                "direction":       "in",
                "quantity":        round(qty, 2),
                "unit":            item.get("unit", "meter"),
                "roll_id":         roll["id"],
                "ref_type":        "sales_return",
                "ref_id":          ret["id"],
                "notes":           f"Retur {ret['number']} — {item.get('reason', '')}",
                "source_document": ret["id"],
                "timestamp":       now,
                "lot":             roll["lot"],
            })

        # Rebuild balances untuk semua (product, warehouse, entity) yang terpengaruh
        combos: set = set()
        for item in ret.get("items", []):
            combos.add((item["product_id"], warehouse_id, ret["entity_id"]))
        for (pid, wid, eid) in combos:
            await rebuild_balance(pid, wid, eid)

    # Update dokumen
    await db.sales_returns.update_one(
        {"id": return_id},
        {"$set": {
            "status":         "approved",
            "stock_adjusted": True,
            "approved_by":    approved_by,
            "approved_at":    now,
            "updated_at":     now,
        }}
    )
    ret = await db.sales_returns.find_one({"id": return_id})
    ret.pop("_id", None)
    # F3 — Credit Note + posting GL reversal (idempotent). Best-effort.
    try:
        cn = await _create_credit_note_and_post_gl(ret)
        ret["credit_note_id"] = cn["id"]
        ret["credit_note_number"] = cn["number"]
        ret["credit_note_amount"] = cn["gross_amount"]
    except Exception:  # noqa: BLE001
        pass
    return ret


# ─── REJECT ─────────────────────────────────────────────────────────────────

async def reject_return(
    return_id: str,
    rejected_by: str,
    reason: str,
) -> Dict[str, Any]:
    ret = await db.sales_returns.find_one({"id": return_id})
    if not ret:
        raise ValueError(f"Return {return_id} tidak ditemukan")
    if ret["status"] not in ("draft", "pending_approval"):
        raise ValueError(f"Return {ret['number']} sudah {ret['status']}")

    now = now_iso()
    await db.sales_returns.update_one(
        {"id": return_id},
        {"$set": {
            "status":       "rejected",
            "rejected_by":  rejected_by,
            "rejected_at":  now,
            "reject_reason":reason,
            "updated_at":   now,
        }}
    )
    ret = await db.sales_returns.find_one({"id": return_id})
    ret.pop("_id", None)
    return ret


# ─── HELPER: resolve warehouse ───────────────────────────────────────────────

async def _resolve_return_warehouse(order_id: str) -> str:
    """Cari warehouse dari outbound task atau fallback ke gudang pertama."""
    task = await db.wms_tasks.find_one(
        {"order_id": order_id, "type": "outbound"},
        sort=[("created_at", -1)]
    )
    if task and task.get("warehouse_id"):
        return task["warehouse_id"]

    wh = await db.warehouses.find_one({}, sort=[("created_at", 1)])
    return wh["id"] if wh else "wh_default"
