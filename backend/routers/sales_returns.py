"""
Sub-fase 1.11 — Returns & Barang Sisa
Router prefix: /api/sales-returns
"""
from fastapi import APIRouter, Request, File, UploadFile, HTTPException, Query
from typing import Dict, Any, Optional
from db import db
from dependencies import require_permission, audit
from core_utils import now_iso, new_id
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access
from schemas import SalesReturnCreate, SalesReturnDecision
from services import return_service, storage_service as storage

router = APIRouter(prefix="/api")


# ─── LIST ────────────────────────────────────────────────────────────────────

@router.get("/sales-returns")
async def list_returns(
    request: Request,
    status: Optional[str] = Query(None),
    order_id: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    return_type: Optional[str] = Query(None),
) -> Dict[str, Any]:
    user = await require_permission(request, "sales_return", "view")
    ctx = await entity_ctx(request)
    q: Dict = {}
    if status:      q["status"]      = status
    if order_id:    q["order_id"]    = order_id
    if return_type: q["return_type"] = return_type
    q = resolve_list_scope("sales_returns", q, ctx, entity_id)

    docs = await db.sales_returns.find(q, sort=[("created_at", -1)]).to_list(500)
    for d in docs:
        d.pop("_id", None)
        d["attachments"] = [a for a in (d.get("attachments") or []) if not a.get("is_deleted")]
    return {"items": docs, "total": len(docs)}


# ─── CREDIT NOTES (F3 — Nota Kredit dari retur, posting GL) ──────────────────

