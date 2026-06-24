"""Users router: CRUD users."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit
from core_utils import hash_password, new_id, now_iso, safe_doc
from schemas import GenericPatch, UserCreate

router = APIRouter(prefix="/api")


@router.get("/users")
async def list_users(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "user", "view")
    return await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(100)


@router.post("/users")
async def create_user(payload: UserCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "user", "create")
    if await db.users.find_one({"email": payload.email}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="Email user sudah terdaftar")
    user = {
        "id": new_id("user"),
        "name": payload.name,
        "email": payload.email,
        "role": payload.role,
        "password_hash": hash_password(payload.password),
        "status": "active",
        "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    await audit(actor["name"], "user_created", "user", user["id"],
                {k: v for k, v in user.items() if k != "password_hash"})
    user.pop("password_hash", None)
    return safe_doc(user)


@router.patch("/users/{user_id}")
async def update_user(user_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "user", "update")
    data = {k: v for k, v in payload.data.items() if k in ["name", "email", "role", "status"]}
    if "password" in payload.data and payload.data["password"]:
        data["password_hash"] = hash_password(payload.data["password"])
    data["updated_at"] = now_iso()
    user = await db.users.find_one_and_update(
        {"id": user_id}, {"$set": data},
        projection={"_id": 0, "password_hash": 0},
        return_document=ReturnDocument.AFTER
    )
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    await audit(actor["name"], "user_updated", "user", user_id, user)
    return user
