"""Dashboard router: main metrics + overview."""
from typing import Any, Dict
from fastapi import APIRouter, Request
from db import db
from core_utils import safe_doc
from services.inventory_service import expire_old_reservations, product_summary
from entity_scope import entity_ctx, resolve_list_scope

router = APIRouter(prefix="/api")


@router.get("/dashboard")
async def dashboard(request: Request, entity_id: str = None) -> Dict[str, Any]:
    expired = await expire_old_reservations()
    # Multi-Entity (Fase 0): orders & customers di-scope per entitas; produk,
    # gudang & stok bersifat SHARED lintas-entitas (lihat KN_14 §7).
    # KONSISTENSI (RC-7/INV-4/INV-5): pakai resolve_list_scope yang sama dgn
    # GET /sales-orders → tanpa header/param = entitas AKTIF; header X-Entity-Id:all
    # (view_all) = semua entitas yang diizinkan. KPI dashboard SELALU == list.
    ctx = await entity_ctx(request)
    scope = resolve_list_scope("sales_orders", {}, ctx, entity_id)
    products_raw = await db.products.find({}, {"_id": 0}).to_list(100)
    orders_raw = await db.sales_orders.find(scope, {"_id": 0}).sort("created_at", -1).to_list(20)
    warehouses_raw = await db.warehouses.find({}, {"_id": 0}).to_list(100)
    customers_raw = await db.customers.find(scope, {"_id": 0}).to_list(100)
    products = [safe_doc(p) for p in products_raw if p]
    orders = [safe_doc(o) for o in orders_raw if o]
    warehouses = [safe_doc(w) for w in warehouses_raw if w]
    customers = [safe_doc(c) for c in customers_raw if c]
    # G9 fix (RC-7): active_orders dihitung dari SELURUH order via count_documents,
    # BUKAN dari window 20 order terakhir (yang membuat KPI salah saat >20 order).
    active_orders = await db.sales_orders.count_documents(
        {**scope, "status": {"$nin": ["done", "cancelled", "expired"]}}
    )
    total_products = await db.products.count_documents({})
    total_warehouses = await db.warehouses.count_documents({})
    total_customers = await db.customers.count_documents(scope)
    total_available = 0.0
    total_reserved = 0.0
    for product in products:
        summary = await product_summary(product["id"])
        product.update(summary)
        total_available += summary["available_qty"]
        total_reserved += summary["reserved_qty"]
    return {
        "expired_released": expired,
        "metrics": {
            "products": total_products,
            "warehouses": total_warehouses,
            "customers": total_customers,
            "available_qty": total_available,
            "reserved_qty": total_reserved,
            "active_orders": active_orders,
        },
        "products": products,
        "orders": orders,
        "warehouses": warehouses,
        "customers": customers,
    }
