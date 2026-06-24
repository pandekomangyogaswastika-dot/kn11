"""Pegging / Earmark router (KN_15) — soft-hold roll ke demand (customer/order).

Pegging = "tahan lunak" satu roll untuk demand spesifik TANPA reservasi keras.
- Roll tetap berstatus `available` (balance tidak berubah), tapi DIKECUALIKAN dari
  alokasi order/customer LAIN dan DIPRIORITASKAN saat demand-nya membuat order.
- Saat roll direservasi keras (order dibuat), `earmarked_for` otomatis di-clear
  (lihat roll_service._reserve_single_roll/_split_roll).
Invarian (verify_data_integrity): earmarked_for terisi ⟹ status == 'available'.
"""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from db import db
from dependencies import require_permission, require_role, audit
from core_utils import now_iso, safe_doc

router = APIRouter(prefix="/api")

PEG_ROLES = ["manager", "warehouse", "sales"]  # admin selalu diizinkan (require_role)


class EarmarkIn(BaseModel):
    ref_type: str = "customer"   # "customer" | "order"
    ref_id: str
    note: str = ""


async def _enrich(rolls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(2000)}
    entities = {e["id"]: e for e in await db.business_entities.find({}, {"_id": 0}).to_list(100)}
    for r in rolls:
        wh = warehouses.get(r.get("warehouse_id"), {})
        p = products.get(r.get("product_id"), {})
        ent = entities.get(r.get("owner_entity_id"), {})
        r["warehouse_name"] = wh.get("name", "")
        r["warehouse_city"] = wh.get("city", "")
        r["sku"] = p.get("sku", "")
        r["product_name"] = p.get("name", "")
        r["owner_entity_name"] = ent.get("short_name") or ent.get("legal_name", r.get("owner_entity_id", ""))
    return rolls


@router.get("/pegging/rolls")
async def list_earmarked(request: Request) -> List[Dict[str, Any]]:
    """Daftar roll yang sedang di-pegging (earmarked_for terisi)."""
    await require_permission(request, "product", "view")
    rolls = await db.inventory_rolls.find(
        {"earmarked_for": {"$ne": None}}, {"_id": 0}
    ).sort("updated_at", -1).to_list(5000)
    return await _enrich([safe_doc(r) for r in rolls])


@router.post("/inventory/rolls/{roll_id}/earmark")
async def earmark_roll(roll_id: str, payload: EarmarkIn, request: Request) -> Dict[str, Any]:
    """Pegging satu roll ke customer/order. Hanya roll `available` yang bisa di-pegging."""
    actor = await require_role(request, PEG_ROLES)
    roll = safe_doc(await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0}))
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    if roll.get("status") != "available":
        raise HTTPException(status_code=409, detail="Hanya roll berstatus 'available' yang bisa di-pegging.")
    if payload.ref_type not in ("customer", "order"):
        raise HTTPException(status_code=422, detail="ref_type harus 'customer' atau 'order'.")

    owner = roll.get("owner_entity_id")
    if payload.ref_type == "customer":
        cu = safe_doc(await db.customers.find_one({"id": payload.ref_id}, {"_id": 0}))
        if not cu:
            raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
        # Owner-scoped (KN_15 D3): customer hanya boleh dipenuhi stok entitasnya sendiri.
        if cu.get("entity_id") and owner and cu["entity_id"] != owner:
            raise HTTPException(status_code=409,
                                detail="Customer milik entitas lain — tidak bisa pegging stok entitas pemilik roll ini.")
        name = cu.get("name", payload.ref_id)
    else:
        o = safe_doc(await db.sales_orders.find_one({"id": payload.ref_id}, {"_id": 0}))
        if not o:
            raise HTTPException(status_code=404, detail="Sales order tidak ditemukan")
        name = o.get("number", payload.ref_id)

    ear = {"type": payload.ref_type, "id": payload.ref_id, "name": name,
           "note": (payload.note or "").strip(), "by": actor.get("name", "system"), "at": now_iso()}
    await db.inventory_rolls.update_one(
        {"id": roll_id}, {"$set": {"earmarked_for": ear, "updated_at": now_iso()}})
    await audit(actor.get("name", "system"), "earmark", "inventory_roll", roll_id, ear,
                f"Pegging roll {roll.get('roll_no')} → {payload.ref_type} {name}")
    return {"message": f"Roll {roll.get('roll_no')} di-pegging untuk {name}", "earmarked_for": ear}


@router.delete("/inventory/rolls/{roll_id}/earmark")
async def unearmark_roll(roll_id: str, request: Request) -> Dict[str, Any]:
    """Lepas pegging dari satu roll."""
    actor = await require_role(request, PEG_ROLES)
    roll = safe_doc(await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0}))
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    await db.inventory_rolls.update_one(
        {"id": roll_id}, {"$set": {"earmarked_for": None, "updated_at": now_iso()}})
    await audit(actor.get("name", "system"), "unearmark", "inventory_roll", roll_id,
                {"roll_no": roll.get("roll_no")}, "Lepas pegging")
    return {"message": f"Pegging roll {roll.get('roll_no')} dilepas", "id": roll_id}
