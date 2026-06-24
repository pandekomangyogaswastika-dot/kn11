"""Settings router (Fase 1A) — Configuration Foundation.

Mengelola pengaturan global/per-entitas, term pembayaran, dan matriks approval —
semua CONFIGURABLE (tidak hardcode). Konsumsi engine ada di services/config_service.py.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, current_user, audit
from core_utils import new_id, now_iso, safe_doc
from schemas import SettingsUpdate, PaymentTermPayload, ApprovalRulePayload, GenericPatch
from services.config_service import (
    get_global_settings, get_effective_settings, compute_tax, evaluate_approval, GLOBAL_SCOPE,
)

router = APIRouter(prefix="/api")
SETTINGS_SECTIONS = ["tax", "finance", "sales", "inventory", "allocation", "purchasing", "commission"]


# ── Settings (global + per-entity override) ─────────────────────────────────

@router.get("/settings")
async def read_settings(request: Request) -> Dict[str, Any]:
    await current_user(request)
    return await get_global_settings()


@router.get("/settings/effective")
async def read_effective_settings(request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    await current_user(request)
    return await get_effective_settings(entity_id)


@router.put("/settings")
async def update_settings(payload: SettingsUpdate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "entity", "update")
    scope = payload.scope or GLOBAL_SCOPE
    data: Dict[str, Any] = {"updated_at": now_iso()}
    for sec in SETTINGS_SECTIONS:
        val = getattr(payload, sec, None)
        if val is not None:
            data[sec] = val
    existing = await db.system_settings.find_one({"scope": scope}, {"_id": 0})
    if existing:
        updated = await db.system_settings.find_one_and_update(
            {"scope": scope}, {"$set": data},
            projection={"_id": 0}, return_document=ReturnDocument.AFTER,
        )
    else:
        doc = {"id": new_id("set"), "scope": scope, "created_at": now_iso(), **data}
        await db.system_settings.insert_one(doc)
        updated = safe_doc(doc)
    await audit(actor["name"], "settings_updated", "system_settings", scope, data)
    return updated


# ── Tax & Approval helper endpoints (dipakai FE Sales nanti) ─────────────────

@router.get("/settings/compute-tax")
async def compute_tax_endpoint(request: Request, subtotal: float, entity_id: Optional[str] = None) -> Dict[str, Any]:
    await current_user(request)
    return await compute_tax(subtotal, entity_id)


@router.get("/settings/evaluate-approval")
async def evaluate_approval_endpoint(request: Request, doc_type: str, amount: float,
                                     entity_id: Optional[str] = None) -> Dict[str, Any]:
    await current_user(request)
    return await evaluate_approval(doc_type, amount, entity_id)


# ── Payment Terms CRUD ───────────────────────────────────────────────────────

@router.get("/payment-terms")
async def list_payment_terms(request: Request) -> List[Dict[str, Any]]:
    await current_user(request)
    return await db.payment_terms.find({}, {"_id": 0}).sort("sort", 1).to_list(200)


@router.post("/payment-terms")
async def create_payment_term(payload: PaymentTermPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "entity", "create")
    if await db.payment_terms.find_one({"code": payload.code}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="Kode term sudah digunakan")
    doc = {"id": new_id("pterm"), **payload.model_dump(),
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.payment_terms.insert_one(doc)
    await audit(actor["name"], "payment_term_created", "payment_terms", doc["id"], doc)
    return safe_doc(doc)


@router.patch("/payment-terms/{term_id}")
async def update_payment_term(term_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "entity", "update")
    data = dict(payload.data); data["updated_at"] = now_iso()
    doc = await db.payment_terms.find_one_and_update(
        {"id": term_id}, {"$set": data}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(status_code=404, detail="Term tidak ditemukan")
    await audit(actor["name"], "payment_term_updated", "payment_terms", term_id, data)
    return doc


@router.delete("/payment-terms/{term_id}")
async def delete_payment_term(term_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "entity", "delete")
    doc = await db.payment_terms.find_one_and_update(
        {"id": term_id}, {"$set": {"active": False, "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(status_code=404, detail="Term tidak ditemukan")
    await audit(actor["name"], "payment_term_deactivated", "payment_terms", term_id, {})
    return doc

# NOTE: Approval Rules CRUD telah dipindah ke routers/approval_rules.py
# Jangan duplikasi di sini — RC-11 (service contract drift + G2 duplicate route)
