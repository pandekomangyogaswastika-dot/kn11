"""Admin router: master data import/export, permissions, bulk ops."""
import csv
import io
import os
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from db import db
from dependencies import require_permission, audit
from core_utils import hash_password, new_id, now_iso, safe_doc
from schemas import PermissionUpdate
from permissions_config import DEFAULT_PERMISSIONS
from services.demo_seed_service import run_demo_seed

try:
    import openpyxl
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

router = APIRouter(prefix="/api")


def _parse_csv_or_xlsx(content: bytes, filename: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """Parse CSV or XLSX, return (headers, rows)."""
    if filename.endswith(".xlsx") and XLSX_AVAILABLE:
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], []
        headers = [str(h).strip() for h in rows[0]]
        data = []
        for row in rows[1:]:
            if any(cell is not None for cell in row):
                data.append({headers[i]: str(row[i] or "").strip() for i in range(len(headers))})
        return headers, data
    else:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        return list(headers), list(reader)


def _validate_and_enrich_product(row: Dict[str, str], idx: int) -> Tuple[Optional[Dict], Optional[str]]:
    """Validate a product row. Returns (product_dict, error_msg)."""
    errors = []
    sku = row.get("sku", "").strip()
    name = row.get("name", "").strip()
    if not sku:
        errors.append("SKU wajib diisi")
    if not name:
        errors.append("Nama wajib diisi")
    try:
        price = float(row.get("price", 0) or 0)
    except ValueError:
        errors.append("Price harus angka")
        price = 0
    if errors:
        return None, f"Baris {idx + 2}: {', '.join(errors)}"
    return {
        "sku": sku, "name": name,
        "category": row.get("category", "Kain").strip() or "Kain",
        "variant": row.get("variant", "Regular").strip() or "Regular",
        "color": row.get("color", "Natural").strip() or "Natural",
        "motif": row.get("motif", "Polos").strip() or "Polos",
        "grade": row.get("grade", "A").strip() or "A",
        "supplier": row.get("supplier", "Internal").strip() or "Internal",
        "base_unit": row.get("base_unit", "meter").strip() or "meter",
        "price": price,
        "image": row.get("image", "https://images.unsplash.com/photo-1774679817333-decf0d988dd5?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85").strip(),
        "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
    }, None


@router.post("/master-data/import-products")
async def import_products(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = False
) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "import")
    content = await file.read()
    _, rows = _parse_csv_or_xlsx(content, file.filename or "")
    if not rows:
        raise HTTPException(status_code=400, detail="File kosong atau format tidak dikenal")
    results = {"total": len(rows), "created": 0, "updated": 0, "errors": [], "dry_run": dry_run}
    for idx, row in enumerate(rows):
        product_data, error = _validate_and_enrich_product(row, idx)
        if error:
            results["errors"].append(error)
            continue
        existing = safe_doc(await db.products.find_one({"sku": product_data["sku"]}, {"_id": 0}))
        if dry_run:
            if existing:
                results["updated"] += 1
            else:
                results["created"] += 1
            continue
        if existing:
            await db.products.update_one(
                {"sku": product_data["sku"]},
                {"$set": {**product_data, "updated_at": now_iso()}}
            )
            results["updated"] += 1
        else:
            product_data.update({"id": new_id("prod"), "created_at": now_iso(), "updated_at": now_iso()})
            await db.products.insert_one(product_data)
            results["created"] += 1
    if not dry_run:
        await audit(actor["name"], "products_imported", "product", "bulk",
                    {"total": results["total"], "created": results["created"],
                     "updated": results["updated"], "errors": len(results["errors"])})
    return results


