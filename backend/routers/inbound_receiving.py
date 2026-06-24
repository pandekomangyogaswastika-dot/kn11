"""Inbound Receiving router: scan-based receiving with escalation."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, Body
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_list_scope
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID
from schemas import POReceiveItem, QCDecision, GRCompletePayload

router = APIRouter(prefix="/api")


@router.get("/inbound/tasks")
async def list_inbound_tasks(request: Request, status: str = None) -> List[Dict[str, Any]]:
    """List all inbound receiving tasks, optionally filtered by status."""
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    
    query = {"flow_type": "inbound", "source_type": "purchase_order"}
    if status:
        query["status"] = status
    query = resolve_list_scope("wms_tasks", query, ctx)
    
    tasks = await db.wms_tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    # Enrich with PO info
    po_ids = list(set(t.get("po_id") for t in tasks if t.get("po_id")))
    pos = {p["id"]: p for p in await db.purchase_orders.find({"id": {"$in": po_ids}}, {"_id": 0}).to_list(100)}
    
    for task in tasks:
        if task.get("po_id"):
            po = pos.get(task["po_id"], {})
            task["supplier_name"] = po.get("supplier_name", "")
    
    return tasks


@router.post("/inbound/tasks/{task_id}/scan-receive")
async def scan_receive_item(
    task_id: str,
    payload: POReceiveItem,
    request: Request
) -> Dict[str, Any]:
    """
    Scan and receive item for inbound task.
    
    Updates received_qty and tracks batch/lot/roll/bin.
    If received_qty reaches expected_qty, auto-advance to next stage.
    """
    actor = await require_permission(request, "wms", "update")
    
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Inbound task tidak ditemukan")
    
    if task.get("flow_type") != "inbound":
        raise HTTPException(status_code=400, detail="Task ini bukan inbound task")
    
    if task["status"] in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Task sudah selesai atau dibatalkan")
    
    # Validate product match
    if payload.product_id != task["product_id"]:
        raise HTTPException(status_code=400, detail="Product ID tidak sesuai dengan task")
    
    # Update received qty
    new_received_qty = task.get("received_qty", 0.0) + payload.actual_qty
    expected_qty = task.get("expected_qty", 0.0)

    # Fase 3 — Toleransi kedatangan ±X% (configurable, default 2%). Over-receipt
    # dalam toleransi DITERIMA (mis. benang); melebihi toleransi → ditolak (butuh
    # eskalasi/penyesuaian manager via /escalate).
    from services.config_service import get_effective_settings
    po_ctx = await db.purchase_orders.find_one({"id": task.get("po_id")}, {"_id": 0, "entity_id": 1})
    settings = await get_effective_settings((po_ctx or {}).get("entity_id"))
    tol_pct = float((settings.get("purchasing", {}) or {}).get("receive_tolerance_percent", 2.0) or 0)
    tolerance_qty = round(expected_qty * (1 + tol_pct / 100.0), 4)
    if new_received_qty > tolerance_qty + 1e-6:
        raise HTTPException(
            status_code=400,
            detail=(f"Qty terima ({new_received_qty}) melebihi toleransi +{tol_pct:g}% "
                    f"dari PO ({expected_qty}, maks {tolerance_qty:g}). "
                    f"Gunakan Eskalasi untuk penyesuaian manager.")
        )
    variance_pct = round(((new_received_qty - expected_qty) / expected_qty * 100.0), 2) if expected_qty else 0.0
    within_tolerance = abs(variance_pct) <= tol_pct
    
    # Log scan entry
    scan_entry = {
        "id": new_id("scan"),
        "scan_type": "receive",
        "actual_qty": payload.actual_qty,
        "batch": payload.batch,
        "lot": payload.lot,
        "roll_id": payload.roll_id,
        "bin_id": payload.bin_id,
        "actor": actor["name"],
        "timestamp": now_iso()
    }
    
    update_data = {
        "received_qty": new_received_qty,
        "receive_variance_percent": variance_pct,
        "receive_within_tolerance": within_tolerance,
        "receive_tolerance_percent": tol_pct,
        "batch": payload.batch or task.get("batch", ""),
        "lot": payload.lot or task.get("lot", ""),
        "dye_lot": payload.dye_lot or task.get("dye_lot", ""),
        "grade": payload.grade or task.get("grade", ""),
        "roll_id": payload.roll_id or task.get("roll_id", ""),
        "bin_id": payload.bin_id or task.get("bin_id", ""),
        "updated_at": now_iso()
    }
    
    # If received qty matches expected, auto-advance to receiving status
    if task["status"] == "waiting_goods" and new_received_qty > 0:
        update_data["status"] = "receiving"
    
    # If fully received, mark as ready for QC
    if new_received_qty >= expected_qty:
        update_data["status"] = "qc_check"
        update_data["quantity"] = new_received_qty  # Set final quantity
    
    updated_task = await db.wms_tasks.find_one_and_update(
        {"id": task_id},
        {
            "$set": update_data,
            "$push": {"scan_log": scan_entry}
        },
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "inbound_scan_receive", "wms_task", task_id, {
        "actual_qty": payload.actual_qty,
        "received_qty": new_received_qty,
        "expected_qty": expected_qty
    })
    
    return safe_doc(updated_task)


@router.post("/inbound/tasks/{task_id}/escalate")
async def escalate_inbound_task(
    task_id: str,
    request: Request,
    reason: str = "Qty tidak sesuai dengan PO"
) -> Dict[str, Any]:
    """
    Escalate inbound task to manager due to qty mismatch or other issues.
    
    Manager can then adjust expected_qty or investigate issue.
    """
    actor = await require_permission(request, "wms", "update")
    
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Inbound task tidak ditemukan")
    
    escalation = {
        "escalated_by": actor["name"],
        "escalated_at": now_iso(),
        "reason": reason,
        "status": "pending_review",
        "resolved_by": None,
        "resolved_at": None,
        "resolution_notes": ""
    }
    
    updated_task = await db.wms_tasks.find_one_and_update(
        {"id": task_id},
        {
            "$set": {
                "escalation": escalation,
                "status": "escalated",
                "updated_at": now_iso()
            }
        },
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "inbound_escalated", "wms_task", task_id, {
        "reason": reason,
        "received_qty": task.get("received_qty", 0),
        "expected_qty": task.get("expected_qty", 0)
    })
    
    return safe_doc(updated_task)


@router.post("/inbound/tasks/{task_id}/resolve-escalation")
async def resolve_escalation(
    task_id: str,
    request: Request,
    adjusted_qty: float = None,
    resolution_notes: str = ""
) -> Dict[str, Any]:
    """
    Resolve escalated inbound task (manager only).
    
    Manager can adjust expected_qty to match actual received qty.
    """
    actor = await require_permission(request, "wms", "approve")  # Manager permission
    
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Inbound task tidak ditemukan")
    
    if not task.get("escalation"):
        raise HTTPException(status_code=400, detail="Task tidak dalam status escalation")
    
    escalation = task["escalation"]
    escalation["status"] = "resolved"
    escalation["resolved_by"] = actor["name"]
    escalation["resolved_at"] = now_iso()
    escalation["resolution_notes"] = resolution_notes
    
    update_data = {
        "escalation": escalation,
        "status": "qc_check",  # Move to QC after resolution
        "updated_at": now_iso()
    }
    
    # If manager adjusts qty, update expected and final quantity
    if adjusted_qty is not None:
        update_data["expected_qty"] = adjusted_qty
        update_data["quantity"] = task.get("received_qty", 0.0)
    
    updated_task = await db.wms_tasks.find_one_and_update(
        {"id": task_id},
        {"$set": update_data},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "inbound_escalation_resolved", "wms_task", task_id, {
        "adjusted_qty": adjusted_qty,
        "resolution_notes": resolution_notes
    })
    
    return safe_doc(updated_task)


@router.post("/inbound/tasks/{task_id}/complete")
async def complete_inbound_receiving(
    task_id: str,
    request: Request,
    payload: Optional[GRCompletePayload] = Body(default=None),
) -> Dict[str, Any]:
    """
    Complete inbound receiving and update inventory.
    
    This moves task from qc_check → put_away → completed.
    Inventory is updated ONLY when status becomes 'completed'.

    P0-4 — body opsional `GRCompletePayload`: bila `rolls` diisi → buat multi-roll
    (panjang + dye_lot + grade per roll); bila kosong → satu roll dengan dye_lot/grade
    default (dari task/scan atau fallback lot/A). Pemanggilan TANPA body tetap jalan.
    """
    actor = await require_permission(request, "wms", "update")
    
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Inbound task tidak ditemukan")
    
    if task["status"] not in ["qc_check", "put_away"]:
        raise HTTPException(
            status_code=400,
            detail=f"Task harus dalam status qc_check atau put_away (current: {task['status']})"
        )
    
    # Check if qty is finalized
    final_qty = task.get("quantity", 0.0)
    if final_qty <= 0:
        # Fallback: if quantity wasn't explicitly set, use received_qty
        final_qty = task.get("received_qty", 0.0)
    if final_qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity harus lebih dari 0 untuk complete")
    
    # Advance status — Depth #3a (QC Hold) menentukan tujuan barang.
    # Operator menekan "Selesaikan Penerimaan" → barang masuk inventory.
    # Sub-fase 1.6 — Roll-as-SSOT + Depth #3a — QC Hold/Quarantine.
    from services.roll_service import rebuild_balance
    from services.backorder_service import auto_fulfill_backorders
    from services.config_service import get_effective_settings

    # Owner entity diturunkan dari PO (default entitas utama)
    owner_entity_id = DEFAULT_ENTITY_ID
    po_doc = None
    if task.get("po_id"):
        po_doc = await db.purchase_orders.find_one({"id": task["po_id"]}, {"_id": 0})
        owner_entity_id = (po_doc or {}).get("entity_id") or DEFAULT_ENTITY_ID

    # Depth #3a — bila qc_on_receipt: barang masuk → roll `quarantine` (BUKAN available),
    # task → `qc_pending` (menunggu inspeksi QC). Bila non-aktif: legacy available+completed.
    qc_cfg = await get_effective_settings(owner_entity_id)
    qc_on_receipt = bool((qc_cfg.get("purchasing", {}) or {}).get("qc_on_receipt", True))
    roll_status = "quarantine" if qc_on_receipt else "available"
    next_stage = "qc_pending" if qc_on_receipt else "completed"

    # Buat roll + update PO untuk kedua jalur (available langsung / karantina)
    if next_stage in ("completed", "qc_pending"):

        lot = task.get("lot") or f"LOT-{task.get('po_number', task_id)}"
        # P0-4 — dye_lot & grade aktual (default backward-compatible: dye_lot=lot, grade=A)
        default_dye_lot = (payload.dye_lot if payload else "") or task.get("dye_lot") or lot
        default_grade = (payload.grade if payload else "") or task.get("grade") or "A"

        # Fase 8 (Catch-weight) — roll length dlm BASE unit (meter) + weight_kg AKTUAL.
        product_doc = safe_doc(await db.products.find_one({"id": task["product_id"]}, {"_id": 0})) or {}
        gr_base_unit = product_doc.get("base_unit", "meter")
        gr_task_unit = task.get("unit", "meter")
        from services.uom_service import load_fixed_factors, resolve_roll_measures
        _factors = await load_fixed_factors()
        _is_weight_task = (gr_task_unit or "").strip().lower() == "kg"

        # P0-4 + Fase 8 — payload.rolls → MULTI roll (panjang m + berat kg + dye_lot/grade per roll).
        # Validasi Σ kontribusi (task_qty) ≈ qty diterima (SATUAN task). Bila kosong → satu roll.
        roll_specs: List[Dict[str, Any]] = []
        if payload and payload.rolls:
            measures = [resolve_roll_measures(product_doc, gr_task_unit,
                                              float(r.length or 0), float(r.weight or 0), _factors)
                        for r in payload.rolls]
            total_task = round(sum(m["task_qty"] for m in measures), 2)
            if total_task <= 0:
                raise HTTPException(status_code=400, detail="Total ukuran roll harus lebih dari 0.")
            tol_line = max(0.5, round(final_qty * 0.02, 2))
            if abs(total_task - final_qty) > tol_line:
                raise HTTPException(
                    status_code=400,
                    detail=(f"Total roll ({total_task:g} {gr_task_unit}) tidak cocok dengan qty diterima "
                            f"({final_qty:g} {gr_task_unit}, toleransi ±{tol_line:g})."))
            for r, m in zip(payload.rolls, measures):
                roll_specs.append({
                    "length_base": m["length_base"],
                    "weight_kg": m["weight_kg"],
                    "dye_lot": (r.dye_lot or default_dye_lot),
                    "grade": (r.grade or default_grade),
                    "defects": list(r.defects or []),
                })
        else:
            m = resolve_roll_measures(
                product_doc, gr_task_unit,
                0.0 if _is_weight_task else final_qty,   # length_in (m) utk PO per-panjang
                final_qty if _is_weight_task else 0.0,   # weight_in (kg) utk PO per-berat
                _factors)
            roll_specs.append({
                "length_base": m["length_base"],
                "weight_kg": m["weight_kg"],
                "dye_lot": default_dye_lot,
                "grade": default_grade,
                "defects": [],
            })

        # P0-5 — base HPP roll dari harga PO saat GR (per BASE unit). Landed cost
        # (Fase 5.4) menambah di atas base ini. Fallback: harga_pokok produk.
        _po_doc = None
        if task.get("po_id"):
            _po_doc = safe_doc(await db.purchase_orders.find_one({"id": task["po_id"]}, {"_id": 0}))
        _po_unit_price = 0.0
        if _po_doc:
            for _it in _po_doc.get("items", []):
                if _it.get("product_id") == task["product_id"]:
                    _po_unit_price = float(_it.get("price", 0) or 0)
                    break
        if _po_unit_price <= 0:
            _po_unit_price = float(product_doc.get("harga_pokok", 0) or 0)
        _total_base = round(sum(s["length_base"] for s in roll_specs), 4)
        if _po_unit_price > 0 and _total_base > 0:
            # total cost (task unit × harga) dibagi total base qty → HPP per base unit
            base_unit_cost = round((final_qty * _po_unit_price) / _total_base, 4)
        else:
            base_unit_cost = None

        roll_seq = await db.inventory_rolls.count_documents({})
        is_multi = len(roll_specs) > 1
        for spec in roll_specs:
            roll_seq += 1
            spec_len = spec["length_base"]
            roll_doc = {
                "id": new_id("roll"),
                "product_id": task["product_id"],
                "owner_entity_id": owner_entity_id,
                "ownership_type": "internal",
                "consignor_ref": None,
                "warehouse_id": task["warehouse_id"],
                "bin_id": task.get("bin_id") or None,
                "lot": lot,
                "dye_lot": spec["dye_lot"],
                "batch": task.get("batch") or (lot.replace("LOT", "BATCH") if lot else ""),
                "roll_no": f"RL-{roll_seq:05d}",
                "length_initial": spec_len,
                "length_remaining": spec_len,
                "unit": gr_base_unit,
                "weight_kg": spec.get("weight_kg", 0.0),   # Fase 8 — catch-weight aktual roll
                "weight_unit": "kg",
                "grade": spec["grade"],
                "defects": spec["defects"],
                "status": roll_status,
                "qc_task_id": task_id if qc_on_receipt else None,
                "tracking_mode": "barcode",
                "earmarked_for": None,
                "location_type": "warehouse_bin",
                "reserved_ref": None,
                "unit_cost": base_unit_cost,
                "base_unit_cost": base_unit_cost,
                "landed_cost_total": 0.0,
                "landed_cost_refs": [],
                "acquired": {"via": "inbound", "ref_id": task.get("po_id") or task_id, "date": now_iso()},
                "rfid_tag_id": (task.get("roll_id") or None) if not is_multi else None,
                "is_remnant": False,
                "created_at": now_iso(), "updated_at": now_iso(),
                "created_by": actor.get("id") or "system", "created_by_name": actor["name"],
            }
            await db.inventory_rolls.insert_one(dict(roll_doc))

            # Log movement (owner-scoped, link roll)
            await db.inventory_movements.insert_one({
                "id": new_id("mov"),
                "product_id": task["product_id"],
                "warehouse_id": task["warehouse_id"],
                "owner_entity_id": owner_entity_id,
                "movement_type": "inbound_receiving",
                "quantity": spec_len,
                "unit": gr_base_unit,
                "weight_kg": spec.get("weight_kg", 0.0),   # Fase 8 — catch-weight
                "batch": task.get("batch", ""),
                "lot": lot,
                "roll_id": roll_doc["id"],
                "source_document": f"PO_{task.get('po_number', '')}",
                "timestamp": now_iso()
            })

        # Update PO item received_qty (akumulatif) + status
        if task.get("po_id"):
            await db.purchase_orders.update_one(
                {
                    "id": task["po_id"],
                    "items.product_id": task["product_id"]
                },
                {
                    "$inc": {"items.$.received_qty": final_qty},
                    "$set": {
                        "status": "receiving",
                        "last_received_at": now_iso(),
                        "updated_at": now_iso()
                    }
                }
            )
            # Depth 1A — hitung ulang status PO (partial/completed) dari received_qty
            from routers.purchase_orders import recompute_po_status
            await recompute_po_status(task["po_id"])

        # Rebuild proyeksi balance segmen (jaga invarian balance == Σ rolls)
        await rebuild_balance(task["product_id"], task["warehouse_id"], owner_entity_id)

        # AUTO-FULFILL backorder hanya bila stok LANGSUNG available (QC non-aktif).
        # Bila qc_on_receipt: barang di karantina → tunggu keputusan QC accept (qc_service).
        if not qc_on_receipt:
            await auto_fulfill_backorders(task["product_id"], owner_entity_id)
    
    updated_task = await db.wms_tasks.find_one_and_update(
        {"id": task_id},
        {"$set": {
            "status": next_stage,
            "updated_at": now_iso(),
            **({"qc_status": "pending", "quarantine_qty": final_qty} if qc_on_receipt else {}),
        }},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "inbound_completed", "wms_task", task_id, {
        "final_qty": final_qty,
        "status": next_stage
    })
    
    return safe_doc(updated_task)


@router.get("/inbound/qc/queue")
async def qc_inspection_queue(request: Request) -> List[Dict[str, Any]]:
    """Depth #3a — antrian inspeksi QC: task inbound berstatus `qc_pending`
    (barang di karantina menunggu keputusan terima/tolak)."""
    await require_permission(request, "wms", "view")
    from services.qc_service import quarantine_qty_for_task
    ctx = await entity_ctx(request)
    tasks = await db.wms_tasks.find(
        resolve_list_scope("wms_tasks", {"flow_type": "inbound", "status": "qc_pending"}, ctx), {"_id": 0},
    ).sort("updated_at", -1).to_list(200)
    po_ids = list({t.get("po_id") for t in tasks if t.get("po_id")})
    pos = {p["id"]: p for p in await db.purchase_orders.find(
        {"id": {"$in": po_ids}}, {"_id": 0}).to_list(100)}
    prod_ids = list({t.get("product_id") for t in tasks if t.get("product_id")})
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": prod_ids}}, {"_id": 0}).to_list(500)}
    whs = {w["id"]: w for w in await db.warehouses.find({}, {"_id": 0}).to_list(100)}
    out = []
    for t in tasks:
        po = pos.get(t.get("po_id"), {})
        prod = prods.get(t.get("product_id"), {})
        t["supplier_name"] = po.get("supplier_name", "")
        t["po_number"] = t.get("po_number") or po.get("po_number", "")
        t["product_name"] = t.get("product_name") or prod.get("name", "")
        t["sku"] = prod.get("sku", "")
        t["warehouse_name"] = whs.get(t.get("warehouse_id"), {}).get("name", "")
        t["quarantine_qty"] = await quarantine_qty_for_task(t["id"])
        out.append(safe_doc(t))
    return out


@router.post("/inbound/tasks/{task_id}/qc-decision")
async def qc_decision(task_id: str, payload: QCDecision, request: Request) -> Dict[str, Any]:
    """Depth #3a — keputusan inspeksi QC: terima (→available) &/atau tolak
    (→damaged / retur ke supplier dengan Nota Debit otomatis)."""
    actor = await require_permission(request, "wms", "update")
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Inbound task tidak ditemukan")
    if task.get("status") != "qc_pending":
        raise HTTPException(
            status_code=400,
            detail=f"Task harus berstatus qc_pending untuk inspeksi (current: {task.get('status')})")
    from services.qc_service import process_qc_decision
    try:
        result = await process_qc_decision(
            task, payload.accept_qty, payload.reject_qty,
            payload.reject_disposition, payload.reason, actor,
            accept_grade=payload.accept_grade, defects=payload.defects)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "qc_decision", "wms_task", task_id, result)
    return result



@router.get("/inbound/po/{po_id}/receiving-goods-document")
async def generate_receiving_goods_document(po_id: str, request: Request):
    """
    Generate Receiving Goods document (like surat jalan) for completed PO.
    
    Shows all received items with batch/lot/qty details.
    """
    from datetime import datetime, timezone
    
    await require_permission(request, "wms", "view")
    
    po = safe_doc(await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}))
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order tidak ditemukan")
    
    # Get all completed inbound tasks for this PO
    tasks = await db.wms_tasks.find({
        "po_id": po_id,
        "status": "completed"
    }, {"_id": 0}).to_list(100)
    
    if not tasks:
        raise HTTPException(status_code=400, detail="Belum ada inbound task yang completed untuk PO ini")
    
    # Build items table
    items_rows = ""
    for task in tasks:
        items_rows += f"""
        <tr>
            <td>{task.get('sku', '')}</td>
            <td>{task.get('product_name', '')}</td>
            <td>{task.get('quantity', 0.0)}</td>
            <td>{task.get('unit', '')}</td>
            <td>{task.get('batch', '-')}</td>
            <td>{task.get('lot', '-')}</td>
            <td>{task.get('bin_id', '-')}</td>
        </tr>
        """
    
    html = f"""
    <html>
    <head>
        <title>Surat Penerimaan Barang - {po['po_number']}</title>
        <style>
            @page {{size: A4 portrait; margin: 12mm}}
            body {{font-family: Arial, sans-serif; padding: 0; color: #111}}
            .header {{display: flex; justify-content: space-between; border-bottom: 2px solid #111; padding-bottom: 16px; margin-bottom: 20px}}
            h1 {{margin: 0; font-size: 24px}}
            h2 {{margin: 10px 0; font-size: 18px}}
            table {{width: 100%; border-collapse: collapse; margin-top: 18px}}
            td, th {{border: 1px solid #ddd; padding: 10px; text-align: left}}
            th {{background: #f5f5f5; font-weight: bold}}
            .info-section {{margin: 20px 0}}
            .signature {{display: flex; justify-content: space-between; margin-top: 60px}}
            .signature div {{text-align: center}}
            footer {{margin-top: 40px; border-top: 1px solid #ddd; padding-top: 12px; color: #555; font-size: 12px}}
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <h1>Kain Nusantara</h1>
                <p style="color: #555; margin: 5px 0">Enterprise Textile Warehouse</p>
            </div>
            <div style="text-align: right">
                <h2>SURAT PENERIMAAN BARANG</h2>
                <p style="margin: 5px 0"><strong>{po['po_number']}</strong></p>
                <p style="margin: 5px 0">{datetime.now(timezone.utc).strftime('%d %b %Y')}</p>
            </div>
        </div>
        
        <div class="info-section">
            <h3>Informasi PO</h3>
            <p><strong>Supplier:</strong> {po['supplier_name']}</p>
            <p><strong>Kontak:</strong> {po.get('supplier_contact', '-')}</p>
            <p><strong>Gudang Tujuan:</strong> {po.get('warehouse_name', '-')} ({po.get('warehouse_city', '')})</p>
            <p><strong>Tanggal Expected:</strong> {po.get('expected_delivery_date', '-')}</p>
        </div>
        
        <h3>Barang yang Diterima</h3>
        <table>
            <thead>
                <tr>
                    <th>SKU</th>
                    <th>Nama Produk</th>
                    <th>Qty Diterima</th>
                    <th>Unit</th>
                    <th>Batch</th>
                    <th>Lot</th>
                    <th>Bin Location</th>
                </tr>
            </thead>
            <tbody>
                {items_rows}
            </tbody>
        </table>
        
        <div class="signature">
            <div>
                <p>Diterima Oleh</p>
                <br/><br/>
                <p><strong>_________________</strong></p>
                <p>Warehouse Staff</p>
            </div>
            <div>
                <p>Disetujui Oleh</p>
                <br/><br/>
                <p><strong>_________________</strong></p>
                <p>Warehouse Manager</p>
            </div>
        </div>
        
        <footer>
            <p>Dokumen ini dibuat secara otomatis oleh sistem Kain Nusantara WMS.</p>
            <p>Barang diterima dalam kondisi baik dan sesuai dengan spesifikasi PO.</p>
        </footer>
    </body>
    </html>
    """
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
