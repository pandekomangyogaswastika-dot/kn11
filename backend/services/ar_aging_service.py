"""EPIC7-A — AR / Piutang Aging (read/derived report).

SSOT: diturunkan dari `sales_orders` + `payments[]` (SAMA dengan credit engine &
collection_worklist). Reuse helper `customer_service` agar TIDAK terjadi drift:
  `_order_grand_total`, `_order_paid`, `order_payment_method`, `_term_days`,
  `_parse_dt`, `DEAD_STATUSES`, `NON_AR_METHODS`.

Buckets aging (berdasar hari telat jatuh tempo):
  current (belum jatuh tempo), 1-30, 31-60, 61-90, 90+.

Denda (late fee) = **ESTIMASI informasional** (tidak posting ke order/GL),
configurable via `system_settings.ar` (`denda_rate_pct_per_month`, `grace_days`).
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import math

from db import db
from services.config_service import get_effective_settings
from services.customer_service import (
    _order_grand_total as order_grand_total,
    _order_paid as order_paid,
    order_payment_method,
    _term_days as term_days,
    _parse_dt as parse_dt,
    DEAD_STATUSES,
    NON_AR_METHODS,
)

EPS = 0.01
BUCKET_KEYS = ["current", "b1_30", "b31_60", "b61_90", "b90_plus"]
WARNING_RATIO = 0.8
OVERDUE_BLOCK_DAYS = 14


async def get_ar_config(entity_id: Optional[str] = None) -> Dict[str, Any]:
    settings = await get_effective_settings(entity_id)
    ar = (settings or {}).get("ar") or {}
    return {
        "denda_rate_pct_per_month": float(ar.get("denda_rate_pct_per_month", 0) or 0),
        "grace_days": int(ar.get("grace_days", 0) or 0),
    }


def _bucket(days_late: int) -> str:
    if days_late <= 0:
        return "current"
    if days_late <= 30:
        return "b1_30"
    if days_late <= 60:
        return "b31_60"
    if days_late <= 90:
        return "b61_90"
    return "b90_plus"


def _denda_estimate(outstanding: float, days_late: int, cfg: Dict[str, Any]) -> float:
    rate = float(cfg.get("denda_rate_pct_per_month", 0) or 0)
    eff = days_late - int(cfg.get("grace_days", 0) or 0)
    if rate <= 0 or eff <= 0 or outstanding <= EPS:
        return 0.0
    months = math.ceil(eff / 30)
    return round(outstanding * (rate / 100.0) * months, 2)


def _empty_buckets() -> Dict[str, float]:
    return {k: 0.0 for k in BUCKET_KEYS}


def _credit_status(credit_limit: float, ar_outstanding: float, max_overdue_days: int,
                   manual_status: str) -> str:
    status = "active"
    near = credit_limit > 0 and ar_outstanding >= WARNING_RATIO * credit_limit
    over = credit_limit > 0 and ar_outstanding >= credit_limit
    if near or max_overdue_days > 0:
        status = "warning"
    if over or max_overdue_days > OVERDUE_BLOCK_DAYS:
        status = "blocked"
    if manual_status == "blocked":
        status = "blocked"
    return status


async def _load_scope(entity_id: Optional[str], sales_id: Optional[str]):
    """Ambil customers (terfilter) + map sales-name dalam minimal query."""
    cust_filter: Dict[str, Any] = {}
    if entity_id and entity_id != "all":
        cust_filter["entity_id"] = entity_id
    if sales_id:
        cust_filter["assigned_sales_id"] = sales_id
    customers = await db.customers.find(
        cust_filter,
        {"_id": 0, "id": 1, "name": 1, "assigned_sales_id": 1, "payment_profile": 1,
         "credit_limit": 1, "status": 1, "entity_id": 1, "deposit_balance": 1},
    ).to_list(5000)
    sales_ids = {c.get("assigned_sales_id") for c in customers if c.get("assigned_sales_id")}
    smap = {}
    if sales_ids:
        for u in await db.users.find({"id": {"$in": list(sales_ids)}}, {"_id": 0, "id": 1, "name": 1}).to_list(2000):
            smap[u["id"]] = u.get("name", "")
    return customers, smap


def _eligible_outstanding(o: Dict[str, Any]):
    """Return outstanding bila order termasuk AR terbuka, else None."""
    if o.get("status") in DEAD_STATUSES or o.get("payment_status") == "paid":
        return None
    if order_payment_method(o) in NON_AR_METHODS:
        return None
    outstanding = round(order_grand_total(o) - order_paid(o), 2)
    if outstanding <= EPS:
        return None
    return outstanding


async def aging_report(entity_id: Optional[str] = None, sales_id: Optional[str] = None,
                       as_of: Optional[str] = None) -> Dict[str, Any]:
    """Ringkasan aging piutang: totals per-bucket + baris per-customer."""
    now = parse_dt(as_of) or datetime.now(timezone.utc)
    cfg = await get_ar_config(entity_id)
    customers, smap = await _load_scope(entity_id, sales_id)
    cmap = {c["id"]: c for c in customers}
    cust_ids = list(cmap.keys())

    per_customer: Dict[str, Dict[str, Any]] = {}
    totals = {**_empty_buckets(), "total": 0.0, "overdue": 0.0, "denda": 0.0,
              "orders": 0, "customers": 0}

    if cust_ids:
        orders = await db.sales_orders.find(
            {"customer_id": {"$in": cust_ids}},
            {"_id": 0, "id": 1, "number": 1, "customer_id": 1, "customer_name": 1,
             "status": 1, "payment_status": 1, "grand_total": 1, "total_amount": 1,
             "payments": 1, "created_at": 1, "payment_term_code": 1,
             "payment_term_days": 1, "payment_profile_method": 1},
        ).to_list(20000)

        for o in orders:
            outstanding = _eligible_outstanding(o)
            if outstanding is None:
                continue
            cid = o.get("customer_id")
            cust = cmap.get(cid, {})
            created = parse_dt(o.get("created_at")) or now
            due = created + timedelta(days=term_days(cust, o))
            days_late = (now - due).days
            bucket = _bucket(days_late)
            denda = _denda_estimate(outstanding, days_late, cfg)

            row = per_customer.get(cid)
            if not row:
                row = {
                    "customer_id": cid,
                    "customer_name": o.get("customer_name") or cust.get("name", ""),
                    "assigned_sales_id": cust.get("assigned_sales_id", ""),
                    "assigned_sales_name": smap.get(cust.get("assigned_sales_id", ""), ""),
                    "credit_limit": round(float(cust.get("credit_limit", 0) or 0), 2),
                    "deposit_balance": round(float(cust.get("deposit_balance", 0) or 0), 2),
                    **_empty_buckets(),
                    "outstanding": 0.0, "overdue": 0.0, "denda": 0.0,
                    "oldest_days": 0, "orders": 0,
                    "_manual_status": cust.get("status", ""),
                }
                per_customer[cid] = row
            row[bucket] = round(row[bucket] + outstanding, 2)
            row["outstanding"] = round(row["outstanding"] + outstanding, 2)
            row["orders"] += 1
            if days_late > 0:
                row["overdue"] = round(row["overdue"] + outstanding, 2)
                row["oldest_days"] = max(row["oldest_days"], days_late)
            row["denda"] = round(row["denda"] + denda, 2)

            totals[bucket] = round(totals[bucket] + outstanding, 2)
            totals["total"] = round(totals["total"] + outstanding, 2)
            totals["orders"] += 1
            if days_late > 0:
                totals["overdue"] = round(totals["overdue"] + outstanding, 2)
            totals["denda"] = round(totals["denda"] + denda, 2)

    rows: List[Dict[str, Any]] = []
    for row in per_customer.values():
        row["credit_status"] = _credit_status(
            row["credit_limit"], row["outstanding"], row["oldest_days"], row.pop("_manual_status", ""))
        row["available_credit"] = (round(max(row["credit_limit"] - row["outstanding"], 0), 2)
                                   if row["credit_limit"] > 0 else None)
        rows.append(row)
    rows.sort(key=lambda r: r["outstanding"], reverse=True)
    totals["customers"] = len(rows)

    return {
        "as_of": now.isoformat(),
        "entity_id": entity_id or "all",
        "config": cfg,
        "totals": totals,
        "customers": rows,
    }


async def customer_aging_detail(customer_id: str, as_of: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Rincian per-order untuk satu customer (untuk drill-down)."""
    customer = await db.customers.find_one(
        {"id": customer_id},
        {"_id": 0, "id": 1, "name": 1, "assigned_sales_id": 1, "payment_profile": 1,
         "credit_limit": 1, "status": 1, "deposit_balance": 1},
    )
    if not customer:
        return None
    now = parse_dt(as_of) or datetime.now(timezone.utc)
    cfg = await get_ar_config()
    orders = await db.sales_orders.find(
        {"customer_id": customer_id}, {"_id": 0}
    ).to_list(5000)

    items: List[Dict[str, Any]] = []
    totals = {**_empty_buckets(), "total": 0.0, "overdue": 0.0, "denda": 0.0}
    for o in orders:
        outstanding = _eligible_outstanding(o)
        if outstanding is None:
            continue
        created = parse_dt(o.get("created_at")) or now
        due = created + timedelta(days=term_days(customer, o))
        days_late = (now - due).days
        bucket = _bucket(days_late)
        denda = _denda_estimate(outstanding, days_late, cfg)
        items.append({
            "order_id": o.get("id"),
            "order_number": o.get("number") or o.get("id"),
            "grand_total": round(order_grand_total(o), 2),
            "paid_total": round(order_paid(o), 2),
            "outstanding": outstanding,
            "due_date": due.date().isoformat(),
            "days_late": days_late,
            "bucket": bucket,
            "overdue": days_late > 0,
            "denda_estimate": denda,
            "payment_status": o.get("payment_status") or "unpaid",
            "created_at": o.get("created_at"),
        })
        totals[bucket] = round(totals[bucket] + outstanding, 2)
        totals["total"] = round(totals["total"] + outstanding, 2)
        totals["denda"] = round(totals["denda"] + denda, 2)
        if days_late > 0:
            totals["overdue"] = round(totals["overdue"] + outstanding, 2)
    items.sort(key=lambda r: r["days_late"], reverse=True)

    return {
        "customer_id": customer["id"],
        "customer_name": customer.get("name", ""),
        "credit_limit": round(float(customer.get("credit_limit", 0) or 0), 2),
        "deposit_balance": round(float(customer.get("deposit_balance", 0) or 0), 2),
        "config": cfg,
        "totals": totals,
        "items": items,
    }
