"""Purchase Orders router: simplified PO management for inbound receiving."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit, current_user
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID, timeline_entry, next_doc_number
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access
from schemas import PurchaseOrderCreate, POReceiveItem, POPaymentCreate, POCloseRequest, PurchaseOrderAmend, BlanketPOCreate, CallOffCreate, BlanketCloseRequest
from services.config_service import evaluate_approval, build_approval_chain, current_pending_level, role_satisfies, get_effective_settings, compute_order_pricing
from services.po_amendment_service import amend_po as amend_po_service
from services import blanket_po_service

router = APIRouter(prefix="/api")

# Status PO yang dianggap "barang sudah/akan diterima" → menimbulkan hutang (AP)
AP_LIABILITY_STATUSES = {"pending", "receiving", "partial", "completed", "closed_short"}
TERMINAL_PO_STATUSES = {"cancelled", "rejected", "closed_short", "completed"}


def _po_financials(po: Dict[str, Any]) -> Dict[str, Any]:
    """Hitung nilai keuangan PO: diterima, retur, dibayar, outstanding (AP).

    P0-1 — basis tagihan/hutang = grand_total (incl PPN & setelah diskon) bila ada,
    fallback ke total_amount (GROSS) untuk PO lama tanpa breakdown."""
    ordered_value = 0.0
    received_value = 0.0
    for it in po.get("items", []):
        price = float(it.get("price", 0) or 0)
        ordered_value += float(it.get("quantity", 0) or 0) * price
        received_value += float(it.get("received_qty", 0) or 0) * price
    gross_total = float(po.get("total_amount", 0) or 0)
    if gross_total <= 0.0:  # fallback PO lama tanpa total_amount tersimpan
        gross_total = ordered_value
    # Basis tagihan ke supplier: grand_total (incl PPN) bila tersedia, else gross.
    grand = float(po.get("grand_total", 0) or 0)
    base = grand if grand > 0.0 else gross_total
    amount_paid = float(po.get("amount_paid", 0) or 0)
    returned_amount = float(po.get("returned_amount", 0) or 0)
    billable = max(base - returned_amount, 0.0)
    outstanding = round(max(billable - amount_paid, 0.0), 2)
    if amount_paid <= 0.01:
        pay_status = "unpaid"
    elif outstanding <= 0.01:
        pay_status = "paid"
    else:
        pay_status = "partial"
    return {
        "total_amount": round(base, 2),         # base tagihan (incl PPN bila ada) — dipakai UI/payables
        "gross_total": round(gross_total, 2),   # Σ subtotal (sebelum diskon & pajak)
        "discount_total": round(float(po.get("discount_total", 0) or 0), 2),
        "net_subtotal": round(float(po.get("net_subtotal", 0) or 0), 2),
        "dpp": round(float(po.get("dpp", 0) or 0), 2),
        "ppn_rate": float(po.get("ppn_rate", 0) or 0),
        "ppn_amount": round(float(po.get("ppn_amount", 0) or 0), 2),
        "grand_total": round(base, 2),
        "received_value": round(received_value, 2),
        "returned_amount": round(returned_amount, 2),
        "amount_paid": round(amount_paid, 2),
        "outstanding": outstanding,
        "payment_status": pay_status,
    }


async def recompute_po_status(po_id: str) -> None:
    """Depth 1A — hitung status PO dari received_qty tiap item.
    Tidak menimpa status terminal (cancelled/rejected/closed_short/completed)."""
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po or po.get("status") in TERMINAL_PO_STATUSES:
        return
    items = po.get("items", [])
    if not items:
        return
    settings = await get_effective_settings(po.get("entity_id"))
    tol = float((settings.get("purchasing", {}) or {}).get("receive_tolerance_percent", 2.0) or 0)
    total_received = sum(float(it.get("received_qty", 0) or 0) for it in items)
    # Item dianggap lengkap bila received >= ordered*(1 - toleransi)
    all_complete = all(
        float(it.get("received_qty", 0) or 0) + 1e-6 >= float(it.get("quantity", 0) or 0) * (1 - tol / 100.0)
        for it in items
    )
    if all_complete and total_received > 0:
        new_status = "completed"
    elif total_received > 0:
        new_status = "partial"
    else:
        new_status = po.get("status", "pending")
    if new_status != po.get("status"):
        update_ops: Dict[str, Any] = {"$set": {"status": new_status, "updated_at": now_iso()}}
        if new_status == "completed":
            update_ops["$push"] = {"timeline": timeline_entry(
                "completed", "Penerimaan barang selesai", "Sistem",
                f"Total diterima {total_received:g}")}
        elif new_status == "partial":
            update_ops["$push"] = {"timeline": timeline_entry(
                "received", "Barang diterima sebagian", "Sistem",
                f"Diterima {total_received:g}")}
        await db.purchase_orders.update_one({"id": po_id}, update_ops)


async def recompute_po_payment_status(po_id: str) -> None:
    """Depth 1C — sinkronkan payment_status & outstanding PO."""
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        return
    fin = _po_financials(po)
    await db.purchase_orders.update_one(
        {"id": po_id},
        {"$set": {"payment_status": fin["payment_status"], "outstanding": fin["outstanding"],
                  "updated_at": now_iso()}})


async def _create_inbound_tasks_for_po(po: Dict[str, Any]) -> None:
    """Buat inbound receiving task untuk tiap item PO (dipanggil saat PO siap
    diterima: langsung bila tak butuh approval, atau setelah di-approve)."""
    # Resolve warehouse name/city defensively (PO lama/seed mungkin tak menyimpannya).
    wh_name = po.get("warehouse_name", "")
    wh_city = po.get("warehouse_city", "")
    entity_id = po.get("entity_id") or ""  # F0-C/D: wms_tasks ter-stamp per entitas dari PO induk.
    if not wh_name and po.get("warehouse_id"):
        wh = await db.warehouses.find_one({"id": po["warehouse_id"]}, {"_id": 0, "name": 1, "city": 1})
        if wh:
            wh_name = wh.get("name", "")
            wh_city = wh.get("city", "") or wh_city
    for item in po.get("items", []):
        # Phase 7.2 — idempotent saat re-approval amendment: jangan duplikat task yg sudah ada.
        existing = await db.wms_tasks.find_one({
            "po_id": po["id"], "product_id": item["product_id"], "flow_type": "inbound",
            "status": {"$nin": ["cancelled", "completed"]},
        }, {"_id": 0, "id": 1, "expected_qty": 1})
        if existing:
            if abs(float(existing.get("expected_qty", 0) or 0) - float(item["quantity"] or 0)) > 0.001:
                await db.wms_tasks.update_one(
                    {"id": existing["id"]},
                    {"$set": {"expected_qty": item["quantity"], "unit": item.get("unit", "meter"),
                              "updated_at": now_iso()}})
            continue
        stages = ["waiting_goods", "receiving", "qc_check", "put_away", "completed"]
        await db.wms_tasks.insert_one({
            "id": new_id("wms"),
            "entity_id": entity_id,
            "flow_type": "inbound",
            "source_type": "purchase_order",
            "po_id": po["id"],
            "po_number": po["po_number"],
            "product_id": item["product_id"],
            "product_name": item.get("product_name", ""),
            "sku": item.get("sku", ""),
            "expected_qty": item["quantity"],
            "received_qty": 0.0,
            "quantity": 0.0,
            "unit": item.get("unit", "meter"),
            "warehouse_id": po["warehouse_id"],
            "warehouse_name": wh_name,
            "warehouse_city": wh_city,
            "supplier_name": po.get("supplier_name", ""),
            "bin_id": "", "batch": "", "lot": "", "roll_id": "",
            "status": stages[0], "stages": stages, "scan_log": [],
            "escalation": None,
            "created_by": po.get("created_by", "system"),
            "created_at": now_iso(), "updated_at": now_iso(),
        })


@router.get("/purchase-orders")
async def list_purchase_orders(request: Request, entity_id: str = None) -> List[Dict[str, Any]]:
    """List all purchase orders."""
    await require_permission(request, "purchase_order", "view")
    ctx = await entity_ctx(request)
    query = {"po_type": {"$ne": "blanket"}}  # blanket punya daftar terpisah (GET /purchase-orders/blanket)
    query = resolve_list_scope("purchase_orders", query, ctx, entity_id)
    pos = await db.purchase_orders.find(query, {"_id": 0}).sort("created_at", -1).to_list(300)
    return pos


@router.post("/purchase-orders")
async def create_purchase_order(payload: PurchaseOrderCreate, request: Request) -> Dict[str, Any]:
    """Create a new purchase order (auto-create inbound task bila tak butuh approval)."""
    actor = await require_permission(request, "purchase_order", "create")
    ctx = await entity_ctx(request)
    return await _create_po_core(payload, actor, active_entity_id=ctx.active_entity_id)


async def _create_po_core(payload: PurchaseOrderCreate, actor: Dict[str, Any], *,
                          po_type: str = "standard", parent: Dict[str, Any] = None,
                          force_approval: bool = False, force_reason: str = "",
                          extra_note: str = "", active_entity_id: str = DEFAULT_ENTITY_ID) -> Dict[str, Any]:
    """Inti pembuatan PO — dipakai PO standar & call-off Blanket PO (2.a).

    `force_approval`/`force_reason` → paksa approval dari awal (mis. over-call 4.b).
    `parent` = dokumen Blanket PO (untuk linkage call-off). Auto-create inbound task
    bila TIDAK butuh approval (atau nanti setelah /approve).
    """
    # Validate warehouse
    warehouse = safe_doc(await db.warehouses.find_one({"id": payload.warehouse_id}, {"_id": 0}))
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse tidak ditemukan")

    # Fase 3 — resolve supplier master (FK) → snapshot. Fallback ke supplier_name manual.
    supplier_id = ""
    supplier_name = (payload.supplier_name or "").strip()
    supplier_contact = payload.supplier_contact
    supplier_npwp = ""
    if payload.supplier_id:
        supplier = safe_doc(await db.suppliers.find_one({"id": payload.supplier_id}, {"_id": 0}))
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier tidak ditemukan")
        supplier_id = supplier["id"]
        supplier_name = supplier.get("name", "")
        supplier_npwp = supplier.get("npwp", "")
        if not supplier_contact:
            pic = supplier.get("pic_name", "")
            phone = supplier.get("phone", "")
            supplier_contact = " | ".join([x for x in [pic, phone] if x])
    if not supplier_name:
        raise HTTPException(status_code=400, detail="Supplier wajib dipilih atau diisi")
    
    # Validate products and calculate total
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    raw_items = []

    from services.supplier_service import resolve_price
    # Fase 8 (Catch-weight) — siapkan faktor konversi untuk quantity_base (meter-ekuivalen).
    from services.uom_service import to_base, load_fixed_factors
    _uom_factors = await load_fixed_factors()

    for item_in in payload.items:
        product = products.get(item_in.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Produk {item_in.product_id} tidak ditemukan")

        # Depth #3 — auto-isi harga dari price-list supplier bila tak diisi manual.
        price = float(item_in.price or 0)
        if price <= 0:
            resolved = await resolve_price(supplier_id, item_in.product_id, item_in.quantity)
            price = float(resolved.get("price", 0) or 0)
        if price <= 0:
            price = float(product.get("price", 0) or 0)

        # Fase 8 — qty dalam BASE unit (meter) untuk perencanaan stok (on_order/ATP).
        # Bila dibeli per 'kg', konversi via catch-weight; gagal konversi → fallback = quantity.
        base_unit = product.get("base_unit", "meter")
        order_unit = item_in.unit or base_unit
        if (order_unit or "").strip().lower() == (base_unit or "meter").strip().lower():
            quantity_base = round(float(item_in.quantity or 0), 2)
        else:
            try:
                quantity_base = to_base(product, float(item_in.quantity or 0), order_unit, _uom_factors)
            except HTTPException:
                quantity_base = round(float(item_in.quantity or 0), 2)

        raw_items.append({
            "product_id": product["id"],
            "sku": product["sku"],
            "product_name": product["name"],
            "quantity": item_in.quantity,
            "unit": item_in.unit,
            "base_unit": base_unit,                # Fase 8 — satuan stok produk
            "quantity_base": quantity_base,        # Fase 8 — qty meter-ekuivalen (planning)
            "price": price,
            "discount_percent": float(item_in.discount_percent or 0),  # P0-1 — diskon item supplier
            "received_qty": 0.0  # Tracking actual received
        })

    entity_id = payload.entity_id or active_entity_id
    # P0-1 — breakdown harga PO: diskon item/order + DPP + PPN (Faktur Pajak Masukan).
    # INVARIAN-SAFE: total_amount tetap GROSS (Σ subtotal), pajak/diskon di field terpisah.
    pricing = await compute_order_pricing(
        raw_items, entity_id, payload.order_discount_percent,
        cfg_section="purchasing", tax_override=payload.tax_mode)
    items = pricing["items"]
    total_amount = pricing["total_amount"]
    grand_total = pricing["grand_total"]

    # Generate PO number (deletion-safe / max-based — P0-A)
    po_number = await next_doc_number("purchase_orders", "po_number", "PO-", entity_id=entity_id)

    # Fase 7.1 — kebutuhan approval BERJENJANG (multi-level) dari approval_rules + extra_levels
    appr = await build_approval_chain("purchase_order", total_amount, entity_id)
    approval_chain = appr["approval_chain"]
    needs_approval = appr["requires_approval"]
    required_role = appr["required_role"]
    approval_reason = "amount_threshold" if needs_approval else ""

    # Depth #3 — guard penyimpangan harga vs price-list supplier → wajib approval.
    from services.supplier_service import assess_price_deviation
    from services.config_service import get_effective_settings
    settings = await get_effective_settings(entity_id)
    threshold = float(settings.get("purchasing", {}).get("price_deviation_approval_percent", 10.0) or 10.0)
    price_deviation = await assess_price_deviation(supplier_id, items, threshold) if supplier_id else \
        {"flagged": False, "threshold_pct": threshold, "max_deviation_pct": 0.0, "items": []}
    if price_deviation["flagged"]:
        if not approval_chain:
            appr = await build_approval_chain("purchase_order", total_amount, entity_id, force_level1_role="manager")
            approval_chain = appr["approval_chain"]
        needs_approval = True
        required_role = approval_chain[0]["required_role"] if approval_chain else "manager"
        approval_reason = "price_deviation" if approval_reason == "" else "amount_threshold+price_deviation"

    # 4.b — call-off over-call (atau pemicu lain) → PAKSA approval dari awal.
    if force_approval:
        if not approval_chain:
            appr = await build_approval_chain("purchase_order", total_amount, entity_id, force_level1_role="manager")
            approval_chain = appr["approval_chain"]
        needs_approval = True
        required_role = approval_chain[0]["required_role"] if approval_chain else "manager"
        approval_reason = force_reason if not approval_reason else f"{approval_reason}+{force_reason}"

    # Depth #3 — riwayat/timeline approval PO.
    actor_name = payload.created_by or "Admin"
    _created_label = "Call-off dibuat" if po_type == "call_off" else "PO dibuat"
    _created_detail = f"{len(items)} item · Rp {total_amount:,.0f}"
    if parent:
        _created_detail += f" · dari kontrak {parent.get('po_number', '')}"
    if extra_note:
        _created_detail += f" · {extra_note}"
    po_timeline = [timeline_entry("created", _created_label, actor_name, _created_detail)]
    if needs_approval:
        dev_note = f"deviasi harga +{price_deviation['max_deviation_pct']}%" if price_deviation["flagged"] else "nilai melebihi batas"
        po_timeline.append(timeline_entry(
            "submitted_for_approval", f"Menunggu persetujuan {required_role}", actor_name, dev_note))

    # Create PO document
    po = {
        "id": new_id("po"),
        "po_number": po_number,
        "po_type": po_type,
        "parent_po_id": (parent or {}).get("id", ""),
        "parent_po_number": (parent or {}).get("po_number", ""),
        "call_off_note": extra_note if po_type == "call_off" else "",
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "supplier_contact": supplier_contact,
        "supplier_npwp": supplier_npwp,
        "warehouse_id": payload.warehouse_id,
        "warehouse_name": warehouse["name"],
        "warehouse_city": warehouse.get("city", ""),
        "items": items,
        "total_amount": total_amount,
        # P0-1 — breakdown diskon + PPN (Faktur Pajak Masukan). Invariant-safe.
        "items_discount_total": pricing["items_discount_total"],
        "order_discount_percent": pricing["order_discount_percent"],
        "order_discount_amount": pricing["order_discount_amount"],
        "discount_total": pricing["discount_total"],
        "net_subtotal": pricing["net_subtotal"],
        "dpp": pricing["dpp"],
        "ppn_rate": pricing["ppn_rate"],
        "ppn_mode": pricing["ppn_mode"],
        "is_pkp": pricing["is_pkp"],
        "ppn_amount": pricing["ppn_amount"],
        "grand_total": grand_total,
        "tax_mode": payload.tax_mode or "",
        "entity_id": entity_id,
        "expected_delivery_date": payload.expected_delivery_date,
        "notes": payload.notes,
        # waiting_approval → pending → receiving → completed / partial / cancelled
        "status": "waiting_approval" if needs_approval else "pending",
        "approval_required": needs_approval,
        "required_approval_role": required_role,
        "approval_status": "pending" if needs_approval else "not_required",
        "approval_chain": approval_chain,
        "approval_level_current": (approval_chain[0]["level"] if (needs_approval and approval_chain) else 0),
        "approval_levels_total": len(approval_chain),
        "approval_amount": total_amount,
        "approval_reason": approval_reason,
        "price_deviation": price_deviation,
        "timeline": po_timeline,
        # Depth 1C — pelacakan pembayaran / hutang (AP)
        "amount_paid": 0.0,
        "returned_amount": 0.0,
        "outstanding": round(grand_total, 2),
        "payment_status": "unpaid",
        "payments": [],
        # Phase 7.2 — Amendment / Version History
        "version": 1,
        "amendments": [],
        "created_by": payload.created_by,
        "created_by_id": actor.get("id", ""),
        "created_at": now_iso(),
        "updated_at": now_iso()
    }

    await db.purchase_orders.insert_one(po)

    # Inbound task dibuat hanya bila PO TIDAK butuh approval (atau nanti setelah approve)
    if not needs_approval:
        await _create_inbound_tasks_for_po(po)

    await audit(actor["name"], "po_created", "purchase_order", po["id"], {
        "po_number": po_number,
        "supplier": supplier_name,
        "supplier_id": supplier_id,
        "total_amount": total_amount,
        "approval_required": needs_approval,
        "required_role": required_role,
        "approval_reason": approval_reason,
    })

    # Depth #3 — notifikasi ke role approver bila PO butuh persetujuan.
    if needs_approval:
        from services.notification_service import notify_po_awaiting_approval
        await notify_po_awaiting_approval(po)

    return safe_doc(po)


# ─── Blanket / Contract PO (P2 — call-off) ───────────────────────────────────

@router.post("/purchase-orders/blanket")
async def create_blanket_po(payload: BlanketPOCreate, request: Request) -> Dict[str, Any]:
    """P2 — buat kontrak Blanket/Contract PO (1.c qty per item + plafon nilai). Tanpa inbound task."""
    actor = await require_permission(request, "purchase_order", "create")
    blanket = await blanket_po_service.create_blanket(payload, actor)
    await audit(actor["name"], "blanket_po_created", "purchase_order", blanket["id"], {
        "po_number": blanket["po_number"], "supplier": blanket.get("supplier_name"),
        "items": len(blanket.get("contract_items", [])), "value_cap": blanket.get("contract_value_cap")})
    return blanket


@router.get("/purchase-orders/blanket")
async def list_blanket_pos(request: Request, entity_id: str = None) -> List[Dict[str, Any]]:
    """P2 — daftar Blanket PO + drawdown ringkas (called/remaining/status)."""
    await require_permission(request, "purchase_order", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope("purchase_orders", {}, ctx, entity_id)
    return await blanket_po_service.list_blankets(scope=scope)


@router.post("/purchase-orders/{blanket_id}/call-off")
async def create_call_off(blanket_id: str, payload: CallOffCreate, request: Request) -> Dict[str, Any]:
    """P2 — call-off (release) terhadap Blanket PO → PO anak normal (2.a).

    4.b over-call (qty/nilai > sisa) DIIZINKAN tapi memaksa approval. 3.b override harga
    wajib alasan. 5.a kontrak kadaluarsa/habis → ditolak (di prepare_call_off).
    """
    actor = await require_permission(request, "purchase_order", "create")
    prep = await blanket_po_service.prepare_call_off(blanket_id, payload, actor)
    notes = []
    if prep["has_override"]:
        notes.append(f"override harga: {prep['price_override_reason']}")
    if prep["force_approval"]:
        notes.append("over-call: " + "; ".join(prep["over_items"]))
    po = await _create_po_core(
        prep["po_payload"], actor, po_type="call_off", parent=prep["blanket"],
        force_approval=prep["force_approval"], force_reason=prep["force_reason"],
        extra_note="; ".join(notes))
    await blanket_po_service.recompute_blanket_drawdown(prep["blanket"], persist=True)
    await audit(actor["name"], "po_call_off_created", "purchase_order", po["id"], {
        "po_number": po.get("po_number"), "blanket_id": blanket_id,
        "blanket_po_number": prep["blanket"].get("po_number"),
        "over_call": prep["force_approval"], "price_override": prep["has_override"]})
    return po


@router.post("/purchase-orders/{blanket_id}/close-contract")
async def close_blanket_contract(blanket_id: str, payload: BlanketCloseRequest, request: Request) -> Dict[str, Any]:
    """P2 — tutup kontrak Blanket secara manual (call-off baru ditolak — 5.a)."""
    actor = await require_permission(request, "purchase_order", "update")
    result = await blanket_po_service.close_blanket(blanket_id, payload.reason, actor)
    await audit(actor["name"], "blanket_po_closed", "purchase_order", blanket_id,
                {"reason": payload.reason})
    return result


@router.post("/purchase-orders/{po_id}/amend")
async def amend_purchase_order(po_id: str, payload: PurchaseOrderAmend, request: Request) -> Dict[str, Any]:
    """Phase 7.2 — amandemen PO (item/supplier/tanggal/catatan) + version history + re-approval penuh.

    Aturan owner: ubah semua field (1.c); SELALU re-approval dari awal (2.a); boleh saat partial
    receiving — qty tak boleh < qty diterima & item ber-penerimaan tak bisa dihapus (3.b); simpan
    snapshot penuh + diff tiap versi (4.a); alasan + audit WAJIB (5.a).

    Domain logic diekstrak ke ``services/po_amendment_service.py`` (jaga batas ukuran router ≤800).
    Service mengembalikan ``{po, needs_approval}``; router memutuskan inbound task / notifikasi.
    """
    actor = await require_permission(request, "purchase_order", "update")
    result = await amend_po_service(po_id, payload, actor)
    updated = result["po"]
    if result["needs_approval"]:
        from services.notification_service import notify_po_awaiting_approval
        await notify_po_awaiting_approval(updated)
    else:
        await _create_inbound_tasks_for_po(updated)
    return safe_doc(await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}))


@router.post("/purchase-orders/{po_id}/approve")
async def approve_purchase_order(po_id: str, request: Request) -> Dict[str, Any]:
    """Fase 1B — approve PO (role dinamis dari matriks). Setelah approve, PO
    masuk status 'pending' dan inbound receiving task otomatis dibuat."""
    actor = await current_user(request)
    po = safe_doc(await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}))
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order tidak ditemukan")
    if po.get("status") != "waiting_approval":
        raise HTTPException(status_code=409, detail=f"PO status '{po.get('status')}' tidak menunggu approval")
    required = po.get("required_approval_role")
    if not role_satisfies(actor.get("role"), required):
        raise HTTPException(
            status_code=403,
            detail=f"Approval PO butuh role minimal '{required}'. Role Anda: '{actor.get('role')}'.")
    # H2 — Segregation of Duties: pembuat PO tidak boleh menyetujui PO-nya sendiri.
    creator_id = po.get("created_by_id")
    if creator_id and creator_id == actor.get("id"):
        raise HTTPException(
            status_code=403,
            detail="Pemisahan tugas (SoD): pembuat PO tidak boleh menyetujui PO sendiri. Minta approver lain.")

    # Fase 7.1 — approval BERJENJANG: tandai level berjalan approved, lalu lanjut/selesai.
    chain = po.get("approval_chain") or [{"level": 1, "required_role": required, "status": "pending",
                                          "approved_by": "", "approved_by_id": "", "approved_at": ""}]
    pending = current_pending_level(chain)
    if pending is None:
        raise HTTPException(status_code=409, detail="Semua tingkat approval sudah disetujui.")
    pending["status"] = "approved"
    pending["approved_by"] = actor["name"]
    pending["approved_by_id"] = actor.get("id", "")
    pending["approved_at"] = now_iso()

    next_pending = current_pending_level(chain)
    if next_pending is not None:
        # Masih ada tingkat berikutnya → tetap menunggu approval tingkat selanjutnya.
        updated = await db.purchase_orders.find_one_and_update(
            {"id": po_id},
            {"$set": {"status": "waiting_approval", "approval_status": "pending",
                      "approval_chain": chain, "required_approval_role": next_pending["required_role"],
                      "approval_level_current": next_pending["level"], "updated_at": now_iso()},
             "$push": {"timeline": timeline_entry(
                 "approved_level", f"Disetujui tingkat {pending['level']} ({pending.get('label','')})",
                 actor["name"], f"Lanjut ke {next_pending.get('label', next_pending['required_role'])}")}},
            projection={"_id": 0}, return_document=ReturnDocument.AFTER)
        try:
            from services.notification_service import notify_po_awaiting_approval
            await notify_po_awaiting_approval(updated)
        except Exception:  # noqa: BLE001
            pass
        await audit(actor["name"], "po_approved_level", "purchase_order", po_id,
                    {"po_number": po.get("po_number"), "level": pending["level"],
                     "next_role": next_pending["required_role"]})
        return safe_doc(updated)

    # Semua tingkat selesai → PO disetujui penuh.
    updated = await db.purchase_orders.find_one_and_update(
        {"id": po_id},
        {"$set": {"status": "pending", "approval_status": "approved", "approval_chain": chain,
                  "approval_level_current": 0,
                  "approved_by": actor["name"], "approved_at": now_iso(), "updated_at": now_iso()},
         "$push": {"timeline": timeline_entry(
             "approved", f"Disetujui penuh ({len(chain)} tingkat)", actor["name"],
             f"tingkat akhir oleh role {actor.get('role')}")}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    # Buat inbound task setelah PO disetujui penuh
    await _create_inbound_tasks_for_po(updated)
    await audit(actor["name"], "po_approved", "purchase_order", po_id,
                {"po_number": po.get("po_number"), "total_amount": po.get("total_amount"),
                 "levels": len(chain)})
    return safe_doc(updated)


@router.post("/purchase-orders/{po_id}/reject")
async def reject_purchase_order(po_id: str, request: Request) -> Dict[str, Any]:
    """Fase 3 — tolak PO yang menunggu approval (role dinamis dari matriks).
    PO → status 'rejected'; tidak ada inbound task yang dibuat."""
    actor = await current_user(request)
    po = safe_doc(await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}))
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order tidak ditemukan")
    if po.get("status") != "waiting_approval":
        raise HTTPException(status_code=409, detail=f"PO status '{po.get('status')}' tidak menunggu approval")
    required = po.get("required_approval_role")
    if not role_satisfies(actor.get("role"), required):
        raise HTTPException(
            status_code=403,
            detail=f"Reject PO butuh role minimal '{required}'. Role Anda: '{actor.get('role')}'.")
    body = {}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}
    reason = (body or {}).get("reason", "")
    updated = await db.purchase_orders.find_one_and_update(
        {"id": po_id},
        {"$set": {"status": "rejected", "approval_status": "rejected",
                  "rejected_by": actor["name"], "rejection_reason": reason,
                  "rejected_at": now_iso(), "updated_at": now_iso()},
         "$push": {"timeline": timeline_entry("rejected", "Ditolak", actor["name"], reason)}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    await audit(actor["name"], "po_rejected", "purchase_order", po_id,
                {"po_number": po.get("po_number"), "reason": reason})
    return safe_doc(updated)


@router.get("/purchase-orders/{po_id}")
async def get_purchase_order(po_id: str, request: Request) -> Dict[str, Any]:
    """Get purchase order detail."""
    await require_permission(request, "purchase_order", "view")
    ctx = await entity_ctx(request)
    po = safe_doc(await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}))
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order tidak ditemukan")
    assert_entity_access(po, "purchase_orders", ctx)

    # P2 — Blanket PO: lampirkan drawdown (called/remaining + daftar call-off).
    if po.get("po_type") == "blanket":
        draw = await blanket_po_service.recompute_blanket_drawdown(po, persist=True)
        for k in ("contract_items", "value_called", "value_remaining", "contract_status",
                  "call_offs", "call_off_count"):
            po[k] = draw[k]
        return po

    # Get related inbound tasks
    tasks = await db.wms_tasks.find({"po_id": po_id}, {"_id": 0}).to_list(100)
    po["inbound_tasks"] = tasks
    # Depth 1C — ringkasan keuangan + retur terkait
    po["financials"] = _po_financials(po)
    rets = await db.purchase_returns.find({"po_id": po_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    po["returns"] = rets

    return po


@router.post("/purchase-orders/{po_id}/pay")
async def pay_purchase_order(po_id: str, payload: POPaymentCreate, request: Request) -> Dict[str, Any]:
    """P0-B (SSOT AP) — Pembayaran PO DINONAKTIFKAN.

    Hutang (AP) & pembayaran ke supplier kini dikelola SATU PINTU melalui
    Vendor Bill (menu "Tagihan Supplier"). Endpoint ini sengaja diblokir agar
    tidak terjadi double-count hutang / kas keluar ganda dengan Vendor Bill.
    """
    await require_permission(request, "purchase_order", "update")
    raise HTTPException(
        status_code=400,
        detail=("Pembayaran langsung di PO dinonaktifkan. Hutang & pembayaran supplier "
                "dikelola via Tagihan Supplier (Vendor Bill). Buat/posting Vendor Bill "
                "untuk PO ini, lalu bayar dari sana."))


@router.post("/purchase-orders/{po_id}/close")
async def close_purchase_order_short(po_id: str, payload: POCloseRequest, request: Request) -> Dict[str, Any]:
    """Depth 1A — tutup PO yang kurang terima (short-close). Sisa item tak diharapkan lagi."""
    actor = await require_permission(request, "purchase_order", "update")
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order tidak ditemukan")
    if po.get("status") not in ("receiving", "partial", "pending"):
        raise HTTPException(status_code=400, detail=f"PO status '{po.get('status')}' tidak bisa ditutup-kurang")
    updated = await db.purchase_orders.find_one_and_update(
        {"id": po_id},
        {"$set": {"status": "closed_short", "close_reason": payload.reason,
                  "closed_by": actor["name"], "closed_at": now_iso(), "updated_at": now_iso()},
         "$push": {"timeline": timeline_entry(
             "closed_short", "Ditutup-kurang", actor["name"], payload.reason or "")}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    # Batalkan inbound task yang belum selesai
    await db.wms_tasks.update_many(
        {"po_id": po_id, "status": {"$nin": ["completed", "cancelled"]}},
        {"$set": {"status": "cancelled", "updated_at": now_iso(),
                  "cancel_reason": "PO ditutup-kurang"}})
    await audit(actor["name"], "po_closed_short", "purchase_order", po_id,
                {"po_number": po.get("po_number"), "reason": payload.reason})
    return safe_doc(updated)


@router.get("/purchase-orders/payables/summary")
async def payables_summary(request: Request, entity_id: str = None) -> Dict[str, Any]:
    """Depth 1C — ringkasan hutang (AP) ke supplier + aging per PO."""
    await require_permission(request, "purchase_order", "view")
    from datetime import datetime, timezone
    ctx = await entity_ctx(request)
    q: Dict[str, Any] = {"status": {"$in": list(AP_LIABILITY_STATUSES)}}
    q = resolve_list_scope("purchase_orders", q, ctx, entity_id)
    pos = await db.purchase_orders.find(q, {"_id": 0}).to_list(1000)
    now = datetime.now(timezone.utc)
    by_supplier: Dict[str, Dict[str, Any]] = {}
    aging = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, ">90": 0.0}
    total_outstanding = 0.0
    rows = []
    for po in pos:
        fin = _po_financials(po)
        out = fin["outstanding"]
        if out <= 0.01:
            continue
        total_outstanding += out
        # aging dari expected_delivery_date / created_at
        ref_date = po.get("expected_delivery_date") or po.get("created_at") or ""
        days = 0
        try:
            d = datetime.fromisoformat(ref_date.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            days = (now - d).days
        except Exception:  # noqa: BLE001
            days = 0
        bucket = "0-30" if days <= 30 else "31-60" if days <= 60 else "61-90" if days <= 90 else ">90"
        aging[bucket] += out
        sid = po.get("supplier_id") or po.get("supplier_name") or "—"
        sup = by_supplier.setdefault(sid, {
            "supplier_id": po.get("supplier_id", ""), "supplier_name": po.get("supplier_name", "—"),
            "outstanding": 0.0, "po_count": 0})
        sup["outstanding"] = round(sup["outstanding"] + out, 2)
        sup["po_count"] += 1
        rows.append({
            "po_id": po["id"], "po_number": po.get("po_number"), "supplier_name": po.get("supplier_name"),
            "supplier_id": po.get("supplier_id", ""), "status": po.get("status"),
            "total_amount": fin["total_amount"], "amount_paid": fin["amount_paid"],
            "returned_amount": fin["returned_amount"], "outstanding": out,
            "payment_status": fin["payment_status"], "days_outstanding": days, "aging_bucket": bucket,
            "expected_delivery_date": po.get("expected_delivery_date", ""),
        })
    rows.sort(key=lambda r: (-r["days_outstanding"], -r["outstanding"]))
    return {
        "total_outstanding": round(total_outstanding, 2),
        "aging": {k: round(v, 2) for k, v in aging.items()},
        "by_supplier": sorted(by_supplier.values(), key=lambda s: -s["outstanding"]),
        "purchase_orders": rows,
    }


@router.post("/purchase-orders/{po_id}/cancel")
async def cancel_purchase_order(po_id: str, request: Request) -> Dict[str, Any]:
    """Cancel a purchase order."""
    actor = await require_permission(request, "purchase_order", "update")
    
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order tidak ditemukan")
    
    if po["status"] not in ["pending", "receiving", "waiting_approval"]:
        raise HTTPException(status_code=400, detail=f"PO dengan status {po['status']} tidak bisa dibatalkan")
    
    # Update PO status
    updated_po = await db.purchase_orders.find_one_and_update(
        {"id": po_id},
        {"$set": {"status": "cancelled", "cancelled_by": actor["name"],
                  "cancelled_at": now_iso(), "updated_at": now_iso()},
         "$push": {"timeline": timeline_entry(
             "cancelled", "PO dibatalkan", actor["name"], "")}},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    # Cancel related inbound tasks
    await db.wms_tasks.update_many(
        {"po_id": po_id},
        {"$set": {"status": "cancelled", "updated_at": now_iso()}}
    )
    
    await audit(actor["name"], "po_cancelled", "purchase_order", po_id, {})
    
    return safe_doc(updated_po)
