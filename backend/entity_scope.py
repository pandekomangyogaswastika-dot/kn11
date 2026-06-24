"""F0-B — Entity scoping core (Multi-Entity foundation).

Lapisan TERPUSAT agar semua modul (kini & nanti) sadar-entitas tanpa menulis
ulang logika. Berisi:
- **Scope Registry**: koleksi → nama field entitas (atau SHARED).
- **EntityContext** dependency: resolve entitas aktif dari user + header X-Entity-Id.
- **scope_query / stamp_entity**: helper query & tulis.

Pakai di endpoint:
    ctx = Depends(entity_ctx)                  # konteks entitas
    q = apply_entity_scope("sales_orders", {...}, ctx)  # filter otomatis
    doc = stamp_entity(doc, "sales_orders", ctx)  # stamp saat create
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fastapi import Request, HTTPException

from dependencies import current_user
from services.entity_context_service import (
    PRIMARY_ENTITY_ID, CROSS_ENTITY_ROLES, resolve_allowed_entities,
    all_active_entity_ids,
)

# ─── SCOPE REGISTRY ──────────────────────────────────────────────────────────
# Field entitas per koleksi. Nilai None = SHARED (tidak di-scope).
SHARED = None
SCOPE_FIELD: Dict[str, Optional[str]] = {
    # Inventory: pakai owner_entity_id (semantik kepemilikan, dukung konsinyasi)
    "inventory_rolls": "owner_entity_id",
    "inventory_balances": "owner_entity_id",
    "inventory_movements": "owner_entity_id",
    # SHARED / global (tidak di-scope)
    "uoms": SHARED,
    "document_templates": SHARED,
    "products": SHARED,             # definisi SKU bersama (D1a) — kepemilikan via stok
    "product_templates": SHARED,    # F1b — template katalog (induk varian), SHARED lintas-entitas
    "product_categories": SHARED,
    "business_entities": SHARED,
    "users": SHARED,
    "sessions": SHARED,
    "permission_settings": SHARED,
    "system_settings": SHARED,
    "payment_terms": SHARED,
    "number_sequences": SHARED,
    "counters": SHARED,
    "user_onboarding": SHARED,
    "notifications": SHARED,        # per-user, bukan per-entitas
    # F0-E: Chart of Accounts = SHARED by-code (template bersama). Buku & saldo
    # terpisah per-PT hidup di `journal_entries.entity_id` (bukan di master CoA).
    "gl_accounts": SHARED,
}
DEFAULT_FIELD = "entity_id"

# Koleksi yang WAJIB ter-scope (untuk gate kepatuhan F0-C). Sisanya SHARED.
SCOPED_COLLECTIONS = {
    "sales_orders", "sales_returns", "special_orders", "price_approvals",
    "ar_receipts", "cash_transactions", "bank_accounts", "journal_entries",
    "tax_invoices", "input_tax_invoices",
    "purchase_orders", "purchase_requisitions", "rfqs", "vendor_bills",
    "landed_costs", "incentive_rates", "customers", "suppliers",
    "inventory_rolls", "inventory_balances", "inventory_movements",
    "wms_tasks", "shipments", "qc_inspections",
    "entity_prices",
}


def field_for(collection: str) -> Optional[str]:
    """Field entitas untuk koleksi. None bila SHARED."""
    if collection in SCOPE_FIELD:
        return SCOPE_FIELD[collection]
    return DEFAULT_FIELD


# ─── EntityContext ───────────────────────────────────────────────────────────
@dataclass
class EntityContext:
    user: Dict[str, Any]
    active_entity_id: str
    allowed_entity_ids: List[str] = field(default_factory=list)
    view_all: bool = False  # cross-entity "Semua Entitas" mode (header X-Entity-Id: all)

    @property
    def is_cross_entity(self) -> bool:
        return self.user.get("role") in CROSS_ENTITY_ROLES

    def can_access(self, entity_id: str) -> bool:
        return entity_id in self.allowed_entity_ids


async def entity_ctx(request: Request) -> EntityContext:
    """FastAPI dependency: resolve entitas aktif untuk request."""
    user = await current_user(request)
    home = user.get("home_entity_id") or PRIMARY_ENTITY_ID
    role = user.get("role", "")
    if role in CROSS_ENTITY_ROLES:
        # admin/manager: akses dinamis ke SEMUA entitas aktif (termasuk yang baru dibuat).
        all_ids = await all_active_entity_ids()
        allowed = resolve_allowed_entities(role, home, all_ids)
    else:
        allowed = user.get("allowed_entity_ids") or [home]
    requested = request.headers.get("X-Entity-Id")
    view_all = False
    if requested == "all" and user.get("role") in CROSS_ENTITY_ROLES:
        # mode oversight lintas-PT: tulis tetap ke 'home', baca = semua allowed.
        view_all = True
        active = home if home in allowed else (allowed[0] if allowed else home)
    elif requested and requested in allowed:
        active = requested
    else:
        active = home if home in allowed else (allowed[0] if allowed else home)
    return EntityContext(user=user, active_entity_id=active,
                         allowed_entity_ids=allowed, view_all=view_all)


# ─── Helper query & tulis ────────────────────────────────────────────────────
def apply_entity_scope(collection: str, query: Optional[Dict[str, Any]], ctx: EntityContext,
                       mode: str = "active") -> Dict[str, Any]:
    """Suntik filter entitas ke query.

    mode="active"  → hanya entitas aktif (default; isolasi ketat).
    mode="allowed" → semua entitas yang diizinkan (dashboard lintas-PT).
    SHARED collection → query tidak disentuh.
    """
    q = dict(query or {})
    fld = field_for(collection)
    if fld is None:
        return q
    if mode == "allowed":
        q[fld] = {"$in": ctx.allowed_entity_ids}
    else:
        q[fld] = ctx.active_entity_id
    return q


def stamp_entity(doc: Dict[str, Any], collection: str, ctx: EntityContext) -> Dict[str, Any]:
    """Set field entitas saat create (jika belum ada)."""
    fld = field_for(collection)
    if fld is not None and not doc.get(fld):
        doc[fld] = ctx.active_entity_id
    return doc


def assert_entity_access(doc: Dict[str, Any], collection: str, ctx: EntityContext) -> None:
    """Cegah akses lintas-entitas (anti-IDOR) untuk GET/{id}."""
    fld = field_for(collection)
    if fld is None or not doc:
        return
    ent = doc.get(fld)
    if ent and ent not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan untuk entitas ini")


def resolve_list_scope(collection: str, query: Optional[Dict[str, Any]], ctx: EntityContext,
                       entity_id_param: Optional[str] = None) -> Dict[str, Any]:
    """Logika scope LIST yang baku & backward-compatible.

    - entity_id_param == "all" & role lintas-entitas → semua entitas diizinkan.
    - entity_id_param eksplisit → harus ∈ allowed (else 403), filter ke entitas itu.
    - tidak ada param → scope ke entitas AKTIF (isolasi default).
    """
    q = dict(query or {})
    fld = field_for(collection)
    if fld is None:
        return q
    if entity_id_param == "all":
        if ctx.is_cross_entity:
            q[fld] = {"$in": ctx.allowed_entity_ids}
        else:
            q[fld] = ctx.active_entity_id
    elif entity_id_param:
        if entity_id_param not in ctx.allowed_entity_ids:
            raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
        q[fld] = entity_id_param
    else:
        if getattr(ctx, "view_all", False):
            q[fld] = {"$in": ctx.allowed_entity_ids}
        else:
            q[fld] = ctx.active_entity_id
    return q


def resolve_scope_ids(ctx: EntityContext, entity_id_param: Optional[str] = None) -> List[str]:
    """Daftar entity_id dalam cakupan baca. Dipakai koleksi yang punya record
    'all' (grup) yang harus selalu terlihat (mis. kas_besar / akun bank grup)."""
    if entity_id_param == "all":
        return list(ctx.allowed_entity_ids) if ctx.is_cross_entity else [ctx.active_entity_id]
    if entity_id_param:
        if entity_id_param not in ctx.allowed_entity_ids:
            raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
        return [entity_id_param]
    if getattr(ctx, "view_all", False):
        return list(ctx.allowed_entity_ids)
    return [ctx.active_entity_id]
