"""Business Entities router (Multi-Entity foundation — Fase 0).

Master entitas legal grup Kain Nusantara (PT/CV). entity_id menjadi lapisan
scope untuk data transaksi (SO/Invoice/PO/Customer). Master katalog & gudang
tetap SHARED lintas-entitas (lihat KN_14 §7).
"""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit, current_user
from core_utils import new_id, now_iso, safe_doc
from schemas import BusinessEntityCreate, GenericPatch
from services import entity_provisioning_service

router = APIRouter(prefix="/api")

ALLOWED_FIELDS = [
    "legal_name", "short_name", "type", "npwp", "address", "city",
    "default_tax_mode", "doc_prefix", "logo_url", "status",
    "currency", "parent_entity_id", "is_group", "coa_template",
    "fiscal_year_start", "incentive_payer", "numbering_scheme",
]


@router.get("/entities")
async def list_entities(request: Request) -> List[Dict[str, Any]]:
    """List entitas — dipakai Entity Switcher, jadi semua user login boleh baca."""
    await current_user(request)
    return await db.business_entities.find({}, {"_id": 0}).sort("created_at", 1).to_list(100)


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str, request: Request) -> Dict[str, Any]:
    await current_user(request)
    entity = safe_doc(await db.business_entities.find_one({"id": entity_id}, {"_id": 0}))
    if not entity:
        raise HTTPException(status_code=404, detail="Entitas tidak ditemukan")
    return entity


@router.post("/entities")
async def create_entity(payload: BusinessEntityCreate, request: Request) -> Dict[str, Any]:
    """F0-F — Provisioning entitas baru siap-pakai (CoA, numbering, config, PKP)."""
    actor = await require_permission(request, "entity", "create")
    try:
        result = await entity_provisioning_service.provision_entity(payload.model_dump(), actor["name"])
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    entity = result["entity"]
    await audit(actor["name"], "entity_provisioned", "business_entity", entity["id"],
                {**entity, "provisioning": result["provisioning"]})
    return {**entity, "provisioning": result["provisioning"]}


@router.patch("/entities/{entity_id}")
async def update_entity(entity_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "entity", "update")
    data = {k: v for k, v in payload.data.items() if k in ALLOWED_FIELDS}
    data["updated_at"] = now_iso()
    entity = await db.business_entities.find_one_and_update(
        {"id": entity_id}, {"$set": data},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Entitas tidak ditemukan")
    await audit(actor["name"], "entity_updated", "business_entity", entity_id, data)
    return entity


@router.delete("/entities/{entity_id}")
async def deactivate_entity(entity_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "entity", "delete")
    entity = await db.business_entities.find_one_and_update(
        {"id": entity_id}, {"$set": {"status": "inactive", "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Entitas tidak ditemukan")
    await audit(actor["name"], "entity_deactivated", "business_entity", entity_id, entity)
    return entity
