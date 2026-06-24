"""UOMs router: CRUD unit of measure."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc
from schemas import GenericPatch, UOMPayload

router = APIRouter(prefix="/api")


@router.get("/uoms")
async def list_uoms() -> List[Dict[str, Any]]:
    return await db.uoms.find({}, {"_id": 0}).sort("code", 1).to_list(100)


@router.post("/uoms")
async def create_uom(payload: UOMPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "uom", "create")
    if await db.uoms.find_one({"code": payload.code}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="Kode UOM sudah ada")
    uom = {**payload.model_dump(), "id": new_id("uom"), "status": "active", "created_at": now_iso()}
    await db.uoms.insert_one(uom)
    await audit(actor["name"], "uom_created", "uom", uom["id"], uom)
    return safe_doc(uom)


@router.patch("/uoms/{uom_id}")
async def update_uom(uom_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "uom", "update")
    data = {k: v for k, v in payload.data.items() if k in ["code", "name", "base_type", "precision", "status", "factor_to_base"]}
    data["updated_at"] = now_iso()
    uom = await db.uoms.find_one_and_update(
        {"id": uom_id}, {"$set": data},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not uom:
        raise HTTPException(status_code=404, detail="UOM tidak ditemukan")
    await audit(actor["name"], "uom_updated", "uom", uom_id, uom)
    return uom


@router.delete("/uoms/{uom_id}")
async def delete_uom(uom_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "uom", "delete")
    uom = await db.uoms.find_one_and_update(
        {"id": uom_id},
        {"$set": {"status": "inactive", "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not uom:
        raise HTTPException(status_code=404, detail="UOM tidak ditemukan")
    await audit(actor["name"], "uom_deactivated", "uom", uom_id, uom)
    return uom
