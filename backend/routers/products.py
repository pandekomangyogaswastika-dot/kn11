"""Products router: CRUD products + stock breakdown."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc
from schemas import GenericPatch, ProductPayload
from services.inventory_service import expire_old_reservations, product_summary
from services import pricelist_service
from entity_scope import entity_ctx

router = APIRouter(prefix="/api")


@router.get("/products")
async def list_products(request: Request) -> List[Dict[str, Any]]:
    await expire_old_reservations()
    products = await db.products.find({}, {"_id": 0}).to_list(100)
    # F1a — harga jual per-entitas: tampilkan harga efektif entitas aktif (fallback global).
    try:
        ctx = await entity_ctx(request)
        active = ctx.active_entity_id
    except Exception:
        active = None
    pmap = {p["id"]: p for p in products}
    price_map = await pricelist_service.resolve_many(active, [p["id"] for p in products], pmap)
    for product in products:
        product.update(await product_summary(product["id"]))
        info = price_map.get(product["id"], {})
        product["global_price"] = float(product.get("price", 0) or 0)
        if info.get("source") == "entity":
            product["price"] = info["price"]
        product["price_source"] = info.get("source", "global")
    return products


@router.post("/products")
async def create_product(payload: ProductPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "create")
    if await db.products.find_one({"sku": payload.sku}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="SKU sudah digunakan")
    product = payload.model_dump()
    product.update({"id": new_id("prod"), "batch_lot_rolls": [], "created_at": now_iso(), "updated_at": now_iso()})
    await db.products.insert_one(product)
    await audit(actor["name"], "product_created", "product", product["id"], product)
    return safe_doc(product)


@router.patch("/products/{product_id}")
async def update_product(product_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    allowed = ["sku", "name", "category", "variant", "color", "motif", "grade", "supplier",
               "base_unit", "price", "image", "description", "status", "uom_conversions", "harga_pokok", "gramasi", "lebar",
               "kg_per_meter", "reorder_point", "reorder_qty", "template_id", "variant_attrs"]
    data = {k: v for k, v in payload.data.items() if k in allowed}
    data["updated_at"] = now_iso()
    product = await db.products.find_one_and_update(
        {"id": product_id}, {"$set": data},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    await audit(actor["name"], "product_updated", "product", product_id, product)
    return product


@router.delete("/products/{product_id}")
async def delete_product(product_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "delete")
    product = await db.products.find_one_and_update(
        {"id": product_id},
        {"$set": {"status": "inactive", "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    await audit(actor["name"], "product_deactivated", "product", product_id, product)
    return product


@router.get("/products/{product_id}/stock-breakdown")
async def stock_breakdown(product_id: str) -> Dict[str, Any]:
    product = safe_doc(await db.products.find_one({"id": product_id}, {"_id": 0}))
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    balances_raw = await db.inventory_balances.find({"product_id": product_id}, {"_id": 0}).to_list(100)
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    entities = {e["id"]: e for e in await db.business_entities.find({}, {"_id": 0}).to_list(100)}
    reservations_raw = await db.sales_orders.find(
        {"allocations.product_id": product_id,
         "status": {"$in": ["reserved", "waiting_approval", "approved", "confirmed"]}},
        {"_id": 0}
    ).to_list(100)
    rolls_raw = await db.inventory_rolls.find({"product_id": product_id}, {"_id": 0}).to_list(5000)

    def _ent_name(eid):
        e = entities.get(eid, {})
        return e.get("short_name") or e.get("legal_name", eid)

    rows = []
    for balance in balances_raw:
        b = safe_doc(balance)
        warehouse = safe_doc(warehouses.get(b.get("warehouse_id"), {}))
        rows.append({**b, "warehouse_name": warehouse.get("name"), "warehouse_city": warehouse.get("city"),
                     "owner_entity_name": _ent_name(b.get("owner_entity_id"))})

    # Matriks (Owner × Gudang × Lot) — KN_15 §8 (K1)
    matrix: Dict[tuple, Dict[str, Any]] = {}
    rolls = []
    for r in rolls_raw:
        r = safe_doc(r)
        wh = warehouses.get(r.get("warehouse_id"), {})
        r["warehouse_name"] = wh.get("name", "")
        r["owner_entity_name"] = _ent_name(r.get("owner_entity_id"))
        rolls.append(r)
        key = (r.get("owner_entity_id"), r.get("warehouse_id"), r.get("lot"))
        cell = matrix.setdefault(key, {
            "owner_entity_id": r.get("owner_entity_id"), "owner_entity_name": _ent_name(r.get("owner_entity_id")),
            "warehouse_id": r.get("warehouse_id"), "warehouse_name": wh.get("name", ""),
            "warehouse_city": wh.get("city", ""), "lot": r.get("lot"), "grade": r.get("grade"),
            "available_qty": 0.0, "reserved_qty": 0.0, "committed_qty": 0.0, "on_hand_qty": 0.0,
            "roll_count": 0,
        })
        length = float(r.get("length_remaining", 0) or 0)
        status = r.get("status")
        if status == "available":
            cell["available_qty"] += length
        elif status == "reserved":
            cell["reserved_qty"] += length
        elif status == "committed":
            cell["committed_qty"] += length
        if status in ("available", "reserved", "committed", "picked", "packed", "quarantine", "blocked", "damaged"):
            cell["on_hand_qty"] += length
            cell["roll_count"] += 1
    matrix_list = []
    for cell in matrix.values():
        for k in ("available_qty", "reserved_qty", "committed_qty", "on_hand_qty"):
            cell[k] = round(cell[k], 2)
        matrix_list.append(cell)
    matrix_list.sort(key=lambda c: (c["owner_entity_name"], c["warehouse_name"], c["lot"] or ""))

    return {
        "product": product,
        "balances": rows,
        "ownership_matrix": matrix_list,
        "rolls": rolls,
        "reservations": [safe_doc(r) for r in reservations_raw if r]
    }
