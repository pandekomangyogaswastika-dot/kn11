"""Incentive Rates router (EPIC4) — matriks rate insentif (entity × category).

Akses: admin + manager (require_role manager → admin auto). Respons ARRAY/OBJEK
telanjang (kontrak KN3). PATCH pakai GenericPatch (`{data:{...}}`).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from db import db
from dependencies import require_role, audit
from core_utils import new_id, now_iso, safe_doc

router = APIRouter(prefix="/api")


class RatePayload(BaseModel):
    entity_id: str = "all"
    category: str
    incentive_unit: str = "meter"
    per_unit_amount: float = 0.0
    discount_threshold_type: str = "pct"      # pct | rp_per_unit
    discount_threshold: float = 10.0
    discount_mechanic: str = "tier_factor"    # tier_factor | potong_rp | cutoff
    discount_factor: float = 0.5
    discount_potong_rp: float = 0.0
    margin_cap_pct: float = 50.0
    status: str = "active"


class GenericPatch(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)


_FIELDS = ["entity_id", "category", "incentive_unit", "per_unit_amount",
           "discount_threshold_type", "discount_threshold", "discount_mechanic",
           "discount_factor", "discount_potong_rp", "margin_cap_pct", "status"]


@router.get("/incentive-rates")
async def list_rates(request: Request, entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
    await require_role(request, ["manager"])
    query: Dict[str, Any] = {}
    if entity_id:
        query["entity_id"] = entity_id
    rows = await db.incentive_rates.find(query, {"_id": 0}).to_list(1000)
    rows.sort(key=lambda r: (r.get("entity_id", ""), r.get("category", "")))
    return [safe_doc(r) for r in rows]


@router.post("/incentive-rates")
async def create_rate(payload: RatePayload, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["manager"])
    if not (payload.category or "").strip():
        raise HTTPException(status_code=400, detail="Kategori wajib diisi")
    dup = await db.incentive_rates.find_one(
        {"entity_id": payload.entity_id, "category": payload.category}, {"_id": 0})
    if dup:
        raise HTTPException(status_code=409, detail="Rate untuk entitas+kategori ini sudah ada")
    doc = payload.model_dump()
    doc.update({"id": new_id("irate"), "created_at": now_iso(), "updated_at": now_iso()})
    await db.incentive_rates.insert_one(doc)
    await audit(actor["name"], "incentive_rate_created", "incentive_rate", doc["id"], doc)
    return safe_doc(doc)


@router.patch("/incentive-rates/{rate_id}")
async def update_rate(rate_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["manager"])
    data = {k: v for k, v in payload.data.items() if k in _FIELDS}
    if not data:
        raise HTTPException(status_code=400, detail="Tidak ada field valid untuk diupdate")
    data["updated_at"] = now_iso()
    updated = await db.incentive_rates.find_one_and_update(
        {"id": rate_id}, {"$set": data}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(status_code=404, detail="Rate tidak ditemukan")
    await audit(actor["name"], "incentive_rate_updated", "incentive_rate", rate_id, updated)
    return safe_doc(updated)


@router.delete("/incentive-rates/{rate_id}")
async def delete_rate(rate_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["manager"])
    existing = await db.incentive_rates.find_one({"id": rate_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Rate tidak ditemukan")
    await db.incentive_rates.delete_one({"id": rate_id})
    await audit(actor["name"], "incentive_rate_deleted", "incentive_rate", rate_id, existing)
    return {"id": rate_id, "deleted": True}
