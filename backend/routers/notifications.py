"""Notifications router (Notification Center — Fase 0).

Notifikasi in-app (polling). Sumber event REAL (bukan mock): stok menipis &
reservasi mendekati kedaluwarsa — di-generate dari data inventory & sales_orders.
WebSocket realtime menyusul di Fase 5 (lihat KN_14 §8.2).
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import current_user, require_role
from core_utils import now_iso
from services.notification_service import generate_system_notifications

router = APIRouter(prefix="/api")


def _scope_query(user: Dict[str, Any], entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Notifikasi terlihat bila ditujukan ke role user, ke 'all', atau ke user spesifik."""
    scope = {"$or": [
        {"recipient_role": {"$in": [user.get("role"), "all"]}},
        {"recipient_user": user.get("id")},
    ]}
    if entity_id and entity_id != "all":
        # Notifikasi global (entity_id None) tetap tampil di semua konteks entitas.
        scope = {"$and": [scope, {"$or": [{"entity_id": entity_id}, {"entity_id": None}]}]}
    return scope


@router.get("/notifications")
async def list_notifications(
    request: Request, entity_id: str = None, unread_only: bool = False
) -> List[Dict[str, Any]]:
    user = await current_user(request)
    query = _scope_query(user, entity_id)
    if unread_only:
        query = {"$and": [query, {"read": False}]}
    return await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)


@router.get("/notifications/unread-count")
async def unread_count(request: Request, entity_id: str = None) -> Dict[str, int]:
    user = await current_user(request)
    query = {"$and": [_scope_query(user, entity_id), {"read": False}]}
    return {"count": await db.notifications.count_documents(query)}


@router.post("/notifications/read-all")
async def mark_all_read(request: Request, entity_id: str = None) -> Dict[str, Any]:
    user = await current_user(request)
    query = {"$and": [_scope_query(user, entity_id), {"read": False}]}
    result = await db.notifications.update_many(query, {"$set": {"read": True, "read_at": now_iso()}})
    return {"updated": result.modified_count}


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, request: Request) -> Dict[str, Any]:
    await current_user(request)
    notification = await db.notifications.find_one_and_update(
        {"id": notification_id}, {"$set": {"read": True, "read_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notifikasi tidak ditemukan")
    return notification


@router.post("/notifications/generate")
async def generate(request: Request) -> Dict[str, Any]:
    """Pindai event sistem (stok menipis, reservasi kedaluwarsa) → buat notifikasi."""
    await require_role(request, ["manager"])  # admin auto-allowed di require_role
    created = await generate_system_notifications()
    return {"created": created}
