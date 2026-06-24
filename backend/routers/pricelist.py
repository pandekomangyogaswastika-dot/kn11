"""F1a — Pricelist per-entitas router (harga jual per-PT, histori & tanggal efektif).

Akses: permission module "pricelist" (admin/manager: view+manage; sales: view).
Kontrak respons: list = ARRAY langsung (records), grid = objek {rows,...}.
Koleksi `entity_prices` SCOPED via entity_id (entity_scope).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Query

from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access
from schemas import EntityPriceCreate, EntityPricePatch
from services import pricelist_service as svc

router = APIRouter(prefix="/api")


@router.get("/pricelist")
async def pricelist_grid(request: Request, entity_id: Optional[str] = Query(None),
                         search: str = "") -> Dict[str, Any]:
    """Grid pricelist: satu baris per produk (harga global + harga entitas current)."""
    await require_permission(request, "pricelist", "view")
    ctx = await entity_ctx(request)
    eid = entity_id or ctx.active_entity_id
    if eid not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
    rows = await svc.pricelist_grid(eid, search=search)
    return {"entity_id": eid, "rows": rows, "count": len(rows)}


@router.get("/pricelist/records")
async def pricelist_records(request: Request, product_id: str = None,
                            entity_id: str = None) -> List[Dict[str, Any]]:
    """Histori harga (semua record) ter-scope entitas, filter opsional per produk."""
    await require_permission(request, "pricelist", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope("entity_prices", {}, ctx, entity_id)
    return await svc.list_records(scope, product_id=product_id)


@router.post("/pricelist")
async def create_price(payload: EntityPriceCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "pricelist", "manage")
    ctx = await entity_ctx(request)
    eid = (payload.entity_id or "").strip() or ctx.active_entity_id
    if eid not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
    try:
        rec = await svc.create_price(payload.model_dump(), eid, actor.get("name", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "entity_price_created", "entity_price", rec["id"], {
        "entity_id": eid, "product": rec.get("product_name"),
        "sell_price": rec.get("sell_price"), "valid_from": rec.get("valid_from"),
    })
    return rec


@router.patch("/pricelist/{price_id}")
async def patch_price(price_id: str, payload: EntityPricePatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "pricelist", "manage")
    ctx = await entity_ctx(request)
    rec = await svc.get_record(price_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Harga tidak ditemukan")
    assert_entity_access(rec, "entity_prices", ctx)
    try:
        updated = await svc.patch_price(price_id, payload.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "entity_price_updated", "entity_price", price_id,
                payload.model_dump(exclude_none=True))
    return updated


@router.delete("/pricelist/{price_id}")
async def delete_price(price_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "pricelist", "manage")
    ctx = await entity_ctx(request)
    rec = await svc.get_record(price_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Harga tidak ditemukan")
    assert_entity_access(rec, "entity_prices", ctx)
    try:
        res = await svc.deactivate_price(price_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "entity_price_deactivated", "entity_price", price_id,
                {"product": rec.get("product_name")})
    return res
