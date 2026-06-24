"""Onboarding router: per-role checklists for first-time users."""
from typing import Any, Dict, List
from fastapi import APIRouter, Request
from db import db
from dependencies import current_user, audit
from core_utils import now_iso, safe_doc

router = APIRouter(prefix="/api")

ROLE_CHECKLISTS: Dict[str, List[Dict[str, Any]]] = {
    "admin": [
        {"id": "create_warehouse", "label": "Buat gudang pertama", "description": "Tambahkan minimal 1 gudang di Master Data"},
        {"id": "create_uom", "label": "Buat UOM pertama", "description": "Tambahkan unit satuan di Master Data"},
        {"id": "create_product", "label": "Buat produk pertama", "description": "Tambahkan produk kain di Master Data"},
        {"id": "configure_template", "label": "Konfigurasi document template", "description": "Atur template Surat Jalan atau Invoice"},
        {"id": "create_user", "label": "Buat user baru", "description": "Tambahkan user dengan role Sales atau Warehouse"},
        {"id": "set_permissions", "label": "Review permission matrix", "description": "Cek dan sesuaikan permission per role"},
    ],
    "sales": [
        {"id": "browse_products", "label": "Jelajahi katalog produk", "description": "Lihat produk tersedia di Sales POS"},
        {"id": "add_customer", "label": "Tambah atau pilih customer", "description": "Buat customer baru atau pilih existing"},
        {"id": "create_order", "label": "Buat sales order pertama", "description": "Buat order dan reservasi stok otomatis"},
        {"id": "submit_approval", "label": "Submit order ke approval", "description": "Kirim order ke manager untuk diapprove"},
        {"id": "print_document", "label": "Cetak dokumen order", "description": "Generate dan cetak Surat Jalan atau Invoice"},
    ],
    "manager": [
        {"id": "check_dashboard", "label": "Cek Manager Dashboard", "description": "Review KPI stok, order, dan warehouse"},
        {"id": "approve_order", "label": "Approve sales order", "description": "Review dan approve order yang masuk"},
        {"id": "review_stock_aging", "label": "Review stock aging", "description": "Identifikasi stok lama di laporan"},
        {"id": "run_cycle_count", "label": "Jalankan cycle count", "description": "Buat sesi cycle count untuk gudang"},
        {"id": "export_report", "label": "Export laporan", "description": "Export data produk atau customer ke CSV"},
    ],
    "warehouse": [
        {"id": "check_wms_tasks", "label": "Cek WMS task queue", "description": "Lihat daftar tugas inbound/outbound"},
        {"id": "scan_inbound", "label": "Proses inbound pertama", "description": "Scan dan konfirmasi penerimaan barang"},
        {"id": "advance_task", "label": "Advance task ke stage berikutnya", "description": "Klik Advance Stage untuk update status"},
        {"id": "scan_outbound", "label": "Proses outbound task", "description": "Generate outbound dari order yang confirmed"},
        {"id": "dispatch_shipment", "label": "Dispatch pengiriman", "description": "Selesaikan task outbound ke status dispatched"},
    ],
}


@router.get("/onboarding")
async def get_onboarding(request: Request) -> Dict[str, Any]:
    user = await current_user(request)
    record = safe_doc(
        await db.user_onboarding.find_one({"user_id": user["id"]}, {"_id": 0})
    )
    checklist = ROLE_CHECKLISTS.get(user["role"], [])
    completed_ids = record.get("completed", []) if record else []
    items = [
        {**item, "completed": item["id"] in completed_ids}
        for item in checklist
    ]
    return {
        "user_id": user["id"],
        "role": user["role"],
        "items": items,
        "total": len(items),
        "completed_count": len(completed_ids),
        "progress_pct": round(len(completed_ids) / len(checklist) * 100) if checklist else 0,
    }


@router.post("/onboarding/{task_id}/complete")
async def complete_task(task_id: str, request: Request) -> Dict[str, Any]:
    user = await current_user(request)
    await db.user_onboarding.update_one(
        {"user_id": user["id"]},
        {"$addToSet": {"completed": task_id}, "$set": {"updated_at": now_iso()}},
        upsert=True
    )
    await audit(user["name"], "onboarding_completed", "user", user["id"], {"task_id": task_id})
    return {"task_id": task_id, "completed": True}


@router.post("/onboarding/reset")
async def reset_onboarding(request: Request) -> Dict[str, Any]:
    user = await current_user(request)
    await db.user_onboarding.delete_one({"user_id": user["id"]})
    return {"message": "Onboarding direset"}
