"""Auth router: login, logout, me, context (F0-A multi-entity identity)."""
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request
from db import db
from dependencies import current_user, audit
from core_utils import hash_password, new_id, now_iso, safe_doc
from schemas import LoginRequest
from services.entity_context_service import build_entity_context

router = APIRouter(prefix="/api")


@router.post("/auth/login")
async def login(payload: LoginRequest) -> Dict[str, Any]:
    user = safe_doc(await db.users.find_one({"email": payload.email, "status": "active"}, {"_id": 0}))
    if not user or user.get("password_hash") != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Email atau password tidak sesuai")
    token = new_id("sess")
    await db.sessions.insert_one(
        {"id": new_id("session"), "token": token, "user_id": user["id"], "created_at": now_iso()}
    )
    user.pop("password_hash", None)
    await audit(user["name"], "login", "user", user["id"], {"email": user["email"], "role": user["role"]})
    onboarding = safe_doc(await db.user_onboarding.find_one({"user_id": user["id"]}, {"_id": 0}))
    entity_context = await build_entity_context(user)
    return {"token": token, "user": user, "onboarding": onboarding, "entity_context": entity_context}


@router.get("/auth/me")
async def me(request: Request) -> Dict[str, Any]:
    """User aktif + entity context (active = header X-Entity-Id bila valid)."""
    user = await current_user(request)
    requested = request.headers.get("X-Entity-Id")
    user["entity_context"] = await build_entity_context(user, requested)
    return user


@router.get("/auth/context")
async def auth_context(request: Request) -> Dict[str, Any]:
    """Entity context terpisah (dipakai Entity Switcher / refresh konteks)."""
    user = await current_user(request)
    requested = request.headers.get("X-Entity-Id")
    return await build_entity_context(user, requested)


@router.post("/auth/logout")
async def logout(request: Request) -> Dict[str, str]:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header.replace("Bearer ", "").strip()
        await db.sessions.delete_one({"token": token})
    return {"message": "Logout berhasil"}
