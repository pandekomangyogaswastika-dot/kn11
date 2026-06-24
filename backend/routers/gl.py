"""EPIC7-C — Chart of Accounts + General Ledger router.

Akses: permission module "accounting" (admin/manager). Respons OBJEK/ARRAY
telanjang (kontrak KN3). Jurnal otomatis diturunkan dari SSOT (sales_orders,
cash_transactions) via /api/gl/sync — idempotent.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Query, HTTPException

from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access
from schemas_finance import (
    GLAccountCreate, GLAccountUpdate, JournalEntryCreate,
)
from services import gl_service

router = APIRouter(prefix="/api")


async def _gl_scope(request: Request, entity_id: Optional[str]) -> Dict[str, Any]:
    """Fragmen filter entitas untuk buku/jurnal (default: entitas aktif)."""
    ctx = await entity_ctx(request)
    return resolve_list_scope("journal_entries", {}, ctx, entity_id)


# ─── Chart of Accounts ───────────────────────────────────────────────────────

@router.get("/gl/accounts")
async def list_gl_accounts(request: Request, active_only: bool = Query(False)) -> List[Dict[str, Any]]:
    """Daftar bagan akun (Chart of Accounts)."""
    await require_permission(request, "accounting", "view")
    return await gl_service.list_accounts(active_only=active_only)


@router.post("/gl/accounts")
async def create_gl_account(payload: GLAccountCreate, request: Request) -> Dict[str, Any]:
    """Buat akun baru."""
    actor = await require_permission(request, "accounting", "manage")
    try:
        acc = await gl_service.create_account(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "gl_account_created", "gl_account", acc["code"],
                {"name": acc["name"], "type": acc["type"]})
    return acc


@router.patch("/gl/accounts/{code}")
async def update_gl_account(code: str, payload: GLAccountUpdate, request: Request) -> Dict[str, Any]:
    """Ubah / nonaktifkan akun."""
    actor = await require_permission(request, "accounting", "manage")
    acc = await gl_service.update_account(code, payload.model_dump())
    if acc is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    await audit(actor["name"], "gl_account_updated", "gl_account", code, {})
    return acc


@router.delete("/gl/accounts/{code}")
async def delete_gl_account(code: str, request: Request) -> Dict[str, Any]:
    """Hapus akun non-sistem yang belum dipakai."""
    actor = await require_permission(request, "accounting", "manage")
    try:
        await gl_service.delete_account(code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "gl_account_deleted", "gl_account", code, {})
    return {"ok": True, "code": code}


@router.get("/gl/accounts/{code}/ledger")
async def gl_account_ledger(code: str, request: Request, as_of: Optional[str] = Query(None),
                            entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Buku besar 1 akun (mutasi + running balance) — per entitas."""
    await require_permission(request, "accounting", "view")
    scope = await _gl_scope(request, entity_id)
    led = await gl_service.account_ledger(code, as_of=as_of, scope=scope)
    if led is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    return led


# ─── Journal Entries ─────────────────────────────────────────────────────────

@router.get("/gl/journal")
async def list_journal(
    request: Request,
    source: Optional[str] = Query(None),
    account_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Daftar jurnal (filter sumber/akun/status) — ter-scope entitas."""
    await require_permission(request, "accounting", "view")
    scope = await _gl_scope(request, entity_id)
    return await gl_service.list_entries(source=source, account_code=account_code,
                                         status=status, scope=scope)


@router.post("/gl/journal")
async def create_journal(payload: JournalEntryCreate, request: Request) -> Dict[str, Any]:
    """Buat jurnal manual (double-entry seimbang) — ter-stamp entitas aktif."""
    actor = await require_permission(request, "accounting", "create")
    ctx = await entity_ctx(request)
    try:
        je = await gl_service.create_manual_entry(payload, actor, entity_id=ctx.active_entity_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "journal_entry_created", "journal_entry", je["id"],
                {"number": je["number"], "total": je["total_debit"]})
    return je


@router.get("/gl/journal/{entry_id}")
async def get_journal(entry_id: str, request: Request) -> Dict[str, Any]:
    """Detail satu jurnal."""
    await require_permission(request, "accounting", "view")
    ctx = await entity_ctx(request)
    je = await gl_service.get_entry(entry_id)
    if je is None:
        raise HTTPException(status_code=404, detail="Jurnal tidak ditemukan")
    assert_entity_access(je, "journal_entries", ctx)
    return je


@router.post("/gl/journal/{entry_id}/void")
async def void_journal(entry_id: str, request: Request) -> Dict[str, Any]:
    """Void jurnal manual."""
    actor = await require_permission(request, "accounting", "void")
    try:
        je = await gl_service.void_entry(entry_id, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if je is None:
        raise HTTPException(status_code=404, detail="Jurnal tidak ditemukan")
    await audit(actor["name"], "journal_entry_voided", "journal_entry", entry_id, {})
    return je


# ─── Sync (auto-posting) & Reports ───────────────────────────────────────────

@router.post("/gl/sync")
async def sync_journals(request: Request) -> Dict[str, Any]:
    """Posting otomatis (idempotent) dari SSOT yang belum berjurnal."""
    actor = await require_permission(request, "accounting", "manage")
    result = await gl_service.backfill_journals()
    await audit(actor["name"], "gl_sync", "journal_entry", "batch", result)
    return result


@router.get("/gl/trial-balance")
async def trial_balance(request: Request, as_of: Optional[str] = Query(None),
                        entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Neraca saldo (trial balance) — buku terpisah per entitas."""
    await require_permission(request, "accounting", "view")
    scope = await _gl_scope(request, entity_id)
    return await gl_service.trial_balance(as_of=as_of, scope=scope)


@router.get("/gl/summary")
async def gl_summary(request: Request, entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """KPI ringkas GL (jumlah jurnal, total debit/kredit, seimbang?) — per entitas."""
    await require_permission(request, "accounting", "view")
    scope = await _gl_scope(request, entity_id)
    return await gl_service.gl_summary(scope=scope)


@router.get("/gl/consolidation")
async def gl_consolidation(request: Request, as_of: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Konsolidasi Grup vs Per-PT — ringkasan P&L + neraca tiap entitas + gabungan.

    Memakai buku terpisah per entitas (F0-E). Cakupan = entitas yang diizinkan
    user (admin/manager lintas-PT = semua entitas aktif)."""
    await require_permission(request, "accounting", "view")
    ctx = await entity_ctx(request)
    return await gl_service.consolidation(ctx.allowed_entity_ids, as_of=as_of)