@router.post("/master-data/import-customers")
async def import_customers(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = False
) -> Dict[str, Any]:
    actor = await require_permission(request, "customer", "import")
    content = await file.read()
    _, rows = _parse_csv_or_xlsx(content, file.filename or "")
    if not rows:
        raise HTTPException(status_code=400, detail="File kosong")
    results = {"total": len(rows), "created": 0, "updated": 0, "errors": [], "dry_run": dry_run}
    count = await db.customers.count_documents({})
    for idx, row in enumerate(rows):
        name = row.get("name", "").strip()
        if not name:
            results["errors"].append(f"Baris {idx + 2}: Nama wajib diisi")
            continue
        city = row.get("city", "").strip()
        address = row.get("address", "").strip()
        pic_name = row.get("pic_name", name).strip()
        phone = row.get("phone", "").strip()
        email = row.get("email", "").strip()
        existing = safe_doc(await db.customers.find_one(
            {"$or": [{"name": name}, {"email": email}] if email else [{"name": name}]},
            {"_id": 0}
        ))
        if dry_run:
            if existing:
                results["updated"] += 1
            else:
                results["created"] += 1
            continue
        if existing:
            await db.customers.update_one(
                {"id": existing["id"]},
                {"$set": {"name": name, "pic_name": pic_name, "phone": phone,
                           "city": city, "updated_at": now_iso()}}
            )
            results["updated"] += 1
        else:
            count += 1
            customer = {
                "id": new_id("cust"), "code": f"CUST-{count:04d}",
                "name": name, "pic_name": pic_name, "phone": phone, "email": email,
                "type": row.get("type", "Retail").strip() or "Retail",
                "city": city, "status": "active", "created_by": actor["name"],
                "created_at": now_iso(),
                "addresses": [{"id": new_id("addr"), "label": "Alamat Utama",
                               "recipient_name": pic_name, "phone": phone,
                               "city": city, "address": address, "is_primary": True}]
            }
            await db.customers.insert_one(customer)
            results["created"] += 1
    if not dry_run:
        await audit(actor["name"], "customers_imported", "customer", "bulk",
                    {"total": results["total"], "created": results["created"]})
    return results


@router.post("/master-data/import-warehouses")
async def import_warehouses(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = False
) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "import")
    content = await file.read()
    _, rows = _parse_csv_or_xlsx(content, file.filename or "")
    if not rows:
        raise HTTPException(status_code=400, detail="File kosong")
    results = {"total": len(rows), "created": 0, "updated": 0, "errors": [], "dry_run": dry_run}
    for idx, row in enumerate(rows):
        code = row.get("code", "").strip()
        name = row.get("name", "").strip()
        if not code or not name:
            results["errors"].append(f"Baris {idx + 2}: Code dan nama wajib")
            continue
        if dry_run:
            existing = await db.warehouses.find_one({"code": code}, {"_id": 0})
            if existing:
                results["updated"] += 1
            else:
                results["created"] += 1
            continue
        existing = safe_doc(await db.warehouses.find_one({"code": code}, {"_id": 0}))
        if existing:
            await db.warehouses.update_one(
                {"code": code},
                {"$set": {"name": name, "city": row.get("city", "").strip(), "updated_at": now_iso()}}
            )
            results["updated"] += 1
        else:
            wh_id = new_id("wh")
            await db.warehouses.insert_one({
                "id": wh_id, "code": code, "name": name, "city": row.get("city", "").strip(),
                "lat": None, "lng": None,
                "zones": [{"id": new_id("zone"), "name": "Zone A",
                           "racks": [{"id": new_id("rack"), "name": "Rack A1",
                                      "bins": [{"id": new_id("bin"), "code": "A1-01", "capacity": 1000}]}]}],
                "active": True, "created_at": now_iso()
            })
            results["created"] += 1
    if not dry_run:
        await audit(actor["name"], "warehouses_imported", "warehouse", "bulk",
                    {"total": results["total"], "created": results["created"]})
    return results


