"""Warehouse Transfer router: multi-warehouse transfer workflow with approval."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, Query
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc, next_doc_number
from schemas import TransferCreate, TransferApprove, TransferReject, TransferStatusUpdate, InterCompanyTransferCreate
from services.roll_service import (
    reserve_rolls_for_transfer, execute_ownership_transfer, release_transfer_rolls,
)

router = APIRouter(prefix="/api")


# Allowed status transitions
STATUS_TRANSITIONS = {
    "draft": ["waiting_approval", "cancelled"],
    "waiting_approval": ["approved", "rejected", "cancelled"],
    "approved": ["picking", "cancelled"],
    "picking": ["staging", "cancelled"],
    "staging": ["dispatched", "cancelled"],
    "dispatched": ["completed", "cancelled"],
    "completed": [],
    "rejected": [],
    "cancelled": []
}


def _validate_status_transition(current: str, new: str) -> bool:
    """Check if status transition is valid."""
    return new in STATUS_TRANSITIONS.get(current, [])


@router.get("/transfers")
async def list_transfers(
    request: Request,
    status: Optional[str] = Query(None),
    warehouse_id: Optional[str] = Query(None),
    transfer_kind: Optional[str] = Query(None)
) -> List[Dict[str, Any]]:
    """List all transfers with optional filtering by status, warehouse, or transfer_kind."""
    await require_permission(request, "transfer", "view")
    
    query_filter = {}
    if status:
        query_filter["status"] = status
    if transfer_kind:
        # record lama tanpa field → dianggap intra_entity
        if transfer_kind == "intra_entity":
            query_filter["transfer_kind"] = {"$ne": "inter_entity"}
        else:
            query_filter["transfer_kind"] = transfer_kind
    if warehouse_id:
        query_filter["$or"] = [
            {"source_warehouse_id": warehouse_id},
            {"dest_warehouse_id": warehouse_id}
        ]
    
    transfers = await db.warehouse_transfers.find(query_filter, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    # Enrich with warehouse/entity names and product details
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    entities = {e["id"]: e for e in await db.business_entities.find({}, {"_id": 0}).to_list(100)}
    
    def _ent_name(eid):
        e = entities.get(eid, {})
        return e.get("short_name") or e.get("legal_name") or (eid or "")
    
    for transfer in transfers:
        transfer["transfer_kind"] = transfer.get("transfer_kind", "intra_entity")
        transfer["source_warehouse_name"] = warehouses.get(transfer.get("source_warehouse_id"), {}).get("name", "")
        transfer["dest_warehouse_name"] = warehouses.get(transfer.get("dest_warehouse_id"), {}).get("name", "")
        transfer["source_entity_name"] = _ent_name(transfer.get("source_entity_id"))
        transfer["dest_entity_name"] = _ent_name(transfer.get("dest_entity_id"))
        for item in transfer.get("items", []):
            prod = products.get(item["product_id"], {})
            item.setdefault("sku", prod.get("sku", ""))
            item.setdefault("product_name", prod.get("name", ""))
    
    return transfers


@router.post("/transfers")
async def create_transfer(payload: TransferCreate, request: Request) -> Dict[str, Any]:
    """
    Create a new warehouse transfer.
    
    Default status: waiting_approval
    Requires permission: transfer.create
    """
    actor = await require_permission(request, "transfer", "create")
    
    # Validate warehouses exist
    source_wh = await db.warehouses.find_one({"id": payload.source_warehouse_id}, {"_id": 0})
    dest_wh = await db.warehouses.find_one({"id": payload.dest_warehouse_id}, {"_id": 0})
    
    if not source_wh:
        raise HTTPException(status_code=404, detail="Source warehouse tidak ditemukan")
    if not dest_wh:
        raise HTTPException(status_code=404, detail="Destination warehouse tidak ditemukan")
    if payload.source_warehouse_id == payload.dest_warehouse_id:
        raise HTTPException(status_code=400, detail="Source dan destination warehouse harus berbeda")
    
    # Validate products and items
    if not payload.items or len(payload.items) == 0:
        raise HTTPException(status_code=400, detail="Items tidak boleh kosong")
    
    for item in payload.items:
        prod = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if not prod:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} tidak ditemukan")
        if item.qty <= 0:
            raise HTTPException(status_code=400, detail="Qty harus lebih dari 0")
    
    # Generate transfer code (deletion-safe / max-based — P0-A)
    code = await next_doc_number("warehouse_transfers", "code", "TRF-")
    
    transfer = {
        "id": new_id("trn"),
        "code": code,
        "source_warehouse_id": payload.source_warehouse_id,
        "dest_warehouse_id": payload.dest_warehouse_id,
        "status": "waiting_approval",
        "items": [item.model_dump() for item in payload.items],
        "notes": payload.notes,
        "requested_by": payload.requested_by,
        "approved_by": None,
        "approved_at": None,
        "rejected_by": None,
        "rejected_at": None,
        "rejected_reason": None,
        "created_at": now_iso(),
        "updated_at": now_iso()
    }
    
    await db.warehouse_transfers.insert_one(transfer)
    await audit(actor["name"], "transfer_created", "transfer", transfer["id"], transfer)
    
    return safe_doc(transfer)


@router.post("/transfers/inter-company")
async def create_inter_company_transfer(payload: InterCompanyTransferCreate, request: Request) -> Dict[str, Any]:
    """Sub-fase 1.5 — Minta transfer kepemilikan antar-entitas (B→E) dari preview POS.

    Permission: order:create (dimulai oleh Sales sebagai bagian alur pemenuhan).
    Persetujuan B (transfer:approve) yang akan MEMINDAHKAN kepemilikan (KN_15 §7).
    Reservasi roll milik B (status=reserved, ref=transfer) agar tak dobel-jual.
    """
    actor = await require_permission(request, "order", "create")

    if payload.source_entity_id == payload.dest_entity_id:
        raise HTTPException(status_code=400, detail="Entitas sumber dan tujuan harus berbeda")
    src_ent = await db.business_entities.find_one({"id": payload.source_entity_id}, {"_id": 0})
    dst_ent = await db.business_entities.find_one({"id": payload.dest_entity_id}, {"_id": 0})
    if not src_ent:
        raise HTTPException(status_code=404, detail="Entitas sumber tidak ditemukan")
    if not dst_ent:
        raise HTTPException(status_code=404, detail="Entitas tujuan tidak ditemukan")
    if not payload.items:
        raise HTTPException(status_code=400, detail="Items tidak boleh kosong")

    transfer_id = new_id("trn")
    code = await next_doc_number("warehouse_transfers", "code", "TRF-")

    items_out: List[Dict[str, Any]] = []
    wh_ids: List[str] = []
    try:
        for it in payload.items:
            prod = await db.products.find_one({"id": it.product_id}, {"_id": 0})
            if not prod:
                raise HTTPException(status_code=404, detail=f"Produk {it.product_id} tidak ditemukan")
            if it.quantity <= 0:
                raise HTTPException(status_code=400, detail="Qty harus lebih dari 0")
            reserved = await reserve_rolls_for_transfer(
                it.product_id, payload.source_entity_id, it.quantity, transfer_id
            )
            roll_refs = [{
                "roll_id": r["id"], "roll_no": r.get("roll_no"), "lot": r.get("lot"),
                "warehouse_id": r.get("warehouse_id"), "length": float(r.get("length_remaining", 0) or 0),
            } for r in reserved]
            lots = sorted({r.get("lot") for r in reserved if r.get("lot")})
            for r in reserved:
                if r.get("warehouse_id"):
                    wh_ids.append(r["warehouse_id"])
            items_out.append({
                "product_id": it.product_id, "qty": round(it.quantity, 2), "unit": it.unit,
                "sku": prod.get("sku", ""), "product_name": prod.get("name", ""),
                "lots": lots, "rolls": roll_refs,
            })
    except HTTPException:
        # rollback reservasi parsial bila ada item gagal
        await release_transfer_rolls(transfer_id)
        raise

    primary_wh = wh_ids[0] if wh_ids else ""
    transfer = {
        "id": transfer_id,
        "code": code,
        "transfer_kind": "inter_entity",
        "source_entity_id": payload.source_entity_id,
        "dest_entity_id": payload.dest_entity_id,
        # Ownership-in-place (Sub-fase 1.5): gudang sumber = tujuan (tak ada pindah fisik)
        "source_warehouse_id": primary_wh,
        "dest_warehouse_id": primary_wh,
        "status": "waiting_approval",
        "items": items_out,
        "transfer_price": payload.transfer_price,
        "linked_order_id": payload.linked_order_id,
        "notes": payload.notes,
        "requested_by": payload.requested_by or actor["name"],
        "approved_by": None, "approved_at": None,
        "rejected_by": None, "rejected_at": None, "rejected_reason": None,
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.warehouse_transfers.insert_one(transfer)
    await audit(actor["name"], "inter_company_transfer_requested", "transfer", transfer_id, {
        "source": payload.source_entity_id, "dest": payload.dest_entity_id,
        "items": [{"product_id": i["product_id"], "qty": i["qty"]} for i in items_out],
        "linked_order_id": payload.linked_order_id,
    })
    return safe_doc(transfer)


@router.get("/transfers/{transfer_id}")
async def get_transfer_detail(transfer_id: str, request: Request) -> Dict[str, Any]:
    """Get detailed transfer information."""
    await require_permission(request, "transfer", "view")
    
    transfer = safe_doc(await db.warehouse_transfers.find_one({"id": transfer_id}, {"_id": 0}))
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer tidak ditemukan")
    
    # Enrich with warehouse and product details
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    
    transfer["source_warehouse_name"] = warehouses.get(transfer["source_warehouse_id"], {}).get("name", "")
    transfer["dest_warehouse_name"] = warehouses.get(transfer["dest_warehouse_id"], {}).get("name", "")
    
    for item in transfer.get("items", []):
        prod = products.get(item["product_id"], {})
        item["sku"] = prod.get("sku", "")
        item["product_name"] = prod.get("name", "")
    
    return transfer


@router.post("/transfers/{transfer_id}/approve")
async def approve_transfer(transfer_id: str, payload: TransferApprove, request: Request) -> Dict[str, Any]:
    """
    Approve a transfer.
    
    Status: waiting_approval → approved
    Requires permission: transfer.approve
    """
    actor = await require_permission(request, "transfer", "approve")
    
    transfer = await db.warehouse_transfers.find_one({"id": transfer_id}, {"_id": 0})
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer tidak ditemukan")
    
    if transfer["status"] != "waiting_approval":
        raise HTTPException(status_code=400, detail=f"Transfer tidak bisa diapprove (status: {transfer['status']})")
    
    # Sub-fase 1.5 — inter-company: APPROVE = pindahkan kepemilikan B→E (S3, 1 langkah) → status completed.
    if transfer.get("transfer_kind") == "inter_entity":
        result = await execute_ownership_transfer(transfer)
        updated = await db.warehouse_transfers.find_one_and_update(
            {"id": transfer_id},
            {"$set": {"status": "completed", "approved_by": payload.approved_by,
                      "approved_at": now_iso(), "ownership_moved": result, "updated_at": now_iso()}},
            projection={"_id": 0}, return_document=ReturnDocument.AFTER,
        )
        await audit(actor["name"], "inter_company_transfer_executed", "transfer", transfer_id,
                    {"approved_by": payload.approved_by, **result})
        return safe_doc(updated)

    updated = await db.warehouse_transfers.find_one_and_update(
        {"id": transfer_id},
        {
            "$set": {
                "status": "approved",
                "approved_by": payload.approved_by,
                "approved_at": now_iso(),
                "updated_at": now_iso()
            }
        },
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "transfer_approved", "transfer", transfer_id, {"approved_by": payload.approved_by})
    
    return safe_doc(updated)


@router.post("/transfers/{transfer_id}/reject")
async def reject_transfer(transfer_id: str, payload: TransferReject, request: Request) -> Dict[str, Any]:
    """
    Reject a transfer.
    
    Status: waiting_approval → rejected
    Requires permission: transfer.reject
    """
    actor = await require_permission(request, "transfer", "reject")
    
    transfer = await db.warehouse_transfers.find_one({"id": transfer_id}, {"_id": 0})
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer tidak ditemukan")
    
    if transfer["status"] != "waiting_approval":
        raise HTTPException(status_code=400, detail=f"Transfer tidak bisa direject (status: {transfer['status']})")
    
    # Sub-fase 1.5 — inter-company: lepas reservasi roll di entitas sumber.
    if transfer.get("transfer_kind") == "inter_entity":
        await release_transfer_rolls(transfer_id)

    updated = await db.warehouse_transfers.find_one_and_update(
        {"id": transfer_id},
        {
            "$set": {
                "status": "rejected",
                "rejected_by": payload.rejected_by,
                "rejected_at": now_iso(),
                "rejected_reason": payload.reason,
                "updated_at": now_iso()
            }
        },
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "transfer_rejected", "transfer", transfer_id, {"rejected_by": payload.rejected_by, "reason": payload.reason})
    
    return safe_doc(updated)


@router.post("/transfers/{transfer_id}/status")
async def update_transfer_status(transfer_id: str, payload: TransferStatusUpdate, request: Request) -> Dict[str, Any]:
    """
    Update transfer status (workflow progression).
    
    Valid transitions:
    - approved → picking
    - picking → staging
    - staging → dispatched
    - dispatched → completed
    - any → cancelled (requires cancel permission)
    
    Inventory impact:
    - dispatched: reduce source warehouse on_hand, increase in_transit
    - completed: reduce source in_transit, increase dest on_hand
    """
    actor = await require_permission(request, "transfer", "update")
    
    transfer = await db.warehouse_transfers.find_one({"id": transfer_id}, {"_id": 0})
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer tidak ditemukan")
    
    current_status = transfer["status"]
    new_status = payload.status
    
    # Validate transition
    if not _validate_status_transition(current_status, new_status):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition: {current_status} → {new_status}"
        )
    
    # Special handling for dispatched and completed
    if new_status == "dispatched":
        # Reduce source warehouse stock and set in_transit
        for item in transfer["items"]:
            balance = await db.inventory_balances.find_one({
                "product_id": item["product_id"],
                "warehouse_id": transfer["source_warehouse_id"]
            })
            if not balance or balance["available_qty"] < item["qty"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stok tidak cukup untuk {item['product_id']} di source warehouse"
                )
            
            # Update balance
            await db.inventory_balances.update_one(
                {"product_id": item["product_id"], "warehouse_id": transfer["source_warehouse_id"]},
                {
                    "$inc": {
                        "on_hand_qty": -item["qty"],
                        "available_qty": -item["qty"],
                        "in_transit_qty": item["qty"]
                    },
                    "$set": {"updated_at": now_iso()}
                }
            )
            
            # Log movement
            await db.inventory_movements.insert_one({
                "id": new_id("mov"),
                "product_id": item["product_id"],
                "warehouse_id": transfer["source_warehouse_id"],
                "movement_type": "transfer_out",
                "quantity": -item["qty"],
                "unit": item["unit"],
                "batch": item.get("batch", ""),
                "lot": item.get("lot", ""),
                "roll_id": item.get("roll_id", ""),
                "source_document": f"transfer_{transfer['code']}",
                "timestamp": now_iso()
            })
    
    elif new_status == "completed":
        # Reduce in_transit from source, add to dest warehouse
        for item in transfer["items"]:
            # Update source: reduce in_transit
            await db.inventory_balances.update_one(
                {"product_id": item["product_id"], "warehouse_id": transfer["source_warehouse_id"]},
                {
                    "$inc": {"in_transit_qty": -item["qty"]},
                    "$set": {"updated_at": now_iso()}
                }
            )
            
            # Update destination: create or increment
            dest_balance = await db.inventory_balances.find_one({
                "product_id": item["product_id"],
                "warehouse_id": transfer["dest_warehouse_id"]
            })
            
            if dest_balance:
                await db.inventory_balances.update_one(
                    {"product_id": item["product_id"], "warehouse_id": transfer["dest_warehouse_id"]},
                    {
                        "$inc": {
                            "on_hand_qty": item["qty"],
                            "available_qty": item["qty"]
                        },
                        "$set": {"updated_at": now_iso()}
                    }
                )
            else:
                await db.inventory_balances.insert_one({
                    "id": new_id("bal"),
                    "product_id": item["product_id"],
                    "warehouse_id": transfer["dest_warehouse_id"],
                    "on_hand_qty": item["qty"],
                    "reserved_qty": 0,
                    "available_qty": item["qty"],
                    "blocked_qty": 0,
                    "picked_qty": 0,
                    "in_transit_qty": 0,
                    "updated_at": now_iso()
                })
            
            # Log movement (dest)
            await db.inventory_movements.insert_one({
                "id": new_id("mov"),
                "product_id": item["product_id"],
                "warehouse_id": transfer["dest_warehouse_id"],
                "movement_type": "transfer_in",
                "quantity": item["qty"],
                "unit": item["unit"],
                "batch": item.get("batch", ""),
                "lot": item.get("lot", ""),
                "roll_id": item.get("roll_id", ""),
                "source_document": f"transfer_{transfer['code']}",
                "timestamp": now_iso()
            })
    
    # Update transfer status
    updated = await db.warehouse_transfers.find_one_and_update(
        {"id": transfer_id},
        {
            "$set": {
                "status": new_status,
                "updated_at": now_iso()
            }
        },
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(
        actor["name"],
        "transfer_status_changed",
        "transfer",
        transfer_id,
        {"from": current_status, "to": new_status, "updated_by": payload.updated_by}
    )
    
    return safe_doc(updated)


@router.delete("/transfers/{transfer_id}")
async def cancel_transfer(transfer_id: str, request: Request) -> Dict[str, Any]:
    """
    Cancel a transfer (soft delete via status change).
    
    Can only cancel if status is not completed, rejected, or already cancelled.
    Requires permission: transfer.cancel
    """
    actor = await require_permission(request, "transfer", "cancel")
    
    transfer = await db.warehouse_transfers.find_one({"id": transfer_id}, {"_id": 0})
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer tidak ditemukan")
    
    if transfer["status"] in ["completed", "rejected", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Transfer tidak bisa dibatalkan (status: {transfer['status']})")
    
    # Sub-fase 1.5 — inter-company: lepas reservasi roll di sumber bila masih menunggu.
    if transfer.get("transfer_kind") == "inter_entity":
        await release_transfer_rolls(transfer_id)

    # If dispatched, need to reverse inventory
    if transfer["status"] == "dispatched":
        for item in transfer["items"]:
            # Reverse: add back to source, remove from in_transit
            await db.inventory_balances.update_one(
                {"product_id": item["product_id"], "warehouse_id": transfer["source_warehouse_id"]},
                {
                    "$inc": {
                        "on_hand_qty": item["qty"],
                        "available_qty": item["qty"],
                        "in_transit_qty": -item["qty"]
                    },
                    "$set": {"updated_at": now_iso()}
                }
            )
            
            # Log reversal
            await db.inventory_movements.insert_one({
                "id": new_id("mov"),
                "product_id": item["product_id"],
                "warehouse_id": transfer["source_warehouse_id"],
                "movement_type": "transfer_cancelled",
                "quantity": item["qty"],
                "unit": item["unit"],
                "batch": item.get("batch", ""),
                "lot": item.get("lot", ""),
                "roll_id": item.get("roll_id", ""),
                "source_document": f"transfer_{transfer['code']}_cancelled",
                "timestamp": now_iso()
            })
    
    updated = await db.warehouse_transfers.find_one_and_update(
        {"id": transfer_id},
        {
            "$set": {
                "status": "cancelled",
                "updated_at": now_iso()
            }
        },
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "transfer_cancelled", "transfer", transfer_id, {})
    
    return safe_doc(updated)
