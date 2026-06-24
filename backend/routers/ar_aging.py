"""AR Aging router (EPIC7-A) — Piutang / Accounts Receivable Aging.

Akses: admin/manager (finance). Respons: OBJEK/ARRAY telanjang (kontrak KN3).
Read-only/derived — tidak memodifikasi data (denda = estimasi informasional).
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, Query, HTTPException

from dependencies import require_role
from services import ar_aging_service

router = APIRouter(prefix="/api")


@router.get("/ar/aging")
async def ar_aging(
    request: Request,
    entity_id: Optional[str] = Query(None),
    sales_id: Optional[str] = Query(None),
    as_of: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Ringkasan aging piutang (totals per-bucket + baris per-customer)."""
    await require_role(request, ["manager"])
    return await ar_aging_service.aging_report(entity_id=entity_id, sales_id=sales_id, as_of=as_of)


@router.get("/ar/aging/{customer_id}")
async def ar_aging_detail(customer_id: str, request: Request,
                          as_of: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Rincian aging per-order untuk satu customer (drill-down)."""
    await require_role(request, ["manager"])
    detail = await ar_aging_service.customer_aging_detail(customer_id, as_of=as_of)
    if detail is None:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    return detail
