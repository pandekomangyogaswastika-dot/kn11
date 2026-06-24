"""WMS router: tasks, scanning, stage advance."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc
from entity_scope import entity_ctx, resolve_list_scope
from schemas import ScannerScan, WMSTaskCreate
from services.shipment_service import dispatch_task

router = APIRouter(prefix="/api")

FLOW_STAGES = {
    "inbound": ["created", "in_transit", "receiving", "qc_check", "put_away", "done"],
    "outbound": ["created", "picking", "packing", "staging", "dispatched"],
    "transfer": ["created", "picking", "in_transit", "receiving", "done"],
    "picking": ["created", "picking", "done"],
}


@router.get("/wms/tasks")
async def list_tasks(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    query = resolve_list_scope("wms_tasks", {}, ctx)
    tasks = await db.wms_tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(100)}
    warehouses = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    for task in tasks:
        prod = products.get(task.get("product_id"), {})
        wh = warehouses.get(task.get("warehouse_id"), {})
        task["product_name"] = prod.get("name", "")
        task["sku"] = prod.get("sku", "")
        task["warehouse_name"] = wh.get("name", "")
        task["warehouse_city"] = wh.get("city", "")
    return tasks


@router.post("/wms/tasks")
async def create_task(payload: WMSTaskCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "create")
    ctx = await entity_ctx(request)
    product = safe_doc(await db.products.find_one({"id": payload.product_id}, {"_id": 0}))
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    warehouse = safe_doc(await db.warehouses.find_one({"id": payload.warehouse_id}, {"_id": 0}))
    if not warehouse:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    stages = FLOW_STAGES.get(payload.flow_type, ["created", "done"])
    task = {
        "id": new_id("wms"),
        "entity_id": ctx.active_entity_id,
        "flow_type": payload.flow_type,
        "source_type": payload.source_type,
        "product_id": payload.product_id,
        "product_name": product["name"],
        "sku": product["sku"],
        "quantity": payload.quantity,
        "unit": payload.unit,
        "warehouse_id": payload.warehouse_id,
        "warehouse_name": warehouse["name"],
        "warehouse_city": warehouse["city"],
        "bin_id": payload.bin_id,
        "batch": payload.batch,
        "lot": payload.lot,
        "roll_id": payload.roll_id,
        "status": stages[0],
        "stages": stages,
        "scan_log": [],
        "created_by": actor["name"],
        "created_at": now_iso(), "updated_at": now_iso()
    }
    await db.wms_tasks.insert_one(task)
    if payload.flow_type == "inbound":
        existing = safe_doc(
            await db.inventory_balances.find_one(
                {"product_id": payload.product_id, "warehouse_id": payload.warehouse_id}, {"_id": 0}
            )
        )
        if existing:
            await db.inventory_balances.update_one(
                {"product_id": payload.product_id, "warehouse_id": payload.warehouse_id},
                {"$inc": {"on_hand_qty": payload.quantity, "available_qty": payload.quantity},
                 "$set": {"updated_at": now_iso()}}
            )
        else:
            await db.inventory_balances.insert_one({
                "id": new_id("bal"), "product_id": payload.product_id,
                "warehouse_id": payload.warehouse_id,
                "on_hand_qty": payload.quantity, "reserved_qty": 0,
                "available_qty": payload.quantity, "blocked_qty": 0,
                "picked_qty": 0, "in_transit_qty": 0, "updated_at": now_iso()
            })
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": payload.product_id,
            "warehouse_id": payload.warehouse_id, "movement_type": "inbound",
            "quantity": payload.quantity, "unit": payload.unit,
            "batch": payload.batch, "lot": payload.lot, "roll_id": payload.roll_id,
            "source_document": task["id"], "timestamp": now_iso()
        })
    await audit(actor["name"], "wms_task_created", "wms_task", task["id"],
                {"flow_type": payload.flow_type, "product": product["name"]})
    return safe_doc(task)


@router.post("/wms/tasks/outbound-from-order/{order_id}")
async def create_outbound_from_order(order_id: str, request: Request) -> List[Dict[str, Any]]:
    actor = await require_permission(request, "wms", "create")
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    if order["status"] not in ["confirmed", "partially_picked", "picked", "partially_shipped"]:
        raise HTTPException(status_code=409, detail="Hanya order confirmed yang bisa dibuat outbound task")
    # Sub-fase 1.8 — idempotent via service (cegah duplikasi dgn auto-create saat confirm)
    from services.fulfillment_status import create_outbound_tasks_for_order, recompute_so_status
    created_tasks = await create_outbound_tasks_for_order(order_id, actor["name"])
    await recompute_so_status(order_id)
    await audit(actor["name"], "outbound_tasks_created", "wms_task", order_id,
                {"order_number": order["number"], "tasks_count": len(created_tasks)})
    return created_tasks


@router.post("/wms/tasks/{task_id}/scan")
async def scan_task(task_id: str, payload: ScannerScan, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "scan")
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    if task["status"] in ["done", "dispatched", "cancelled"]:
        raise HTTPException(status_code=409, detail="Task terminal: scan baru diblokir")
    scan_entry = {
        "id": new_id("scan"), "scan_type": payload.scan_type, "scan_value": payload.scan_value,
        "actor": actor["name"], "timestamp": now_iso()
    }
    expected_map = {"sku": task["sku"], "batch": task["batch"], "lot": task["lot"],
                    "roll": task["roll_id"], "bin": task["bin_id"]}
    expected_value = expected_map.get(payload.scan_type, "")
    if expected_value and payload.scan_value != expected_value:
        scan_entry["match"] = False
        scan_entry["note"] = f"Tidak cocok: expected '{expected_value}', got '{payload.scan_value}'"
    else:
        scan_entry["match"] = True
    updated = await db.wms_tasks.find_one_and_update(
        {"id": task_id},
        {"$push": {"scan_log": scan_entry}, "$set": {"updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    await audit(actor["name"], "wms_scan", "wms_task", task_id, scan_entry)
    return safe_doc(updated)


@router.post("/wms/tasks/{task_id}/advance")
async def advance_task(task_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "update")
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
    stages = task.get("stages", FLOW_STAGES.get(task["flow_type"], ["created", "done"]))
    current_idx = stages.index(task["status"]) if task["status"] in stages else 0
    if current_idx >= len(stages) - 1:
        raise HTTPException(status_code=409, detail="Task sudah di stage akhir")
    next_stage = stages[current_idx + 1]
    update_data = {"status": next_stage, "updated_at": now_iso()}
    # Sub-fase 1.8 — outbound mencapai 'dispatched': delegasi ke shipment_service
    # (SSOT-safe: roll committed→in_transit_sales + catat shipment, BUKAN $inc balance).
    if next_stage == "dispatched" and task["flow_type"] == "outbound":
        updated_task, shipment = await dispatch_task(task, None, actor["name"])
        await audit(actor["name"], "wms_task_advanced", "wms_task", task_id,
                    {"status": updated_task["status"], "shipment_no": shipment["shipment_no"]})
        return updated_task
    updated = await db.wms_tasks.find_one_and_update(
        {"id": task_id}, {"$set": update_data},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    await audit(actor["name"], "wms_task_advanced", "wms_task", task_id, {"status": next_stage})
    return safe_doc(updated)
