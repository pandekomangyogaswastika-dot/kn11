"""QC 4-Point Inspection router — Fase 6.2 (P1).

Inspeksi per-roll saat QC (task qc_pending): catat poin defect (4-point) + GSM/lebar
aktual → set Grade roll (A/B/C, ambang configurable). Tanpa aksi karantina otomatis.

Permission: pakai modul `wms` (sejalan dengan QC queue/keputusan existing).
"""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from db import db
from dependencies import require_permission, audit
from core_utils import safe_doc
from schemas import RollInspectionInput
from services.qc_inspection_service import rolls_for_task, inspect_roll, grade_thresholds

router = APIRouter(prefix="/api")


@router.get("/qc/grade-thresholds")
async def get_grade_thresholds(request: Request, entity_id: str = None) -> Dict[str, Any]:
    """Ambang grade 4-point aktif (untuk preview di UI)."""
    await require_permission(request, "wms", "view")
    return await grade_thresholds(entity_id)


@router.get("/inbound/qc/tasks/{task_id}/rolls")
async def list_task_rolls(task_id: str, request: Request) -> List[Dict[str, Any]]:
    """Roll milik 1 inbound task untuk diinspeksi (per qc_task_id)."""
    await require_permission(request, "wms", "view")
    task = await db.wms_tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Inbound task tidak ditemukan")
    return await rolls_for_task(task_id)


@router.post("/inbound/rolls/{roll_id}/inspect")
async def inspect(roll_id: str, payload: RollInspectionInput, request: Request) -> Dict[str, Any]:
    """Catat inspeksi 4-point pada 1 roll → hitung poin & set grade."""
    actor = await require_permission(request, "wms", "update")
    roll = safe_doc(await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0}))
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")

    defects = [d.dict() for d in (payload.defects or [])]
    for d in defects:
        if int(d.get("point_value", 0) or 0) not in (1, 2, 3, 4):
            raise HTTPException(status_code=400, detail="point_value defect harus 1..4")
        if int(d.get("count", 0) or 0) < 0:
            raise HTTPException(status_code=400, detail="count defect tak boleh negatif")

    result = await inspect_roll(roll, defects, payload.gsm_actual, payload.width_actual,
                                payload.note or "", actor)
    await audit(actor["name"], "roll_inspected", "inventory_roll", roll_id,
                {"roll_no": roll.get("roll_no"), "points": result["points"], "grade": result["grade"]})
    return result
