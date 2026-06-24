"""Bank/Cash Accounts router (EPIC7-B) — multi-akun kas & bank + rekonsiliasi.

Akses: permission module "cash" (admin/manager). Respons OBJEK/ARRAY telanjang.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Request, Query, HTTPException

from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_scope_ids
from schemas import BankAccountCreate, BankAccountUpdate, ReconcilePayload
from services import bank_service

router = APIRouter(prefix="/api")


@router.get("/bank-accounts")
async def list_bank_accounts(request: Request, entity_id: str = Query(None)) -> List[Dict[str, Any]]:
    """Daftar akun kas/bank + saldo terhitung."""
    await require_permission(request, "cash", "view")
    ctx = await entity_ctx(request)
    entities = resolve_scope_ids(ctx, entity_id)
    # akun grup (entity_id="all") selalu terlihat lintas-entitas.
    scope = {"$or": [{"entity_id": {"$in": entities}}, {"entity_id": "all"}]}
    return await bank_service.list_accounts(scope=scope)


@router.post("/bank-accounts")
async def create_bank_account(payload: BankAccountCreate, request: Request) -> Dict[str, Any]:
    """Buat akun kas/bank baru."""
    actor = await require_permission(request, "cash", "create")
    try:
        acc = await bank_service.create_account(payload, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "bank_account_created", "bank_account", acc["id"],
                {"name": acc["name"], "type": acc["account_type"]})
    return acc


@router.patch("/bank-accounts/{account_id}")
async def patch_bank_account(account_id: str, payload: BankAccountUpdate, request: Request) -> Dict[str, Any]:
    """Ubah / nonaktifkan akun kas/bank."""
    actor = await require_permission(request, "cash", "create")
    acc = await bank_service.update_account(account_id, payload.model_dump())
    if acc is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    await audit(actor["name"], "bank_account_updated", "bank_account", account_id, {})
    return acc


@router.get("/bank-accounts/{account_id}/ledger")
async def bank_account_ledger(account_id: str, request: Request) -> Dict[str, Any]:
    """Buku besar (ledger) akun: transaksi + running balance."""
    await require_permission(request, "cash", "view")
    led = await bank_service.account_ledger(account_id)
    if led is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    return led


@router.post("/cash-transactions/{txn_id}/reconcile")
async def reconcile_cash_transaction(txn_id: str, payload: ReconcilePayload, request: Request) -> Dict[str, Any]:
    """Tandai transaksi kas sebagai terekonsiliasi / belum."""
    actor = await require_permission(request, "cash", "create")
    txn = await bank_service.reconcile_txn(txn_id, payload.reconciled)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    await audit(actor["name"], "cash_transaction_reconciled", "cash_transaction", txn_id,
                {"reconciled": payload.reconciled})
    return txn
