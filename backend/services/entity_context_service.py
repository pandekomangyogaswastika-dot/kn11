"""F0-A — Entity identity & context helper (Multi-Entity foundation).

Sumber tunggal untuk:
- Default & enrichment skema entitas (currency, coa_template, numbering, incentive_payer).
- Membangun "entity context" user (home + allowed + active) untuk auth/me & switcher.

MODEL 1 (silo selling): sales/warehouse terkunci ke 1 entitas; admin/manager
boleh lintas-entitas (oversight). SO selalu dibukukan atas entitas sales.
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import now_iso

PRIMARY_ENTITY_ID = "ent_ksc"

# Role yang boleh mengoperasikan SEMUA entitas (oversight lintas-PT)
CROSS_ENTITY_ROLES = {"admin", "manager"}

# Default field entitas (enrichment idempotent untuk record lama)
ENTITY_DEFAULTS = {
    "currency": "IDR",
    "parent_entity_id": "",        # untuk konsolidasi grup (fase lanjut)
    "is_group": False,
    "coa_template": "id_standard", # template CoA saat provisioning
    "fiscal_year_start": "01-01",
    "incentive_payer": "sales_entity",  # Model 1: penanggung insentif = entitas SO (=entitas sales)
    "numbering_scheme": "per_entity_prefix",  # nomor: CODE/PREFIX-NNNNN
}


def entity_defaults() -> Dict[str, Any]:
    return dict(ENTITY_DEFAULTS)


def is_pkp(entity: Dict[str, Any]) -> bool:
    """Status PKP entitas (driver PPN) — diturunkan dari default_tax_mode."""
    return (entity or {}).get("default_tax_mode") == "ppn"


async def all_active_entity_ids() -> List[str]:
    rows = await db.business_entities.find(
        {"status": "active"}, {"_id": 0, "id": 1}).to_list(200)
    return [r["id"] for r in rows]


def resolve_allowed_entities(role: str, home_entity_id: str,
                             all_ids: List[str]) -> List[str]:
    """Tentukan daftar entitas yang boleh dioperasikan user (Model 1)."""
    if role in CROSS_ENTITY_ROLES:
        return list(all_ids) or [home_entity_id]
    return [home_entity_id]


async def entity_summaries(entity_ids: List[str]) -> List[Dict[str, Any]]:
    """Ringkasan entitas untuk switcher/FE (subset field aman)."""
    rows = await db.business_entities.find(
        {"id": {"$in": entity_ids}}, {"_id": 0}).to_list(200)
    out = []
    for e in rows:
        out.append({
            "id": e["id"],
            "code": e.get("doc_prefix") or e.get("short_name") or e["id"],
            "name": e.get("legal_name") or e.get("short_name") or e["id"],
            "short_name": e.get("short_name", ""),
            "type": e.get("type", ""),
            "is_pkp": is_pkp(e),
            "currency": e.get("currency", "IDR"),
            "status": e.get("status", "active"),
        })
    # urutkan sesuai urutan entity_ids
    order = {eid: i for i, eid in enumerate(entity_ids)}
    out.sort(key=lambda x: order.get(x["id"], 999))
    return out


async def build_entity_context(user: Dict[str, Any],
                               requested_entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Bangun konteks entitas untuk user (dipakai login, /auth/me, /auth/context).

    - home_entity_id  : entitas kerja/payroll user.
    - allowed_entity_ids : entitas yang boleh dioperasikan (Model 1).
    - active_entity_id : entitas aktif (header X-Entity-Id jika valid, else home).
    - entities : ringkasan entitas yang diizinkan (untuk switcher).
    - can_switch_entity : true bila >1 entitas diizinkan.
    """
    role = user.get("role", "")
    all_ids = await all_active_entity_ids()
    home = user.get("home_entity_id") or PRIMARY_ENTITY_ID
    allowed = user.get("allowed_entity_ids") or resolve_allowed_entities(role, home, all_ids)
    # active = requested bila valid & diizinkan, else home (atau allowed pertama)
    if requested_entity_id and requested_entity_id in allowed:
        active = requested_entity_id
    else:
        active = home if home in allowed else (allowed[0] if allowed else home)
    return {
        "home_entity_id": home,
        "allowed_entity_ids": allowed,
        "active_entity_id": active,
        "can_switch_entity": len(allowed) > 1,
        "entities": await entity_summaries(allowed),
    }


# ─── Migrasi idempotent (dipanggil bootstrap) ────────────────────────────────

async def ensure_entity_defaults() -> int:
    """Lengkapi field default pada entitas yang belum punya (idempotent)."""
    changed = 0
    async for e in db.business_entities.find({}, {"_id": 0}):
        patch = {k: v for k, v in ENTITY_DEFAULTS.items() if k not in e}
        if patch:
            patch["updated_at"] = now_iso()
            await db.business_entities.update_one({"id": e["id"]}, {"$set": patch})
            changed += 1
    return changed


async def ensure_user_entities() -> int:
    """Pastikan setiap user punya home_entity_id + allowed_entity_ids (idempotent).

    Default aman: home = PRIMARY_ENTITY_ID; allowed sesuai role.
    Distribusi demo (sales3 → Kanda) di-set oleh seed, bukan migrasi ini.
    """
    all_ids = await all_active_entity_ids() or [PRIMARY_ENTITY_ID]
    changed = 0
    async for u in db.users.find({}, {"_id": 0, "id": 1, "role": 1,
                                      "home_entity_id": 1, "allowed_entity_ids": 1}):
        patch: Dict[str, Any] = {}
        home = u.get("home_entity_id")
        if not home:
            home = PRIMARY_ENTITY_ID
            patch["home_entity_id"] = home
        if not u.get("allowed_entity_ids"):
            patch["allowed_entity_ids"] = resolve_allowed_entities(u.get("role", ""), home, all_ids)
        if patch:
            patch["updated_at"] = now_iso()
            await db.users.update_one({"id": u["id"]}, {"$set": patch})
            changed += 1
    return changed
