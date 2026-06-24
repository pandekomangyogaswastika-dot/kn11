"""Audit logs router."""
from typing import Any, Dict, List
from fastapi import APIRouter, Request
from db import db
from dependencies import require_permission
from core_utils import safe_doc

router = APIRouter(prefix="/api")


@router.get("/audit-logs")
async def list_audit_logs(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "product", "view")
    logs = await db.audit_logs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(500)
    return [safe_doc(log) for log in logs if log]
