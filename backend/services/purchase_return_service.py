"""Depth #1 — Retur Beli (Purchase Return / Nota Debit).

Kebalikan dari Goods Receipt: barang dikembalikan ke supplier →
- KURANGI `inventory_rolls` available (FIFO owner-scoped, split bila parsial)
- catat movement `return_out` (keluar)
- terbitkan Nota Debit (DN-NNNNN) → mengurangi hutang (AP) PO terkait
- rebuild_balance segmen terdampak

Koleksi kanonik: `purchase_returns` (prefix pret_).
Status: draft → pending_approval → approved | rejected.
"""
import re
from typing import Any, Dict, List
from db import db
from core_utils import now_iso, new_id, DEFAULT_ENTITY_ID, safe_doc
from services.roll_service import rebuild_balance

RETURNED_STATUS = "returned_supplier"  # status terminal roll (tidak masuk bucket manapun)


async def next_return_number() -> str:
    last = await db.purchase_returns.find_one({"number": {"$regex": r"^PRET-"}}, sort=[("number", -1)])
    n = (int(re.search(r"(\d+)$", last["number"]).group(1)) + 1) if (last and last.get("number")) else 1
    return f"PRET-{n:05d}"


async def next_debit_note_number() -> str:
    last = await db.purchase_returns.find_one(
        {"debit_note_number": {"$regex": r"^DN-"}}, sort=[("debit_note_number", -1)])
    n = (int(re.search(r"(\d+)$", last["debit_note_number"]).group(1)) + 1) if (last and last.get("debit_note_number")) else 1
    return f"DN-{n:05d}"


async def create_purchase_return(payload, created_by: str) -> Dict[str, Any]:
    """Buat dokumen retur beli (draft/pending)."""
    supplier_id = payload.supplier_id
    supplier_name = ""
    if supplier_id:
        sup = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
        if not sup:
            raise ValueError("Supplier tidak ditemukan")
        supplier_name = sup.get("name", "")

    po = None
    warehouse_id = payload.warehouse_id
    entity_id = payload.entity_id or DEFAULT_ENTITY_ID
    if payload.po_id:
        po = await db.purchase_orders.find_one({"id": payload.po_id}, {"_id": 0})
        if not po:
            raise ValueError("Purchase Order tidak ditemukan")
        supplier_id = supplier_id or po.get("supplier_id", "")
        supplier_name = supplier_name or po.get("supplier_name", "")
        warehouse_id = warehouse_id or po.get("warehouse_id", "")
        entity_id = payload.entity_id or po.get("entity_id", DEFAULT_ENTITY_ID)

    if not supplier_name:
        raise ValueError("Supplier wajib dipilih")
    if not warehouse_id:
        raise ValueError("Gudang wajib dipilih")

    # Enrich items dengan nama produk + subtotal
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(2000)}
    items: List[Dict[str, Any]] = []
    total = 0.0
    for it in payload.items:
        prod = products.get(it.product_id)
        if not prod:
            raise ValueError(f"Produk {it.product_id} tidak ditemukan")
        price = it.price if it.price > 0 else _po_item_price(po, it.product_id) or float(prod.get("price", 0))
        subtotal = round(price * it.quantity, 2)
        total += subtotal
        # H4 — UOM otoritatif dari master produk (base_unit), bukan dari klien.
        # Cegah drift unit (mis. produk yard/pcs terlanjur tercatat "meter").
        unit = prod.get("base_unit") or (it.unit if it.unit else "") or "meter"
        items.append({
            "product_id": it.product_id, "sku": prod.get("sku", ""),
            "product_name": prod.get("name", ""), "quantity": float(it.quantity),
            "unit": unit, "price": price, "subtotal": subtotal,
            "reason": it.reason, "condition": it.condition,
        })

    number = await next_return_number()
    now = now_iso()
    doc = {
        "id": new_id("pret"), "number": number,
        "supplier_id": supplier_id, "supplier_name": supplier_name,
        "po_id": payload.po_id, "po_number": (po or {}).get("po_number", ""),
        "warehouse_id": warehouse_id,
        "warehouse_name": await _wh_name(warehouse_id),
        "entity_id": entity_id,
        "items": items, "total_amount": round(total, 2),
        "reason": payload.reason, "notes": payload.notes,
        "status": "pending_approval" if payload.submit_now else "draft",
        "debit_note_number": "", "stock_adjusted": False,
        "created_by": created_by, "approved_by": None, "approved_at": None,
        "rejected_by": None, "rejected_at": None, "reject_reason": None,
        "created_at": now, "updated_at": now,
    }
    await db.purchase_returns.insert_one(doc)
    return safe_doc(doc)


async def submit_purchase_return(return_id: str, submitted_by: str = "") -> Dict[str, Any]:
    ret = await db.purchase_returns.find_one({"id": return_id}, {"_id": 0})
    if not ret:
        raise ValueError("Retur tidak ditemukan")
    if ret["status"] != "draft":
        raise ValueError("Hanya draft yang bisa disubmit")
    await db.purchase_returns.update_one({"id": return_id},
        {"$set": {"status": "pending_approval", "submitted_at": now_iso(),
                  "submitted_by": submitted_by, "updated_at": now_iso()}})
    return safe_doc(await db.purchase_returns.find_one({"id": return_id}, {"_id": 0}))


