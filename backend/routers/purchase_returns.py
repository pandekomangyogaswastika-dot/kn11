"""Depth #1 — Retur Beli (Purchase Return / Nota Debit) router."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, HTTPException, Query
from db import db
from dependencies import require_permission, audit
from core_utils import safe_doc
from schemas import PurchaseReturnCreate, PurchaseReturnDecision
from services import purchase_return_service as svc

router = APIRouter(prefix="/api")


@router.get("/purchase-returns")
async def list_purchase_returns(
    request: Request,
    status: Optional[str] = Query(None),
    supplier_id: Optional[str] = Query(None),
    po_id: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    await require_permission(request, "purchase_return", "view")
    q: Dict[str, Any] = {}
    if status:      q["status"] = status
    if supplier_id: q["supplier_id"] = supplier_id
    if po_id:       q["po_id"] = po_id
    if entity_id and entity_id != "all": q["entity_id"] = entity_id
    docs = await db.purchase_returns.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"items": docs, "total": len(docs)}


@router.post("/purchase-returns")
async def create_purchase_return(payload: PurchaseReturnCreate, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "purchase_return", "create")
    if not payload.items:
        raise HTTPException(status_code=400, detail="Minimal satu item retur")
    try:
        doc = await svc.create_purchase_return(payload, created_by=user.get("name", "Admin"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "purchase_return_created", "purchase_return", doc["id"],
                {"number": doc["number"], "supplier": doc["supplier_name"], "total": doc["total_amount"]})
    return doc


@router.get("/purchase-returns/{return_id}")
async def get_purchase_return(return_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "purchase_return", "view")
    doc = safe_doc(await db.purchase_returns.find_one({"id": return_id}, {"_id": 0}))
    if not doc:
        raise HTTPException(status_code=404, detail="Retur tidak ditemukan")
    return doc


@router.post("/purchase-returns/{return_id}/submit")
async def submit_purchase_return(return_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "purchase_return", "update")
    try:
        doc = await svc.submit_purchase_return(return_id, submitted_by=user.get("name", user.get("email", "")))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "purchase_return_submitted", "purchase_return", return_id, {})
    return doc


@router.post("/purchase-returns/{return_id}/approve")
async def approve_purchase_return(return_id: str, request: Request,
                                  payload: PurchaseReturnDecision = PurchaseReturnDecision()) -> Dict[str, Any]:
    user = await require_permission(request, "purchase_return", "approve")
    try:
        doc = await svc.approve_and_adjust_stock(return_id, approved_by=user.get("name", "Admin"), notes=payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "purchase_return_approved", "purchase_return", return_id,
                {"debit_note": doc.get("debit_note_number")})
    return doc


@router.post("/purchase-returns/{return_id}/reject")
async def reject_purchase_return(return_id: str, request: Request,
                                 payload: PurchaseReturnDecision = PurchaseReturnDecision()) -> Dict[str, Any]:
    user = await require_permission(request, "purchase_return", "reject")
    try:
        doc = await svc.reject_purchase_return(return_id, rejected_by=user.get("name", "Admin"), reason=payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "purchase_return_rejected", "purchase_return", return_id, {"reason": payload.notes})
    return doc
