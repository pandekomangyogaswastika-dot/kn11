"""Warehouses router: CRUD warehouses + geolocation support."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc
from schemas import GenericPatch, WarehousePayload

router = APIRouter(prefix="/api")


@router.get("/warehouses")
async def list_warehouses() -> List[Dict[str, Any]]:
    return await db.warehouses.find({}, {"_id": 0}).to_list(100)


@router.post("/warehouses")
async def create_warehouse(payload: WarehousePayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "create")
    if await db.warehouses.find_one({"code": payload.code}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="Kode gudang sudah digunakan")
    warehouse_id = new_id("wh")
    zone_id = new_id("zone")
    rack_id = new_id("rack")
    bin_id = new_id("bin")
    warehouse = {
        "id": warehouse_id,
        "code": payload.code,
        "name": payload.name,
        "city": payload.city,
        "lat": payload.lat,
        "lng": payload.lng,
        "zones": [{"id": zone_id, "name": "Zone A", "racks": [{"id": rack_id, "name": "Rack A1",
                    "bins": [{"id": bin_id, "code": payload.bin_code, "capacity": payload.bin_capacity}]}]}],
        "active": True,
        "created_at": now_iso(),
    }
    await db.warehouses.insert_one(warehouse)
    await audit(actor["name"], "warehouse_created", "warehouse", warehouse_id, warehouse)
    return safe_doc(warehouse)


@router.patch("/warehouses/{warehouse_id}")
async def update_warehouse(warehouse_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "update")
    allowed = ["code", "name", "city", "zones", "active", "lat", "lng"]
    data = {k: v for k, v in payload.data.items() if k in allowed}
    if data.get("code"):
        duplicate = await db.warehouses.find_one(
            {"code": data["code"], "id": {"$ne": warehouse_id}}, {"_id": 0}
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Kode gudang sudah digunakan")
    data["updated_at"] = now_iso()
    warehouse = await db.warehouses.find_one_and_update(
        {"id": warehouse_id}, {"$set": data},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not warehouse:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    await audit(actor["name"], "warehouse_updated", "warehouse", warehouse_id, warehouse)
    return warehouse


@router.delete("/warehouses/{warehouse_id}")
async def delete_warehouse(warehouse_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "delete")
    warehouse = await db.warehouses.find_one_and_update(
        {"id": warehouse_id},
        {"$set": {"active": False, "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not warehouse:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    await audit(actor["name"], "warehouse_deactivated", "warehouse", warehouse_id, warehouse)
    return warehouse