async def approve_and_adjust_stock(return_id: str, approved_by: str, notes: str = "") -> Dict[str, Any]:
    """Approve retur → kurangi roll available → nota debit → kurangi AP PO."""
    ret = await db.purchase_returns.find_one({"id": return_id}, {"_id": 0})
    if not ret:
        raise ValueError("Retur tidak ditemukan")
    if ret["status"] not in ("draft", "pending_approval"):
        raise ValueError(f"Retur {ret['number']} sudah {ret['status']}")

    now = now_iso()
    warehouse_id = ret["warehouse_id"]
    entity_id = ret["entity_id"]

    if not ret.get("stock_adjusted"):
        segments = set()
        for item in ret.get("items", []):
            qty = float(item.get("quantity", 0))
            if qty <= 0:
                continue
            consumed = await _consume_available_rolls(item["product_id"], warehouse_id, entity_id, qty, ret)
            if consumed + 0.01 < qty:
                raise ValueError(
                    f"Stok available {item.get('sku')} tak cukup untuk retur "
                    f"(tersedia {round(consumed,2)} dari {qty}).")
            segments.add((item["product_id"], warehouse_id, entity_id))
        for (pid, wid, eid) in segments:
            await rebuild_balance(pid, wid, eid)

    debit_note = await next_debit_note_number()
    await db.purchase_returns.update_one({"id": return_id}, {"$set": {
        "status": "approved", "stock_adjusted": True, "debit_note_number": debit_note,
        "approved_by": approved_by, "approved_at": now, "decision_notes": notes,
        "updated_at": now,
    }})

    # Kurangi hutang (AP) pada PO terkait
    if ret.get("po_id"):
        await db.purchase_orders.update_one(
            {"id": ret["po_id"]},
            {"$inc": {"returned_amount": float(ret.get("total_amount", 0))},
             "$set": {"updated_at": now}})
        from routers.purchase_orders import recompute_po_payment_status
        await recompute_po_payment_status(ret["po_id"])

    return safe_doc(await db.purchase_returns.find_one({"id": return_id}, {"_id": 0}))


async def reject_purchase_return(return_id: str, rejected_by: str, reason: str) -> Dict[str, Any]:
    ret = await db.purchase_returns.find_one({"id": return_id}, {"_id": 0})
    if not ret:
        raise ValueError("Retur tidak ditemukan")
    if ret["status"] not in ("draft", "pending_approval"):
        raise ValueError(f"Retur {ret['number']} sudah {ret['status']}")
    now = now_iso()
    await db.purchase_returns.update_one({"id": return_id}, {"$set": {
        "status": "rejected", "rejected_by": rejected_by, "rejected_at": now,
        "reject_reason": reason, "updated_at": now,
    }})
    return safe_doc(await db.purchase_returns.find_one({"id": return_id}, {"_id": 0}))


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _consume_available_rolls(product_id, warehouse_id, owner_entity_id, qty, ret) -> float:
    """Kurangi roll available (FIFO) sebesar qty → status returned_supplier / split.
    Catat movement return_out. Return total qty yang berhasil dikurangi."""
    rolls = await db.inventory_rolls.find(
        {"product_id": product_id, "warehouse_id": warehouse_id,
         "owner_entity_id": owner_entity_id, "status": "available",
         "length_remaining": {"$gt": 0}}, {"_id": 0}).to_list(10000)
    rolls.sort(key=lambda r: (r.get("created_at", ""), float(r.get("length_remaining", 0))))
    remaining = round(float(qty), 2)
    consumed = 0.0
    for roll in rolls:
        if remaining <= 0.01:
            break
        rlen = float(roll["length_remaining"])
        take = min(rlen, remaining)
        if take >= rlen - 0.01:
            await db.inventory_rolls.update_one(
                {"id": roll["id"]},
                {"$set": {"status": RETURNED_STATUS, "returned_ref": {"type": "purchase_return", "id": ret["id"]},
                          "updated_at": now_iso()}})
        else:
            await db.inventory_rolls.update_one(
                {"id": roll["id"]},
                {"$set": {"length_remaining": round(rlen - take, 2),
                          "length_initial": round(float(roll["length_initial"]) - take, 2),
                          "updated_at": now_iso()}})
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": product_id, "warehouse_id": warehouse_id,
            "owner_entity_id": owner_entity_id, "type": "return_out", "movement_type": "return_out",
            "direction": "out", "quantity": -round(take, 2), "unit": roll.get("unit", "meter"),
            "roll_id": roll["id"], "ref_type": "purchase_return", "ref_id": ret["id"],
            "source_document": ret["number"], "lot": roll.get("lot", ""),
            "notes": f"Retur beli {ret['number']} ke {ret.get('supplier_name','')}",
            "timestamp": now_iso(),
        })
        consumed = round(consumed + take, 2)
        remaining = round(remaining - take, 2)
    return consumed


def _po_item_price(po, product_id) -> float:
    if not po:
        return 0.0
    for it in po.get("items", []):
        if it.get("product_id") == product_id:
            return float(it.get("price", 0) or 0)
    return 0.0


async def _wh_name(warehouse_id) -> str:
    if not warehouse_id:
        return ""
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0, "name": 1})
    return (wh or {}).get("name", "")
