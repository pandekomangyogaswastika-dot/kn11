"""QC 4-Point Inspection service — Fase 6.2 (P1).

Inspeksi objektif per-roll saat QC (task qc_pending): hitung total poin defect
(metode 4-point sederhana) → tentukan Grade (A/B/C) via ambang configurable, dan
catat GSM & lebar AKTUAL per roll.

Keputusan desain owner:
  - Skor: TOTAL poin defect saja (Σ point_value × count) — tanpa normalisasi per luas.
  - Grade: poin ≤ a_max → A, ≤ b_max → B, > b_max → C (ambang dari Settings `qc.grade_thresholds`).
  - GSM/Lebar aktual: dicatat saja (tanpa pass/fail otomatis).
  - Hasil: set `roll.grade` dari inspeksi (tanpa aksi karantina otomatis).
"""
from typing import Any, Dict, List, Optional
from db import db
from core_utils import now_iso, safe_doc
from services.config_service import get_effective_settings

VALID_POINTS = {1, 2, 3, 4}


async def grade_thresholds(entity_id: Optional[str] = None) -> Dict[str, float]:
    settings = await get_effective_settings(entity_id)
    qc = settings.get("qc", {}) or {}
    th = qc.get("grade_thresholds", {}) or {}
    return {"a_max": float(th.get("a_max", 20.0) or 20.0),
            "b_max": float(th.get("b_max", 40.0) or 40.0)}


def compute_points(defects: List[Dict[str, Any]]) -> float:
    """Total poin = Σ (point_value × count). point_value harus 1..4."""
    total = 0.0
    for d in defects or []:
        pv = int(d.get("point_value", 0) or 0)
        cnt = int(d.get("count", 0) or 0)
        if pv in VALID_POINTS and cnt > 0:
            total += pv * cnt
    return round(total, 2)


def grade_from_points(points: float, th: Dict[str, float]) -> str:
    if points <= th["a_max"]:
        return "A"
    if points <= th["b_max"]:
        return "B"
    return "C"


async def inspect_roll(roll: Dict[str, Any], defects: List[Dict[str, Any]],
                       gsm_actual: Optional[float], width_actual: Optional[float],
                       note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Catat inspeksi 4-point pada 1 roll → hitung poin & grade → update roll."""
    th = await grade_thresholds(roll.get("owner_entity_id"))
    points = compute_points(defects)
    grade = grade_from_points(points, th)

    norm_defects = [{
        "point_value": int(d.get("point_value", 0) or 0),
        "count": int(d.get("count", 0) or 0),
        "note": d.get("note", ""),
    } for d in (defects or []) if int(d.get("point_value", 0) or 0) in VALID_POINTS and int(d.get("count", 0) or 0) > 0]

    inspection = {
        "points": points, "grade": grade,
        "defects": norm_defects,
        "gsm_actual": (float(gsm_actual) if gsm_actual not in (None, "") else None),
        "width_actual": (float(width_actual) if width_actual not in (None, "") else None),
        "thresholds": th, "note": note or "",
        "inspected_by": actor.get("name", "Admin"),
        "inspected_by_id": actor.get("id", ""),
        "inspected_at": now_iso(),
    }
    updated = await db.inventory_rolls.find_one_and_update(
        {"id": roll["id"]},
        {"$set": {"grade": grade, "defects": norm_defects, "inspection": inspection,
                  "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=True)
    return {"roll": safe_doc(updated), "points": points, "grade": grade, "thresholds": th}


async def rolls_for_task(task_id: str) -> List[Dict[str, Any]]:
    """Roll yang menunggu/inspeksi untuk sebuah inbound task (per qc_task_id)."""
    rolls = await db.inventory_rolls.find(
        {"qc_task_id": task_id}, {"_id": 0}).sort("roll_no", 1).to_list(500)
    prod_ids = list({r.get("product_id") for r in rolls if r.get("product_id")})
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": prod_ids}}, {"_id": 0}).to_list(500)}
    out = []
    for r in rolls:
        prod = prods.get(r.get("product_id"), {})
        insp = r.get("inspection") or {}
        out.append({
            "id": r["id"], "roll_no": r.get("roll_no"),
            "product_id": r.get("product_id"), "sku": prod.get("sku", ""),
            "product_name": prod.get("name", ""),
            "gsm_standard": prod.get("gramasi", None), "width_standard": prod.get("lebar", None),
            "length_initial": r.get("length_initial"), "unit": r.get("unit"),
            "grade": r.get("grade", ""), "status": r.get("status", ""),
            "inspected": bool(insp.get("inspected_at")),
            "inspection": insp,
        })
    return out