@router.get("/master-data/export-products")
async def export_products(request: Request) -> Response:
    await require_permission(request, "product", "export")
    products = await db.products.find({}, {"_id": 0}).to_list(1000)
    fields = ["id", "sku", "name", "category", "variant", "color", "motif", "grade",
              "supplier", "base_unit", "price", "status"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(products)
    return Response(content=out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=products.csv"})


@router.get("/master-data/export-customers")
async def export_customers(request: Request) -> Response:
    await require_permission(request, "customer", "export")
    customers = await db.customers.find({}, {"_id": 0}).to_list(500)
    fields = ["id", "code", "name", "pic_name", "phone", "email", "type", "city", "status"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(customers)
    return Response(content=out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=customers.csv"})


@router.get("/master-data/export-warehouses")
async def export_warehouses(request: Request) -> Response:
    await require_permission(request, "warehouse", "export")
    warehouses = await db.warehouses.find({}, {"_id": 0}).to_list(100)
    fields = ["id", "code", "name", "city", "active"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(warehouses)
    return Response(content=out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=warehouses.csv"})


@router.get("/permissions")
async def get_permissions(request: Request) -> Dict[str, Any]:
    await require_permission(request, "permission", "view")
    record = safe_doc(await db.permission_settings.find_one({"id": "default"}, {"_id": 0}))
    return {"matrix": record.get("matrix", DEFAULT_PERMISSIONS) if record else DEFAULT_PERMISSIONS}


@router.put("/permissions")
async def update_permissions(payload: PermissionUpdate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "permission", "update")
    await db.permission_settings.update_one(
        {"id": "default"}, {"$set": {"matrix": payload.matrix, "updated_at": now_iso()}}, upsert=True
    )
    await audit(actor["name"], "permissions_updated", "permission_settings", "default", payload.matrix)
    return {"matrix": payload.matrix}


# =============================================================================
# DEMO SEED ENDPOINT
# =============================================================================
# Endpoint admin-only untuk reset & re-populate database dengan data demo.
# Diproteksi dengan:
#   1. Role admin (via require_permission)
#   2. Confirm token wajib di body (mencegah accidental call)
#   3. Optional env var SEED_DEMO_ENABLED — bila di-set ke "false", endpoint
#      akan menolak request (untuk safety di production setelah data real masuk)
# =============================================================================

class SeedDemoRequest(BaseModel):
    confirm: str  # Harus = "YES_CLEAR_AND_SEED_DEMO_DATA"


@router.post("/admin/seed-demo")
async def seed_demo(payload: SeedDemoRequest, request: Request) -> Dict[str, Any]:
    """
    DESTRUCTIVE: Hapus semua data operasional dan isi ulang dengan demo data.
    Hanya untuk admin. Wajib kirim confirm token agar tidak terjadi accidental call.
    """
    actor = await require_permission(request, "permission", "update")

    # Safety check 1 — feature flag
    enabled = os.environ.get("SEED_DEMO_ENABLED", "true").lower()
    if enabled in ("false", "0", "no"):
        raise HTTPException(
            status_code=403,
            detail="Seed demo endpoint dinonaktifkan via SEED_DEMO_ENABLED=false"
        )

    # Safety check 2 — explicit confirm token
    expected_token = "YES_CLEAR_AND_SEED_DEMO_DATA"
    if payload.confirm != expected_token:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Confirm token tidak sesuai. Wajib kirim body "
                f'{{"confirm": "{expected_token}"}} untuk konfirmasi reset+seed.'
            )
        )

    # Run seed pipeline
    try:
        summary = await run_demo_seed(db)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Seed gagal dijalankan: {type(exc).__name__}: {exc}"
        )

    # Audit log
    await audit(
        actor["name"],
        "demo_seed_executed",
        "database",
        "all_operational_collections",
        summary
    )

    return {
        "status": "ok",
        "executed_by": actor["name"],
        "summary": summary,
        "note": (
            "Database telah di-reset dan diisi ulang dengan demo data. "
            "Login dengan akun demo: admin / sales / manager / warehouse (password: demo12345)."
        ),
    }
