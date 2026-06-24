"""Emergent Object Storage wrapper (Sub-fase 1.7).

Helper upload/download attachment (bukti) yang dapat dipakai ulang oleh banyak
modul (price_approvals sekarang; sales_returns nanti). DB tetap source-of-truth
referensi file; storage tidak punya delete API → soft-delete dilakukan di DB.

Kontrak nyata: semua akses file lewat backend (tidak ada presigned URL).
"""
import asyncio
import logging
import os
import uuid

import requests

logger = logging.getLogger("storage_service")

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "kn7"

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf",
}
MIME_BY_EXT = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "gif": "image/gif", "pdf": "application/pdf",
}

_storage_key = None


def _emergent_key() -> str:
    return os.environ.get("EMERGENT_LLM_KEY", "")


def _init_sync():
    global _storage_key
    if _storage_key:
        return _storage_key
    if not _emergent_key():
        raise RuntimeError("EMERGENT_LLM_KEY belum dikonfigurasi")
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": _emergent_key()}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    logger.info("[storage_service] storage_key initialized")
    return _storage_key


def _reset_key():
    global _storage_key
    _storage_key = None


def _put_sync(path: str, data: bytes, content_type: str) -> dict:
    for attempt in range(2):
        key = _init_sync()
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data, timeout=120,
        )
        if resp.status_code == 403 and attempt == 0:
            _reset_key()
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("Upload gagal setelah retry")


def _get_sync(path: str):
    for attempt in range(2):
        key = _init_sync()
        resp = requests.get(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key}, timeout=60,
        )
        if resp.status_code == 403 and attempt == 0:
            _reset_key()
            continue
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
    raise RuntimeError("Download gagal setelah retry")


def ext_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if filename and "." in filename else "bin"


def build_path(scope: str, ext: str) -> str:
    """Path object tanpa leading slash: kn7/{scope}/{uuid}.{ext}."""
    return f"{APP_NAME}/{scope}/{uuid.uuid4().hex}.{ext}"


def validate_upload(filename: str, content_type: str, size: int) -> str:
    """Validasi ekstensi/MIME/ukuran. Mengembalikan content_type ter-normalisasi
    atau melempar ValueError dengan pesan ramah."""
    ext = ext_of(filename)
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct not in ALLOWED_MIME:
        ct = MIME_BY_EXT.get(ext, "")
    if ct not in ALLOWED_MIME:
        raise ValueError("Tipe file tidak didukung. Hanya JPG, PNG, WEBP, GIF, atau PDF.")
    if size > MAX_FILE_BYTES:
        raise ValueError("Ukuran file melebihi batas 10 MB.")
    if size <= 0:
        raise ValueError("File kosong.")
    return ct


async def init_storage():
    return await asyncio.to_thread(_init_sync)


async def put_object(path: str, data: bytes, content_type: str) -> dict:
    return await asyncio.to_thread(_put_sync, path, data, content_type)


async def get_object(path: str):
    return await asyncio.to_thread(_get_sync, path)
