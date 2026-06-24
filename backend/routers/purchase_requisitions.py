"""Depth #2 — Purchase Requisition (PR) router + Reorder/Replenishment.

Hulu procurement: PR → approval → konversi ke PO. Plus saran reorder.
Permission module: 'purchase_requisition'.
"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, HTTPException, Query
from db import db
from dependencies import require_permission, current_user, audit
from core_utils import safe_doc
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access
from schemas import (
    PurchaseRequisitionCreate, PurchaseRequisitionDecision, PurchaseRequisitionConvert,
)
from services import purchase_requisition_service as svc

router = APIRouter(prefix="/api")


@router.get("/purchase-requisitions")
async def list_requisitions(
    request: Request,
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    await require_permission(request, "purchase_requisition", "view")
    ctx = await entity_ctx(request)
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if source:
        q["source"] = source
    q = resolve_list_scope("purchase_requisitions", q, ctx, entity_id)
    docs = await db.purchase_requisitions.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    # ringkas stat per status
    by_status: Dict[str, int] = {}
    for d in docs:
        by_status[d.get("status", "?")] = by_status.get(d.get("status", "?"), 0) + 1
    return {"items": docs, "total": len(docs), "by_status": by_status}


@router.get("/purchase-requisitions/reorder-suggestions")
async def reorder_suggestions(request: Request, entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Depth #2b — saran replenishment berbasis reorder_point produk."""
    await require_permission(request, "purchase_requisition", "view")
    return await svc.reorder_suggestions(entity_id=entity_id)


@router.post("/purchase-requisitions")
async def create_requisition(payload: PurchaseRequisitionCreate, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "purchase_requisition", "create")
    if not payload.items:
        raise HTTPException(status_code=400, detail="Minimal satu item kebutuhan")
    try:
        doc = await svc.create_requisition(payload, created_by=user.get("name", "Admin"),
                                           created_by_id=user.get("id", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "pr_created", "purchase_requisition", doc["id"],
                {"number": doc["number"], "total": doc["total_est_amount"], "source": doc["source"]})
    return doc


@router.get("/purchase-requisitions/{pr_id}")
async def get_requisition(pr_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "purchase_requisition", "view")
    ctx = await entity_ctx(request)
    doc = safe_doc(await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0}))
    if not doc:
        raise HTTPException(status_code=404, detail="PR tidak ditemukan")
    assert_entity_access(doc, "purchase_requisitions", ctx)
    return doc


@router.post("/purchase-requisitions/{pr_id}/submit")
async def submit_requisition(pr_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "purchase_requisition", "update")
    try:
        doc = await svc.submit_requisition(pr_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "pr_submitted", "purchase_requisition", pr_id, {"status": doc["status"]})
    return doc


@router.post("/purchase-requisitions/{pr_id}/approve")
async def approve_requisition(pr_id: str, request: Request,
                              payload: PurchaseRequisitionDecision = PurchaseRequisitionDecision()) -> Dict[str, Any]:
    await require_permission(request, "purchase_requisition", "approve")
    actor = await current_user(request)
    try:
        doc = await svc.approve_requisition(pr_id, actor, notes=payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "pr_approved", "purchase_requisition", pr_id, {"number": doc["number"]})
    return doc


@router.post("/purchase-requisitions/{pr_id}/reject")
async def reject_requisition(pr_id: str, request: Request,
                             payload: PurchaseRequisitionDecision = PurchaseRequisitionDecision()) -> Dict[str, Any]:
    await require_permission(request, "purchase_requisition", "reject")
    actor = await current_user(request)
    try:
        doc = await svc.reject_requisition(pr_id, actor, reason=payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "pr_rejected", "purchase_requisition", pr_id, {"reason": payload.notes})
    return doc


@router.post("/purchase-requisitions/{pr_id}/cancel")
async def cancel_requisition(pr_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "purchase_requisition", "update")
    try:
        doc = await svc.cancel_requisition(pr_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "pr_cancelled", "purchase_requisition", pr_id, {})
    return doc


@router.post("/purchase-requisitions/{pr_id}/convert-to-po")
async def convert_to_po(pr_id: str, payload: PurchaseRequisitionConvert, request: Request) -> Dict[str, Any]:
    await require_permission(request, "purchase_order", "create")
    actor = await current_user(request)
    try:
        result = await svc.convert_to_po(
            pr_id, supplier_id=payload.supplier_id, actor=actor,
            warehouse_id=payload.warehouse_id, expected_delivery_date=payload.expected_delivery_date,
            notes=payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "pr_converted_to_po", "purchase_requisition", pr_id,
                {"po_number": result["po"]["po_number"]})
    return result
