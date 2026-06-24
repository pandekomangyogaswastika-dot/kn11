"""EPIC 1 — Agregasi Home/landing per role (Control Tower / Performa Saya).

Reuse service existing (sales_force, customer credit, reorder, approvals).
Payload SALES sengaja TANPA biaya/HPP (role tightening EPIC 1).
"""
from calendar import monthrange
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db import db
from services import sales_force_service as sf
from services.customer_service import (
    compute_customer_credit,
    _order_grand_total,
    DEAD_STATUSES,
)
from services.purchase_requisition_service import reorder_suggestions
from services.approval_service import get_pending_approvals_count


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _today_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month_progress() -> tuple:
    now = datetime.now(timezone.utc)
    return now.day, monthrange(now.year, now.month)[1]


async def sales_home(sales_id: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Performa Saya — komisi MTD (akrual+proyeksi), target & capaian, customer+kredit,
    penagihan, order terbaru. TANPA biaya/HPP."""
    period = _current_month()
    comm = await sf.compute_commission(sales_id, period, entity_id)
    kpi = comm["kpi"]
    history = await sf.commission_history(sales_id, "month", period, 6, entity_id)

    day, dim = _month_progress()
    projection = round(comm["total_incentive"] / day * dim, 2) if day else comm["total_incentive"]

    # Customer saya + kredit
    cust_filter: Dict[str, Any] = {"assigned_sales_id": sales_id}
    if entity_id and entity_id != "all":
        cust_filter["entity_id"] = entity_id
    customers = await db.customers.find(cust_filter, {"_id": 0}).to_list(2000)
    cust_rows: List[Dict[str, Any]] = []
    for c in customers:
        cc = await compute_customer_credit(c)
        cust_rows.append({
            "id": c["id"], "name": c.get("name", ""),
            "credit_limit": cc["credit_limit"], "ar_outstanding": cc["ar_outstanding"],
            "overdue_amount": cc["overdue_amount"], "status": cc["status"],
        })
    cust_rows.sort(key=lambda r: r["overdue_amount"], reverse=True)
    collections = [r for r in cust_rows if r["overdue_amount"] > 0][:8]

    # Order terbaru (tanpa biaya)
    recent_orders: List[Dict[str, Any]] = []
    cust_ids = [c["id"] for c in customers]
    if cust_ids:
        cmap = {c["id"]: c.get("name", "") for c in customers}
        raw = await db.sales_orders.find(
            {"customer_id": {"$in": cust_ids}}, {"_id": 0}
        ).sort("created_at", -1).to_list(8)
        for o in raw:
            recent_orders.append({
                "id": o.get("id"), "number": o.get("number"),
                "customer_name": cmap.get(o.get("customer_id"), ""),
                "grand_total": _order_grand_total(o),
                "status": o.get("status"), "payment_status": o.get("payment_status"),
                "created_at": o.get("created_at"),
            })

    return {
        "period": period,
        "commission": {
            "mtd_accrual": comm["total_incentive"],
            "projection_month_end": projection,
            "projection_full": comm.get("projection_full", comm["total_incentive"]),
            "strategy": comm.get("strategy", "per_sku"),
            "breakdown": comm.get("breakdown", []),
            "base_amount": comm["base_amount"],
            "applied_rate": comm["applied_rate"],
            "bonus_new_customer": comm["bonus_new_customer"],
        },
        "target": {"amount": comm["target_amount"], "achievement_pct": comm["achievement_pct"]},
        "kpi": {
            "total_sales": kpi["total_sales"],
            "total_collected": kpi["total_collected"],
            "collection_rate": kpi["collection_rate"],
            "ar_outstanding": kpi["ar_outstanding"],
            "overdue_amount": kpi["overdue_amount"],
            "orders_count": kpi["orders_count"],
            "customers_count": kpi["customers_count"],
            "new_customers": kpi["new_customers"],
            "avg_order_value": kpi["avg_order_value"],
        },
        "history": history,
        "customers": cust_rows[:10],
        "collections": collections,
        "recent_orders": recent_orders,
    }


async def manager_home(period: Optional[str] = None, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Manager Home — leaderboard tim, total, target, koleksi, approval."""
    period = period or _current_month()
    board = await sf.leaderboard(period, entity_id)
    totals = {
        "total_sales": round(sum(r["total_sales"] for r in board), 2),
        "total_collected": round(sum(r["total_collected"] for r in board), 2),
        "ar_outstanding": round(sum(r["ar_outstanding"] for r in board), 2),
        "overdue_amount": round(sum(r["overdue_amount"] for r in board), 2),
    }
    target_total = 0.0
    for r in board:
        target_total += await sf._target_collection_for(r["sales_id"], period)
    achievement = round(totals["total_collected"] / target_total * 100, 2) if target_total else 0
    approvals_pending = await get_pending_approvals_count("manager")
    return {
        "period": period,
        "leaderboard": board,
        "totals": totals,
        "target": {"amount": round(target_total, 2), "achievement_pct": achievement},
        "approvals_pending": approvals_pending,
    }


async def admin_home(entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Admin Control Tower — penjualan hari/MTD, AR aging ringkas, approval pending,
    low-stock/reorder, ringkasan payout insentif."""
    period = _current_month()
    board = await sf.leaderboard(period, entity_id)

    sales_mtd = round(sum(r["total_sales"] for r in board), 2)
    collected_mtd = round(sum(r["total_collected"] for r in board), 2)
    ar_total = round(sum(r["ar_outstanding"] for r in board), 2)
    overdue_total = round(sum(r["overdue_amount"] for r in board), 2)

    # Penjualan hari ini
    scope: Dict[str, Any] = {}
    if entity_id and entity_id != "all":
        scope["entity_id"] = entity_id
    today_orders = await db.sales_orders.find(
        {**scope, "created_at": {"$regex": f"^{_today_prefix()}"}}, {"_id": 0}
    ).to_list(4000)
    live_today = [o for o in today_orders if o.get("status") not in DEAD_STATUSES]
    today_sales = round(sum(_order_grand_total(o) for o in live_today), 2)

    approvals_pending = await get_pending_approvals_count("admin")

    reorder = await reorder_suggestions(entity_id)
    reorder_items = reorder.get("items", [])

    payout = 0.0
    for r in board:
        c = await sf.compute_commission(r["sales_id"], period, entity_id)
        payout += c["total_incentive"]

    top_overdue = sorted(board, key=lambda r: r["overdue_amount"], reverse=True)[:5]

    return {
        "period": period,
        "sales": {
            "today": today_sales, "today_orders": len(live_today),
            "mtd": sales_mtd, "collected_mtd": collected_mtd,
        },
        "ar": {"outstanding": ar_total, "overdue": overdue_total},
        "approvals_pending": approvals_pending,
        "low_stock": {"count": len(reorder_items), "items": reorder_items[:8]},
        "incentive_payout": round(payout, 2),
        "leaderboard_top": board[:5],
        "top_overdue": [
            {"sales_name": r.get("sales_name", ""), "overdue_amount": r["overdue_amount"],
             "ar_outstanding": r["ar_outstanding"]}
            for r in top_overdue
        ],
    }
