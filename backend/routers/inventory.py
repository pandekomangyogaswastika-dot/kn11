"""Inventory router: balances (owner-aware), rolls (SSOT), movements, history."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID
from entity_scope import entity_ctx, resolve_list_scope
from schemas import RollPayload
from services.roll_service import rebuild_balance
from services.fulfillment_service import status_board as _status_board

router = APIRouter(prefix="/api")


async def _entity_map() -> Dict[str, Dict[str, Any]]:
    return {e["id"]: e for e in await db.business_entities.find({}, {"_id": 0}).to_list(100)}


@router.get("/inventory/status-board")
async def inventory_status_board(
    request: Request,
    product_id: Optional[str] = None,
    owner_entity_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Sub-fase 1.4 — Inventory Status Board.

    Ringkasan per produk: on_hand / available / reserved / incoming / ATP,
    di-breakdown per entitas pemilik & gudang, plus indikator peluang
    pemenuhan lintas-entitas (inter-company)."""
    await require_permission(request, "product", "view")
    return await _status_board(product_id=product_id, owner_entity_id=owner_entity_id)


@router.get("/inventory/balances")
async def list_balances(request: Request, owner_entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
    await require_permission(request, "product", "view")
    ctx = await entity_ctx(request)
    query: Dict[str, Any] = resolve_list_scope("inventory_balances", {}, ctx, owner_entity_id)
    balances = await db.inventory_balances.find(query, {"_id": 0}).to_list(2000)
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    entities = await _entity_map()
    result = []
    for b in balances:
        b["warehouse_name"] = warehouses.get(b["warehouse_id"], {}).get("name", "")
        b["warehouse_city"] = warehouses.get(b["warehouse_id"], {}).get("city", "")
        p = products.get(b["product_id"], {})
        b["sku"] = p.get("sku", "")
        b["product_name"] = p.get("name", "")
        b["base_unit"] = p.get("base_unit", "meter")  # F2 (UoM SSOT) — untuk tampilan "X roll / Y base_unit"
        owner = b.get("owner_entity_id", DEFAULT_ENTITY_ID)
        b["owner_entity_id"] = owner
        b["owner_entity_name"] = entities.get(owner, {}).get("short_name") or entities.get(owner, {}).get("legal_name", owner)
        result.append(b)
    return result


@router.get("/inventory/rolls")
async def list_rolls(
    request: Request,
    product_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    owner_entity_id: Optional[str] = None,
    status: Optional[str] = None,
    lot: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daftar roll fisik (SSOT) dengan filter owner/lot/status/warehouse."""
    await require_permission(request, "product", "view")
    ctx = await entity_ctx(request)
    query: Dict[str, Any] = {}
    if product_id:
        query["product_id"] = product_id
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    if status:
        query["status"] = status
    if lot:
        query["lot"] = lot
    query = resolve_list_scope("inventory_rolls", query, ctx, owner_entity_id)
    rolls = await db.inventory_rolls.find(query, {"_id": 0}).sort("created_at", -1).to_list(5000)
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    entities = await _entity_map()
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


@router.get("/inventory/movements")
async def list_movements(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "product", "view")
    ctx = await entity_ctx(request)
    query = resolve_list_scope("inventory_movements", {}, ctx)
    return await db.inventory_movements.find(query, {"_id": 0}).sort("timestamp", -1).to_list(500)


@router.post("/inventory/initial-stock")
async def add_initial_stock(payload: RollPayload, request: Request) -> Dict[str, Any]:
    """Tambah stok awal sebagai ROLL fisik (KN_15) + movement, lalu rebuild balance."""
    actor = await require_permission(request, "product", "create")
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity harus > 0")
    owner = payload.owner_entity_id or DEFAULT_ENTITY_ID
    if not await db.products.find_one({"id": payload.product_id}, {"_id": 0}):
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    if not await db.warehouses.find_one({"id": payload.warehouse_id}, {"_id": 0}):
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    lot = payload.lot or "LOT-MANUAL"
    roll = {
        "id": new_id("roll"), "product_id": payload.product_id, "owner_entity_id": owner,
        "ownership_type": payload.ownership_type, "consignor_ref": None,
        "warehouse_id": payload.warehouse_id, "bin_id": payload.bin_id or None,
        "lot": lot, "batch": payload.batch or lot.replace("LOT", "BATCH"),
        "dye_lot": getattr(payload, "dye_lot", "") or lot, "defects": [],
        "roll_no": payload.roll_no or f"RL-{new_id('x')[2:8].upper()}",
        "length_initial": float(payload.quantity), "length_remaining": float(payload.quantity),
        "unit": payload.unit, "grade": payload.grade, "status": "available",
        "tracking_mode": payload.tracking_mode, "earmarked_for": None,
        "location_type": "warehouse_bin", "reserved_ref": None,
        "unit_cost": None, "base_unit_cost": None, "landed_cost_total": 0.0, "landed_cost_refs": [],
        "acquired": {"via": "initial", "ref_id": "manual", "date": now_iso()},
        "rfid_tag_id": None, "is_remnant": False,
        "created_at": now_iso(), "updated_at": now_iso(),
        "created_by": actor.get("id", "system"), "created_by_name": actor.get("name", "System"),
    }
    await db.inventory_rolls.insert_one(roll)
    await db.inventory_movements.insert_one({
        "id": new_id("mov"), "product_id": payload.product_id, "warehouse_id": payload.warehouse_id,
        "owner_entity_id": owner, "movement_type": "initial_stock", "quantity": float(payload.quantity),
        "unit": payload.unit, "batch": roll["batch"], "lot": lot, "roll_id": roll["id"],
        "source_document": "initial_stock", "timestamp": now_iso(),
    })
    await rebuild_balance(payload.product_id, payload.warehouse_id, owner)
    await audit(actor["name"], "initial_stock_added", "inventory", payload.product_id,
                {"roll_id": roll["id"], "qty": payload.quantity, "owner": owner, "lot": lot})
    return {"message": "Stok awal (roll) berhasil ditambahkan", "roll_id": roll["id"], "lot": lot}


@router.get("/history/{product_id}")
async def product_history(product_id: str, request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "product", "view")
    movements = await db.inventory_movements.find(
        {"product_id": product_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(200)
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    for m in movements:
        m["warehouse_name"] = warehouses.get(m.get("warehouse_id", ""), {}).get("name", "")
    return movements
