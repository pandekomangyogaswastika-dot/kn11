"""Price Approvals router (Sub-fase 1.7) — Special Price / Approval Harga.

Alur: Sales mengajukan harga khusus (nego) per customer+product → upload bukti
(opsional) → manager/admin approve/reject. Harga yang DISETUJUI & masih berlaku
dapat dipakai saat membuat SO (override harga normal). Invarian akuntansi tetap:
item.subtotal = price × quantity (price = harga khusus yang disetujui).

Koleksi: price_approvals (prefix pra_) — terdaftar L0 di ENTITY_REGISTRY.
Kontrak respons: list = ARRAY langsung, detail = objek langsung (tanpa envelope).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Query, Header
from fastapi.responses import Response
from pymongo import ReturnDocument

from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access
from schemas import PriceApprovalCreate, PriceApprovalDecision, GenericPatch
from services import storage_service as storage

router = APIRouter(prefix="/api")

EDITABLE_STATUSES = {"draft", "pending"}
DECIDABLE_STATUSES = {"pending"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _norm_until(value: str) -> str:
    """Normalisasi valid_until: 'YYYY-MM-DD' → akhir hari UTC agar tak dianggap
    kadaluarsa di hari yang sama. Kosong → '' (tanpa kadaluarsa)."""
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) == 10 and v.count("-") == 2:
        return f"{v}T23:59:59+00:00"
    return v


async def _resolve_entity(payload_entity: str, customer: Dict[str, Any]) -> str:
    eid = (payload_entity or "").strip()
    if eid:
        return eid
    return customer.get("entity_id") or DEFAULT_ENTITY_ID


def _is_active_approval(r: Dict[str, Any], now: str) -> bool:
    if r.get("status") != "approved":
        return False
    vf = r.get("valid_from") or ""
    vu = r.get("valid_until") or ""
    if vf and vf > now:
        return False
    if vu and vu < now:
        return False
    return True


def _decorate(r: Dict[str, Any]) -> Dict[str, Any]:
    """Tambah field turunan untuk FE: discount_percent & is_expired (read-time)."""
    if not r:
        return r
    normal = float(r.get("normal_price", 0) or 0)
    req = float(r.get("requested_price", 0) or 0)
    r["discount_percent"] = round((normal - req) / normal * 100, 2) if normal > 0 else 0.0
    r["savings_per_unit"] = round(normal - req, 2)
    now = now_iso()
    vu = r.get("valid_until") or ""
    r["is_expired"] = bool(r.get("status") == "approved" and vu and vu < now)
    # sembunyikan attachment yang sudah dihapus
    r["attachments"] = [a for a in (r.get("attachments") or []) if not a.get("is_deleted")]
    return r


async def get_effective_special_price(
    entity_id: str, customer_id: str, product_id: str,
    quantity: Optional[float] = None, approval_id: str = "",
) -> Optional[Dict[str, Any]]:
    """Cari price_approval DISETUJUI & berlaku untuk (entity, customer, product).
    Dipakai oleh sales_orders saat membuat SO. None bila tidak ada/expired/qty<min."""
    q: Dict[str, Any] = {"customer_id": customer_id, "product_id": product_id, "status": "approved"}
    if entity_id:
        q["entity_id"] = entity_id
    if approval_id:
        q["id"] = approval_id
    rows = await db.price_approvals.find(q, {"_id": 0}).sort("decided_at", -1).to_list(50)
    now = now_iso()
    for r in rows:
        if not _is_active_approval(r, now):
            continue
        if quantity is not None and float(quantity) < float(r.get("min_quantity", 0) or 0):
            continue
        return r
    return None


async def _get_or_404(approval_id: str) -> Dict[str, Any]:
    doc = safe_doc(await db.price_approvals.find_one({"id": approval_id}, {"_id": 0}))
    if not doc:
        raise HTTPException(status_code=404, detail="Pengajuan harga tidak ditemukan")
    return doc


def _ensure_owner_or_privileged(doc: Dict[str, Any], user: Dict[str, Any]) -> None:
    role = user.get("role")
    if role in ("admin", "manager"):
        return
    if doc.get("requested_by") != user.get("id"):
        raise HTTPException(status_code=403, detail="Anda hanya dapat mengelola pengajuan Anda sendiri")


# ─── List & lookup (specific routes BEFORE /{id}) ────────────────────────────

@router.get("/price-approvals")
async def list_price_approvals(
    request: Request, status: str = None, customer_id: str = None,
    product_id: str = None, entity_id: str = None,
) -> List[Dict[str, Any]]:
    user = await require_permission(request, "price_approval", "view")
    ctx = await entity_ctx(request)
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if customer_id:
        query["customer_id"] = customer_id
    if product_id:
        query["product_id"] = product_id
    query = resolve_list_scope("price_approvals", query, ctx, entity_id)
    # Row-level: sales hanya melihat pengajuannya sendiri
    if user.get("role") == "sales":
        query["requested_by"] = user.get("id")
    rows = await db.price_approvals.find(query, {"_id": 0}).sort("created_at", -1).to_list(300)
    return [_decorate(safe_doc(r)) for r in rows]


@router.get("/price-approvals/effective")
async def effective_price(
    request: Request, customer_id: str = Query(...), product_id: str = Query(...),
    entity_id: str = "", quantity: float = None,
) -> Dict[str, Any]:
    """Harga khusus efektif (disetujui & berlaku) untuk POS. Kembalikan objek
    {has_special, ...} — selalu objek (bukan 404) agar mudah dikonsumsi FE."""
    await require_permission(request, "price_approval", "view")
    eid = (entity_id or "").strip()
    if not eid:
        cust = await db.customers.find_one({"id": customer_id}, {"_id": 0, "entity_id": 1})
        eid = (cust or {}).get("entity_id") or DEFAULT_ENTITY_ID
    appr = await get_effective_special_price(eid, customer_id, product_id, quantity)
    if not appr:
        return {"has_special": False}
    return {
        "has_special": True,
        "price_approval_id": appr["id"],
        "requested_price": float(appr["requested_price"]),
        "normal_price": float(appr.get("normal_price", 0) or 0),
        "min_quantity": float(appr.get("min_quantity", 0) or 0),
        "valid_until": appr.get("valid_until", ""),
    }


@router.get("/price-approvals/stats/summary")
async def price_approval_stats(request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "price_approval", "view")
    base: Dict[str, Any] = {}
    if user.get("role") == "sales":
        base["requested_by"] = user.get("id")
    pipeline = [{"$match": base}] if base else []
    pipeline.append({"$group": {"_id": "$status", "count": {"$sum": 1}}})
    rows = await db.price_approvals.aggregate(pipeline).to_list(50)
    by_status = {r["_id"]: r["count"] for r in rows}
    return {
        "by_status": by_status,
        "pending": by_status.get("pending", 0),
        "total": sum(by_status.values()),
    }


# ─── Create ──────────────────────────────────────────────────────────────────

@router.post("/price-approvals")
async def create_price_approval(payload: PriceApprovalCreate, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "price_approval", "create")
    customer = safe_doc(await db.customers.find_one({"id": payload.customer_id}, {"_id": 0}))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    product = safe_doc(await db.products.find_one({"id": payload.product_id}, {"_id": 0}))
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    req_price = round(float(payload.requested_price or 0), 2)
    if req_price <= 0:
        raise HTTPException(status_code=400, detail="Harga khusus harus lebih dari 0")
    entity_id = await _resolve_entity(payload.entity_id, customer)
    status = "pending" if payload.submit_now else "draft"
    doc = {
        "id": new_id("pra"),
        "entity_id": entity_id,
        "customer_id": customer["id"], "customer_name": customer.get("name", ""),
        "product_id": product["id"], "sku": product.get("sku", ""),
        "product_name": product.get("name", ""),
        "normal_price": round(float(product.get("price", 0) or 0), 2),
        "requested_price": req_price,
        "min_quantity": round(float(payload.min_quantity or 0), 2),
        "unit": product.get("base_unit", "meter"),
        "reason": (payload.reason or "").strip(),
        "valid_from": now_iso(),
        "valid_until": _norm_until(payload.valid_until),
        "status": status,
        "attachments": [],
        "requested_by": user.get("id"), "requested_by_name": user.get("name", ""),
        "approved_by": None, "approved_by_name": None, "decision_notes": "", "decided_at": None,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.price_approvals.insert_one(doc)
    await audit(user.get("name", ""), "price_approval_created", "price_approval", doc["id"], {
        "customer": doc["customer_name"], "product": doc["product_name"],
        "normal_price": doc["normal_price"], "requested_price": req_price, "status": status,
    })
    return _decorate(safe_doc(doc))


# ─── Detail / Patch / Delete ─────────────────────────────────────────────────

@router.get("/price-approvals/{approval_id}")
async def get_price_approval(approval_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "price_approval", "view")
    ctx = await entity_ctx(request)
    doc = await _get_or_404(approval_id)
    assert_entity_access(doc, "price_approvals", ctx)
    _ensure_owner_or_privileged(doc, user)
    return _decorate(doc)


@router.patch("/price-approvals/{approval_id}")
async def patch_price_approval(approval_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "price_approval", "update")
    doc = await _get_or_404(approval_id)
    _ensure_owner_or_privileged(doc, user)
    if doc["status"] not in EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Pengajuan status '{doc['status']}' tidak dapat diubah")
    allowed = {"requested_price", "min_quantity", "reason", "valid_until"}
    data: Dict[str, Any] = {}
    for k, v in (payload.data or {}).items():
        if k not in allowed:
            continue
        if k == "requested_price":
            rp = round(float(v or 0), 2)
            if rp <= 0:
                raise HTTPException(status_code=400, detail="Harga khusus harus lebih dari 0")
            data[k] = rp
        elif k == "min_quantity":
            data[k] = round(float(v or 0), 2)
        elif k == "valid_until":
            data[k] = _norm_until(str(v))
        else:
            data[k] = (str(v) or "").strip()
    if not data:
        raise HTTPException(status_code=400, detail="Tidak ada field valid untuk diperbarui")
    data["updated_at"] = now_iso()
    updated = await db.price_approvals.find_one_and_update(
        {"id": approval_id}, {"$set": data},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER,
    )
    await audit(user.get("name", ""), "price_approval_updated", "price_approval", approval_id, data)
    return _decorate(safe_doc(updated))


@router.delete("/price-approvals/{approval_id}")
async def delete_price_approval(approval_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "price_approval", "delete")
    doc = await _get_or_404(approval_id)
    _ensure_owner_or_privileged(doc, user)
    if doc["status"] == "approved":
        raise HTTPException(status_code=409, detail="Pengajuan yang sudah disetujui tidak dapat dihapus")
    await db.price_approvals.delete_one({"id": approval_id})
    await audit(user.get("name", ""), "price_approval_deleted", "price_approval", approval_id, {"status": doc["status"]})
    return {"deleted": True, "id": approval_id}


# ─── Lifecycle: submit / approve / reject ────────────────────────────────────

@router.post("/price-approvals/{approval_id}/submit")
async def submit_price_approval(approval_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "price_approval", "update")
    doc = await _get_or_404(approval_id)
    _ensure_owner_or_privileged(doc, user)
    if doc["status"] != "draft":
        raise HTTPException(status_code=409, detail="Hanya pengajuan draft yang dapat disubmit")
    updated = await db.price_approvals.find_one_and_update(
        {"id": approval_id}, {"$set": {"status": "pending", "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER,
    )
    await audit(user.get("name", ""), "price_approval_submitted", "price_approval", approval_id, {"status": "pending"})
    return _decorate(safe_doc(updated))


@router.post("/price-approvals/{approval_id}/approve")
async def approve_price_approval(approval_id: str, payload: PriceApprovalDecision, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "price_approval", "approve")
    doc = await _get_or_404(approval_id)
    if doc["status"] not in DECIDABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Status '{doc['status']}' tidak dapat disetujui")
    update = {
        "status": "approved", "approved_by": user.get("id"),
        "approved_by_name": user.get("name", ""),
        "decision_notes": (payload.decision_notes or "").strip(),
        "decided_at": now_iso(), "updated_at": now_iso(),
    }
    updated = await db.price_approvals.find_one_and_update(
        {"id": approval_id}, {"$set": update},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER,
    )
    await audit(user.get("name", ""), "price_approval_approved", "price_approval", approval_id, {
        "requested_price": doc.get("requested_price"), "approved_by": user.get("name", ""),
    })
    return _decorate(safe_doc(updated))


@router.post("/price-approvals/{approval_id}/reject")
async def reject_price_approval(approval_id: str, payload: PriceApprovalDecision, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "price_approval", "reject")
    doc = await _get_or_404(approval_id)
    if doc["status"] not in DECIDABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Status '{doc['status']}' tidak dapat ditolak")
    update = {
        "status": "rejected", "approved_by": user.get("id"),
        "approved_by_name": user.get("name", ""),
        "decision_notes": (payload.decision_notes or "").strip(),
        "decided_at": now_iso(), "updated_at": now_iso(),
    }
    updated = await db.price_approvals.find_one_and_update(
        {"id": approval_id}, {"$set": update},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER,
    )
    await audit(user.get("name", ""), "price_approval_rejected", "price_approval", approval_id, {
        "reason": update["decision_notes"], "rejected_by": user.get("name", ""),
    })
    return _decorate(safe_doc(updated))


# ─── Attachments (bukti) ─────────────────────────────────────────────────────

@router.post("/price-approvals/{approval_id}/attachments")
async def upload_attachment(approval_id: str, request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    user = await require_permission(request, "price_approval", "update")
    doc = await _get_or_404(approval_id)
    _ensure_owner_or_privileged(doc, user)
    data = await file.read()
    try:
        content_type = storage.validate_upload(file.filename, file.content_type, len(data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    path = storage.build_path(f"price_approvals/{approval_id}", storage.ext_of(file.filename))
    try:
        result = await storage.put_object(path, data, content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gagal mengunggah file: {e}")
    att = {
        "id": new_id("att"),
        "storage_path": result.get("path", path),
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "uploaded_by": user.get("name", ""),
        "uploaded_at": now_iso(),
        "is_deleted": False,
    }
    await db.price_approvals.update_one(
        {"id": approval_id}, {"$push": {"attachments": att}, "$set": {"updated_at": now_iso()}}
    )
    await audit(user.get("name", ""), "price_approval_attachment_added", "price_approval", approval_id,
                {"file": file.filename})
    return att


@router.get("/price-approvals/{approval_id}/attachments/{att_id}/download")
async def download_attachment(
    approval_id: str, att_id: str, request: Request, auth: str = Query(None),
    authorization: str = Header(None),
):
    # Dukung query-param auth untuk <img>/<a> yang tidak bisa kirim header.
    if not authorization and auth:
        # suntik header agar dependency current_user dapat membacanya
        request.scope["headers"] = list(request.scope.get("headers", [])) + [
            (b"authorization", f"Bearer {auth}".encode())
        ]
    user = await require_permission(request, "price_approval", "view")
    doc = await _get_or_404(approval_id)
    _ensure_owner_or_privileged(doc, user)
    att = next((a for a in (doc.get("attachments") or []) if a.get("id") == att_id and not a.get("is_deleted")), None)
    if not att:
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    try:
        content, ctype = await storage.get_object(att["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gagal mengambil file: {e}")
    return Response(
        content=content, media_type=att.get("content_type", ctype),
        headers={"Content-Disposition": f'inline; filename="{att.get("original_filename", "file")}"'},
    )


@router.delete("/price-approvals/{approval_id}/attachments/{att_id}")
async def delete_attachment(approval_id: str, att_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "price_approval", "update")
    doc = await _get_or_404(approval_id)
    _ensure_owner_or_privileged(doc, user)
    res = await db.price_approvals.update_one(
        {"id": approval_id, "attachments.id": att_id},
        {"$set": {"attachments.$.is_deleted": True, "updated_at": now_iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    await audit(user.get("name", ""), "price_approval_attachment_deleted", "price_approval", approval_id,
                {"attachment_id": att_id})
    return {"deleted": True, "id": att_id}
