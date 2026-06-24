"""Shared auth/permission dependencies and audit helper."""
from typing import Any, Dict, List
from fastapi import HTTPException, Request
from db import db
from core_utils import safe_doc, now_iso, new_id
from permissions_config import DEFAULT_PERMISSIONS


async def current_user(request: Request) -> Dict[str, Any]:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Login diperlukan")
    token = header.replace("Bearer ", "").strip()
    session = safe_doc(await db.sessions.find_one({"token": token}, {"_id": 0}))
    if not session:
        raise HTTPException(status_code=401, detail="Session tidak valid")
    user = safe_doc(await db.users.find_one({"id": session["user_id"], "status": "active"}, {"_id": 0, "password_hash": 0}))
    if not user:
        raise HTTPException(status_code=401, detail="User tidak aktif")
    return user


async def require_role(request: Request, allowed_roles: List[str]) -> Dict[str, Any]:
    user = await current_user(request)
    if user.get("role") == "admin" or user.get("role") in allowed_roles:
        return user
    raise HTTPException(status_code=403, detail="Role Anda tidak memiliki izin untuk aksi ini")


async def permission_matrix() -> Dict[str, Dict[str, List[str]]]:
    record = safe_doc(await db.permission_settings.find_one({"id": "default"}, {"_id": 0}))
    return record.get("matrix", DEFAULT_PERMISSIONS) if record else DEFAULT_PERMISSIONS


async def require_permission(request: Request, module: str, action: str) -> Dict[str, Any]:
    user = await current_user(request)
    matrix = await permission_matrix()
    allowed = matrix.get(user.get("role"), {}).get(module, [])
    if action in allowed or "*" in allowed:
        return user
    raise HTTPException(status_code=403, detail=f"Permission ditolak: {module}.{action}")


async def audit(
    actor: str, action: str, entity_type: str, entity_id: str, after: Any, reason: str = ""
) -> None:
    # Clean after data to remove any MongoDB ObjectIds recursively
    clean_after = safe_doc(after) if after is not None else None
    await db.audit_logs.insert_one(
        {
            "id": new_id("audit"),
            "actor": actor,
            "role": "system/demo",
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "before": None,
            "after": clean_after,
            "reason": reason,
            "timestamp": now_iso(),
        }
    )
