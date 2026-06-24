"""F0-F — Provisioning entitas baru (wizard "Add New Entity").

Membuat entitas legal siap-pakai dalam satu langkah:
  - validasi short_name & doc_prefix unik (doc_prefix dipakai untuk nomor dokumen),
  - lengkapi default config entitas (numbering_scheme, currency, fiscal year, dll),
  - pastikan bagan akun (CoA) tersedia — CoA SHARED by-code, buku terpisah via
    journal_entries.entity_id (lihat gl_service),
  - siapkan penanda config override per-entitas.
Penomoran (CODE/PREFIX-NNNNN) & buku besar otomatis aktif begitu entitas dipakai.
"""
import re
from typing import Any, Dict

from db import db
from core_utils import new_id, now_iso
from services.entity_context_service import ENTITY_DEFAULTS
from services import gl_service


def _slug_prefix(short_name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]", "", short_name or "").upper()
    return s[:6] or "ENT"


async def provision_entity(payload: Dict[str, Any], actor_name: str) -> Dict[str, Any]:
    short_name = (payload.get("short_name") or "").strip()
    legal_name = (payload.get("legal_name") or "").strip()
    if not short_name or not legal_name:
        raise ValueError("legal_name dan short_name wajib diisi.")
    if await db.business_entities.find_one({"short_name": short_name}, {"_id": 0}):
        raise ValueError(f"Short name '{short_name}' sudah digunakan.")

    doc_prefix = (payload.get("doc_prefix") or "").strip().upper() or _slug_prefix(short_name)
    if await db.business_entities.find_one({"doc_prefix": doc_prefix}, {"_id": 0}):
        raise ValueError(f"Kode dokumen (doc_prefix) '{doc_prefix}' sudah dipakai entitas lain.")

    entity: Dict[str, Any] = dict(ENTITY_DEFAULTS)
    entity.update({k: v for k, v in payload.items() if v is not None})
    entity.update({
        "id": new_id("ent"),
        "short_name": short_name,
        "legal_name": legal_name,
        "doc_prefix": doc_prefix,
        "status": "active",
        "created_by": actor_name,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    await db.business_entities.insert_one(entity)

    # Bagan akun bersama (idempotent) — semua entitas pakai chart yang sama by-code.
    coa_added = await gl_service.seed_default_coa()
    # Penanda config override per-entitas (efektif via get_effective_settings).
    await db.system_settings.update_one(
        {"scope": entity["id"]},
        {"$setOnInsert": {"scope": entity["id"], "created_at": now_iso()},
         "$set": {"updated_at": now_iso()}},
        upsert=True,
    )

    entity.pop("_id", None)
    return {
        "entity": entity,
        "provisioning": {
            "doc_prefix": doc_prefix,
            "numbering_scheme": entity.get("numbering_scheme"),
            "is_pkp": entity.get("default_tax_mode") == "ppn",
            "coa_accounts_added": coa_added,
            "coa_shared": True,
            "config_override_created": True,
        },
    }
