from datetime import datetime, timezone
from typing import Any, Dict, Optional
import hashlib
import re
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def next_doc_number(collection: str, field: str, prefix: str, width: int = 5,
                          entity_id: Optional[str] = None,
                          scheme: str = "per_entity_prefix") -> str:
    """Generate nomor dokumen berurutan (deletion-safe).

    Dua mode:
    - **Legacy/shared** (`entity_id=None` atau `scheme="shared"`): pindai nomor
      tertinggi untuk `prefix` lalu +1. Format `PREFIX-NNNNN` (kompatibel data lama).
    - **Per-entitas** (`entity_id` di-set, `scheme="per_entity_prefix"`): sequence
      atomik per (entity_id, doc_type) di koleksi `number_sequences`
      (`find_one_and_update($inc)` → anti-duplikat & hemat scan). Format
      `{CODE}/{PREFIX}NNNNN`, mis. `KSC/SO-00001`, `KANDA/SO-00001`.

    Contoh: next_doc_number("purchase_orders","po_number","PO-",entity_id="ent_ksc") -> "KSC/PO-00010".
    """
    from db import db
    if entity_id is None or entity_id == "all" or scheme == "shared":
        coll = db[collection]
        pat = re.compile(r"(\d+)\s*$")
        n = 0
        async for d in coll.find(
            {field: {"$regex": f"^{re.escape(prefix)}"}}, {"_id": 0, field: 1}
        ):
            val = d.get(field)
            if isinstance(val, str):
                m = pat.search(val)
                if m:
                    n = max(n, int(m.group(1)))
        return f"{prefix}{n + 1:0{width}d}"

    # ── Mode per-entitas: sequence atomik ──────────────────────────────────
    from pymongo import ReturnDocument
    doc_type = prefix.rstrip("-/").upper() or prefix
    code = await entity_code(entity_id)
    key = {"entity_id": entity_id, "doc_type": doc_type}
    # Inisialisasi sekali dari nomor tertinggi existing (legacy & baru) agar tak tabrakan.
    if not await db.number_sequences.find_one(key):
        seed_no = await _max_existing_number(collection, field, prefix, entity_id)
        await db.number_sequences.update_one(
            key,
            {"$setOnInsert": {**key, "prefix": prefix, "last_no": seed_no,
                              "created_at": now_iso()}},
            upsert=True,
        )
    seq = await db.number_sequences.find_one_and_update(
        key,
        {"$inc": {"last_no": 1}, "$set": {"updated_at": now_iso()}},
        return_document=ReturnDocument.AFTER,
    )
    return f"{code}/{prefix}{seq['last_no']:0{width}d}"


_ENTITY_CODE_CACHE: Dict[str, str] = {}


async def entity_code(entity_id: str) -> str:
    """Kode pendek entitas untuk nomor dokumen (doc_prefix → short_name → upper id)."""
    if entity_id in _ENTITY_CODE_CACHE:
        return _ENTITY_CODE_CACHE[entity_id]
    from db import db
    ent = await db.business_entities.find_one(
        {"id": entity_id}, {"_id": 0, "doc_prefix": 1, "short_name": 1, "code": 1}) or {}
    code = (ent.get("doc_prefix") or ent.get("code") or ent.get("short_name")
            or (entity_id or "").replace("ent_", "").upper() or "ENT")
    _ENTITY_CODE_CACHE[entity_id] = code
    return code


async def _max_existing_number(collection: str, field: str, prefix: str,
                               entity_id: str, scope_field: str = "entity_id") -> int:
    """Nomor seri tertinggi existing utk (entitas, prefix) — match legacy & baru."""
    from db import db
    pat = re.compile(r"(\d+)\s*$")
    n = 0
    q = {field: {"$regex": re.escape(prefix)}, scope_field: entity_id}
    async for d in db[collection].find(q, {"_id": 0, field: 1}):
        val = d.get(field)
        if isinstance(val, str):
            m = pat.search(val)
            if m:
                n = max(n, int(m.group(1)))
    return n


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def timeline_entry(event: str, label: str, actor: str = "", note: str = "") -> Dict[str, Any]:
    """Entri riwayat/timeline standar (dipakai PO approval history, dll)."""
    return {"event": event, "label": label, "actor": actor or "Sistem",
            "at": now_iso(), "note": note or ""}


def _coerce(value: Any) -> Any:
    """Recursively make a MongoDB document JSON-serializable."""
    try:
        from bson import ObjectId
        if isinstance(value, ObjectId):
            return str(value)
    except ImportError:
        pass
    if isinstance(value, dict):
        return {k: _coerce(v) for k, v in value.items() if k != "_id"}
    if isinstance(value, list):
        return [_coerce(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # datetime, etc.
    try:
        return str(value)
    except Exception:
        return None


def safe_doc(doc: Optional[Any]) -> Optional[Any]:
    """Recursively remove _id fields and convert ObjectId to str."""
    if doc is None:
        return None
    return _coerce(doc)


def hash_password(password: str) -> str:
    return hashlib.sha256(f"kain-nusantara::{password}".encode()).hexdigest()


# ── Multi-Entity (Fase 0) ─────────────────────────────────────────────────────
# Entitas legal utama grup. Dipakai sebagai default entity_id untuk data lama
# (backfill) & transaksi baru bila konteks entitas belum dipilih.
DEFAULT_ENTITY_ID = "ent_ksc"  # PT Kain Suka Cita