@router.get("/credit-notes")
async def list_credit_notes(
    request: Request,
    customer_id: Optional[str] = Query(None),
    return_id: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    await require_permission(request, "sales_return", "view")
    ctx = await entity_ctx(request)
    q: Dict = {}
    if customer_id: q["customer_id"] = customer_id
    if return_id:   q["return_id"] = return_id
    q = resolve_list_scope("credit_notes", q, ctx, entity_id)
    docs = await db.credit_notes.find(q, sort=[("created_at", -1)]).to_list(500)
    for d in docs:
        d.pop("_id", None)
    total = round(sum(float(d.get("gross_amount", 0) or 0) for d in docs), 2)
    return {"items": docs, "total": len(docs), "total_amount": total}


@router.get("/credit-notes/{cn_id}")
async def get_credit_note(cn_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "sales_return", "view")
    ctx = await entity_ctx(request)
    doc = await db.credit_notes.find_one({"id": cn_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Credit Note tidak ditemukan")
    doc.pop("_id", None)
    assert_entity_access(doc, "credit_notes", ctx)
    return doc


# ─── CREATE ──────────────────────────────────────────────────────────────────

@router.post("/sales-returns")
async def create_return(
    request: Request,
    payload: SalesReturnCreate,
) -> Dict[str, Any]:
    user = await require_permission(request, "sales_return", "create")

    order = await db.sales_orders.find_one({"id": payload.order_id})
    if not order:
        raise HTTPException(status_code=404, detail=f"Pesanan {payload.order_id} tidak ditemukan")

    allowed_statuses = {
        "confirmed", "partially_picked", "picked",
        "partially_shipped", "shipped", "done"
    }
    if order.get("status") not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Return hanya bisa dibuat dari pesanan yang sudah dikonfirmasi. Status: {order.get('status')}"
        )

    entity_id = payload.entity_id or order.get("entity_id", "")
    doc = await return_service.create_return(
        order_id=payload.order_id,
        return_type=payload.return_type,
        items=[item.dict() for item in payload.items],
        notes=payload.notes,
        entity_id=entity_id,
        created_by=user.get("name", user.get("email", "")),
        submit_now=payload.submit_now,
    )
    await audit(user.get("name", ""), "sales_return_created", "sales_return", doc["id"],
                {"number": doc["number"], "order_id": payload.order_id, "type": payload.return_type})
    return doc


# ─── DETAIL ──────────────────────────────────────────────────────────────────

@router.get("/sales-returns/{return_id}")
async def get_return(return_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "sales_return", "view")
    ctx = await entity_ctx(request)
    doc = await db.sales_returns.find_one({"id": return_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Return tidak ditemukan")
    doc.pop("_id", None)
    assert_entity_access(doc, "sales_returns", ctx)
    doc["attachments"] = [a for a in (doc.get("attachments") or []) if not a.get("is_deleted")]
    return doc


# ─── SUBMIT (draft → pending_approval) ──────────────────────────────────────

@router.post("/sales-returns/{return_id}/submit")
async def submit_return(return_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "sales_return", "update")
    doc = await db.sales_returns.find_one({"id": return_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Return tidak ditemukan")
    if doc["status"] != "draft":
        raise HTTPException(status_code=400, detail="Hanya draft yang bisa disubmit")
    await db.sales_returns.update_one(
        {"id": return_id},
        {"$set": {"status": "pending_approval",
                  "submitted_at": now_iso(),
                  "submitted_by": user.get("name", user.get("email", "")),
                  "updated_at": now_iso()}}
    )
    doc = await db.sales_returns.find_one({"id": return_id})
    doc.pop("_id", None)
    await audit(user.get("name", ""), "sales_return_submitted", "sales_return", return_id, {})
    return doc


# ─── APPROVE ─────────────────────────────────────────────────────────────────

@router.post("/sales-returns/{return_id}/approve")
async def approve_return(
    return_id: str,
    request: Request,
    payload: SalesReturnDecision = SalesReturnDecision(),
) -> Dict[str, Any]:
    user = await require_permission(request, "sales_return", "approve")
    doc = await return_service.approve_and_adjust_stock(
        return_id=return_id,
        approved_by=user.get("name", user.get("email", "")),
        notes=payload.notes,
    )
    await audit(user.get("name", ""), "sales_return_approved", "sales_return", return_id,
                {"notes": payload.notes})
    return doc


# ─── REJECT ──────────────────────────────────────────────────────────────────

@router.post("/sales-returns/{return_id}/reject")
async def reject_return(
    return_id: str,
    request: Request,
    payload: SalesReturnDecision = SalesReturnDecision(),
) -> Dict[str, Any]:
    user = await require_permission(request, "sales_return", "reject")
    doc = await return_service.reject_return(
        return_id=return_id,
        rejected_by=user.get("name", user.get("email", "")),
        reason=payload.notes,
    )
    await audit(user.get("name", ""), "sales_return_rejected", "sales_return", return_id,
                {"reason": payload.notes})
    return doc


# ─── ATTACHMENTS ─────────────────────────────────────────────────────────────

@router.post("/sales-returns/{return_id}/attachments")
async def upload_attachment(
    return_id: str,
    request: Request,
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    user = await require_permission(request, "sales_return", "update")
    doc = await db.sales_returns.find_one({"id": return_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Return tidak ditemukan")
    if doc["status"] == "approved":
        raise HTTPException(status_code=400, detail="Return sudah approved, tidak bisa tambah lampiran")

    data = await file.read()
    content_type = storage.validate_upload(file.filename, file.content_type, len(data))
    path = f"sales_returns/{return_id}/{new_id('att')}-{file.filename}"
    result = await storage.put_object(path, data, content_type)

    att = {
        "id":          new_id("att"),
        "filename":    file.filename,
        "url":         result.get("url", ""),
        "path":        path,
        "size":        len(data),
        "content_type":content_type,
        "uploaded_by": user.get("name", ""),
        "uploaded_at": now_iso(),
        "is_deleted":  False,
    }
    await db.sales_returns.update_one(
        {"id": return_id},
        {"$push": {"attachments": att}, "$set": {"updated_at": now_iso()}}
    )
    await audit(user.get("name", ""), "sales_return_attachment_added", "sales_return", return_id,
                {"filename": file.filename})
    return att


@router.get("/sales-returns/{return_id}/attachments/{att_id}/download")
async def download_attachment(return_id: str, att_id: str, request: Request):
    await require_permission(request, "sales_return", "view")
    doc = await db.sales_returns.find_one({"id": return_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Return tidak ditemukan")
    att = next((a for a in (doc.get("attachments") or []) if a.get("id") == att_id and not a.get("is_deleted")), None)
    if not att:
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    from fastapi.responses import Response
    obj = await storage.get_object(att["path"])
    return Response(
        content=obj["data"],
        media_type=att.get("content_type", "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{att["filename"]}"'}
    )


@router.delete("/sales-returns/{return_id}/attachments/{att_id}")
async def delete_attachment(return_id: str, att_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "sales_return", "update")
    await db.sales_returns.update_one(
        {"id": return_id, "attachments.id": att_id},
        {"$set": {"attachments.$.is_deleted": True, "updated_at": now_iso()}}
    )
    await audit(user.get("name", ""), "sales_return_attachment_deleted", "sales_return", return_id,
                {"attachment_id": att_id})
    return {"ok": True}
