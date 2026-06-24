"""Depth #2 — Purchase Requisition (PR) service + Reorder/Replenishment.

Hulu procurement: kebutuhan beli diajukan sebagai PR → approval → konversi ke PO.
Sumber PR: manual | reorder (saran replenishment) | special_order (jembatan OD).

Koleksi kanonik: `purchase_requisitions` (prefix pr_).
Status: draft → pending_approval → approved → converted | rejected | cancelled.

Invarian (verify_data_integrity L4-PR):
  - item.subtotal == est_price × quantity
  - total_est_amount == Σ item.subtotal
  - status 'converted' ⟹ po_id terisi
"""
import re
from typing import Any, Dict, List, Optional
from db import db
from core_utils import now_iso, new_id, DEFAULT_ENTITY_ID, safe_doc, timeline_entry, next_doc_number
from services.config_service import evaluate_approval, role_satisfies, compute_order_pricing

# Status PO yang dianggap "pipeline terbuka" → menambah on_order (incoming) produk.
OPEN_PO_STATUSES = {"waiting_approval", "pending", "receiving", "partial"}
PR_TERMINAL = {"converted", "rejected", "cancelled"}


async def next_pr_number() -> str:
    last = await db.purchase_requisitions.find_one(
        {"number": {"$regex": r"^PR-"}}, sort=[("number", -1)])
    n = (int(re.search(r"(\d+)$", last["number"]).group(1)) + 1) if (last and last.get("number")) else 1
    return f"PR-{n:05d}"


async def _wh_name(warehouse_id: str) -> str:
    if not warehouse_id:
        return ""
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0, "name": 1})
    return (wh or {}).get("name", "")


async def _enrich_items(raw_items: List[Any]) -> (List[Dict[str, Any]], float):
    """Bangun baris PR + subtotal. product_id opsional (non-katalog/special order)."""
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(2000)}
    items: List[Dict[str, Any]] = []
    total = 0.0
    for it in raw_items:
        pid = (getattr(it, "product_id", "") or "").strip()
        est_price = round(float(getattr(it, "est_price", 0) or 0), 2)
        qty = float(getattr(it, "quantity", 0) or 0)
        if qty <= 0:
            raise ValueError("Quantity item harus > 0")
        sku = ""
        name = (getattr(it, "description", "") or "").strip()
        if pid:
            prod = products.get(pid)
            if not prod:
                raise ValueError(f"Produk {pid} tidak ditemukan")
            sku = prod.get("sku", "")
            name = name or prod.get("name", "")
            if est_price <= 0:
                est_price = float(prod.get("harga_pokok", 0) or prod.get("price", 0) or 0)
        if not name:
            raise ValueError("Deskripsi item wajib diisi untuk item non-katalog")
        subtotal = round(est_price * qty, 2)
        total += subtotal
        items.append({
            "product_id": pid, "sku": sku, "product_name": name,
            "description": name, "quantity": qty,
            "unit": getattr(it, "unit", "meter") or "meter",
            "est_price": est_price, "subtotal": subtotal,
            "note": getattr(it, "note", "") or "",
        })
    return items, round(total, 2)


async def create_requisition(payload, created_by: str, created_by_id: str = "") -> Dict[str, Any]:
    """Buat PR (draft/pending). Approval dievaluasi dari total_est (matriks)."""
    entity_id = payload.entity_id or DEFAULT_ENTITY_ID
    warehouse_id = payload.warehouse_id or ""
    if warehouse_id and not await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0}):
        raise ValueError("Gudang tidak ditemukan")

    items, total = await _enrich_items(payload.items)
    if not items:
        raise ValueError("Minimal satu item kebutuhan")

    # Supplier preferensi (opsional)
    pref_sup_id = getattr(payload, "preferred_supplier_id", "") or ""
    pref_sup_name = ""
    if pref_sup_id:
        sup = await db.suppliers.find_one({"id": pref_sup_id}, {"_id": 0, "name": 1})
        if not sup:
            raise ValueError("Supplier preferensi tidak ditemukan")
        pref_sup_name = sup.get("name", "")

    appr = await evaluate_approval("purchase_requisition", total, entity_id)
    needs = appr["requires_approval"]
    submit_now = bool(getattr(payload, "submit_now", False))
    status = "pending_approval" if (needs and submit_now) else ("pending_approval" if submit_now else "draft")
    # Jika tak butuh approval & submit_now → langsung 'approved' (siap konversi)
    if submit_now and not needs:
        status = "approved"

    now = now_iso()
    doc = {
        "id": new_id("pr"), "number": await next_pr_number(),
        "entity_id": entity_id,
        "warehouse_id": warehouse_id, "warehouse_name": await _wh_name(warehouse_id),
        "items": items, "total_est_amount": total,
        "source": getattr(payload, "source", "manual") or "manual",
        "source_ref_id": getattr(payload, "source_ref_id", "") or "",
        "preferred_supplier_id": pref_sup_id, "preferred_supplier_name": pref_sup_name,
        "reason": getattr(payload, "reason", "") or "",
        "needed_by_date": getattr(payload, "needed_by_date", "") or "",
        "notes": getattr(payload, "notes", "") or "",
        "status": status,
        "approval_required": needs,
        "required_approval_role": appr["required_role"],
        "approval_status": "approved" if status == "approved" else ("pending" if status == "pending_approval" else "not_submitted"),
        "po_id": "", "po_number": "",
        "created_by": created_by, "created_by_id": created_by_id,
        "approved_by": None, "approved_at": None,
        "rejected_by": None, "rejected_at": None, "reject_reason": None,
        "created_at": now, "updated_at": now,
    }
    await db.purchase_requisitions.insert_one(dict(doc))
    return safe_doc(doc)


async def submit_requisition(pr_id: str) -> Dict[str, Any]:
    pr = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
    if not pr:
        raise ValueError("PR tidak ditemukan")
    if pr["status"] != "draft":
        raise ValueError("Hanya draft yang bisa disubmit")
    # Jika tak butuh approval → langsung approved
    new_status = "pending_approval" if pr.get("approval_required") else "approved"
    appr_status = "pending" if new_status == "pending_approval" else "approved"
    sets = {"status": new_status, "approval_status": appr_status, "updated_at": now_iso()}
    if new_status == "approved":
        sets["approved_by"] = "system (auto)"
        sets["approved_at"] = now_iso()
    await db.purchase_requisitions.update_one({"id": pr_id}, {"$set": sets})
    return safe_doc(await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0}))


async def approve_requisition(pr_id: str, actor: Dict[str, Any], notes: str = "") -> Dict[str, Any]:
    pr = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
    if not pr:
        raise ValueError("PR tidak ditemukan")
    if pr["status"] not in ("draft", "pending_approval"):
        raise ValueError(f"PR {pr['number']} sudah {pr['status']}")
    required = pr.get("required_approval_role")
    if not role_satisfies(actor.get("role"), required):
        raise ValueError(f"Approval PR butuh role minimal '{required or 'manager'}'. Role Anda: '{actor.get('role')}'.")
    # H2 — Segregation of Duties: pembuat PR tidak boleh menyetujui PR-nya sendiri.
    creator_id = pr.get("created_by_id")
    if creator_id and creator_id == actor.get("id"):
        raise ValueError("Pemisahan tugas (SoD): pembuat PR tidak boleh menyetujui PR sendiri. Minta approver lain.")
    now = now_iso()
    await db.purchase_requisitions.update_one({"id": pr_id}, {"$set": {
        "status": "approved", "approval_status": "approved",
        "approved_by": actor.get("name", "Admin"), "approved_at": now,
        "decision_notes": notes, "updated_at": now,
    }})
    return safe_doc(await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0}))


async def reject_requisition(pr_id: str, actor: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    pr = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
    if not pr:
        raise ValueError("PR tidak ditemukan")
    if pr["status"] not in ("draft", "pending_approval"):
        raise ValueError(f"PR {pr['number']} sudah {pr['status']}")
    required = pr.get("required_approval_role")
    if not role_satisfies(actor.get("role"), required):
        raise ValueError(f"Reject PR butuh role minimal '{required or 'manager'}'. Role Anda: '{actor.get('role')}'.")
    now = now_iso()
    await db.purchase_requisitions.update_one({"id": pr_id}, {"$set": {
        "status": "rejected", "approval_status": "rejected",
        "rejected_by": actor.get("name", "Admin"), "rejected_at": now,
        "reject_reason": reason, "updated_at": now,
    }})
    return safe_doc(await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0}))


async def cancel_requisition(pr_id: str) -> Dict[str, Any]:
    pr = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
    if not pr:
        raise ValueError("PR tidak ditemukan")
    if pr["status"] in PR_TERMINAL:
        raise ValueError(f"PR {pr['number']} sudah {pr['status']}")
    await db.purchase_requisitions.update_one({"id": pr_id}, {"$set": {
        "status": "cancelled", "updated_at": now_iso()}})
    return safe_doc(await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0}))


async def convert_to_po(pr_id: str, supplier_id: str, actor: Dict[str, Any],
                        warehouse_id: str = "", expected_delivery_date: str = "",
                        notes: str = "") -> Dict[str, Any]:
    """Konversi PR approved → Purchase Order (semua item WAJIB punya product_id)."""
    from routers.purchase_orders import _create_inbound_tasks_for_po
    pr = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
    if not pr:
        raise ValueError("PR tidak ditemukan")
    if pr["status"] != "approved":
        raise ValueError(f"Hanya PR 'approved' yang bisa dikonversi (status: {pr['status']})")
    if pr.get("po_id"):
        raise ValueError("PR sudah pernah dikonversi ke PO")
    non_catalog = [it for it in pr.get("items", []) if not it.get("product_id")]
    if non_catalog:
        raise ValueError("Ada item non-katalog. Buat produk dulu atau proses manual — tidak bisa auto-konversi ke PO.")

    supplier_id = supplier_id or pr.get("preferred_supplier_id", "")
    if not supplier_id:
        raise ValueError("Supplier wajib dipilih untuk konversi ke PO")
    supplier = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})
    if not supplier:
        raise ValueError("Supplier tidak ditemukan")

    warehouse_id = warehouse_id or pr.get("warehouse_id", "")
    warehouse = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0}) if warehouse_id else None
    if not warehouse:
        raise ValueError("Gudang wajib dipilih untuk konversi ke PO")

    entity_id = pr.get("entity_id") or DEFAULT_ENTITY_ID
    products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(2000)}
    from services.supplier_service import resolve_price
    raw_items = []
    for it in pr["items"]:
        prod = products.get(it["product_id"])
        if not prod:
            raise ValueError(f"Produk {it['product_id']} tidak ditemukan")
        # Depth #3 — prioritas harga: est_price PR → price-list supplier → harga produk.
        price = float(it.get("est_price", 0) or 0)
        unit = it.get("unit", "meter")
        if price <= 0:
            resolved = await resolve_price(supplier_id, it["product_id"], float(it["quantity"]))
            price = float(resolved.get("price", 0) or 0)
            if resolved.get("found") and resolved.get("unit"):
                unit = resolved["unit"]
        if price <= 0:
            price = float(prod.get("price", 0) or 0)
        qty = float(it["quantity"])
        raw_items.append({
            "product_id": prod["id"], "sku": prod["sku"], "product_name": prod["name"],
            "quantity": qty, "unit": unit, "price": price,
            "discount_percent": 0, "received_qty": 0.0,
        })

    # P0-1 — breakdown harga PO (PPN Masukan; PR tanpa diskon item/order). Invariant-safe.
    pricing = await compute_order_pricing(raw_items, entity_id, 0.0, cfg_section="purchasing")
    items = pricing["items"]
    total_amount = pricing["total_amount"]
    grand_total = pricing["grand_total"]

    appr = await evaluate_approval("purchase_order", total_amount, entity_id)
    needs_approval = appr["requires_approval"]
    required_role = appr["required_role"]
    approval_reason = "amount_threshold" if needs_approval else ""

    # Depth #3 — guard penyimpangan harga vs price-list supplier.
    from services.supplier_service import assess_price_deviation
    from services.config_service import get_effective_settings
    settings = await get_effective_settings(entity_id)
    threshold = float(settings.get("purchasing", {}).get("price_deviation_approval_percent", 10.0) or 10.0)
    price_deviation = await assess_price_deviation(supplier_id, items, threshold)
    if price_deviation["flagged"]:
        needs_approval = True
        required_role = required_role or "manager"
        approval_reason = "price_deviation" if approval_reason == "" else "amount_threshold+price_deviation"

    sup_contact = " | ".join([x for x in [supplier.get("pic_name", ""), supplier.get("phone", "")] if x])
    now = now_iso()
    po = {
        "id": new_id("po"), "po_number": await next_doc_number("purchase_orders", "po_number", "PO-", entity_id=entity_id),
        "supplier_id": supplier_id, "supplier_name": supplier.get("name", ""),
        "supplier_contact": sup_contact, "supplier_npwp": supplier.get("npwp", ""),
        "warehouse_id": warehouse_id, "warehouse_name": warehouse["name"],
        "warehouse_city": warehouse.get("city", ""),
        "items": items, "total_amount": total_amount, "entity_id": entity_id,
        # P0-1 — breakdown diskon + PPN (Faktur Pajak Masukan). Invariant-safe.
        "items_discount_total": pricing["items_discount_total"],
        "order_discount_percent": pricing["order_discount_percent"],
        "order_discount_amount": pricing["order_discount_amount"],
        "discount_total": pricing["discount_total"],
        "net_subtotal": pricing["net_subtotal"],
        "dpp": pricing["dpp"], "ppn_rate": pricing["ppn_rate"],
        "ppn_mode": pricing["ppn_mode"], "is_pkp": pricing["is_pkp"],
        "ppn_amount": pricing["ppn_amount"], "grand_total": grand_total, "tax_mode": "",
        "expected_delivery_date": expected_delivery_date or pr.get("needed_by_date", ""),
        "notes": notes or f"Dari {pr['number']}",
        "status": "waiting_approval" if needs_approval else "pending",
        "approval_required": needs_approval, "required_approval_role": required_role,
        "approval_status": "pending" if needs_approval else "not_required",
        "approval_amount": total_amount,
        "approval_reason": approval_reason, "price_deviation": price_deviation,
        "amount_paid": 0.0, "returned_amount": 0.0, "outstanding": round(grand_total, 2),
        "payment_status": "unpaid", "payments": [],
        "source_pr_id": pr_id, "source_pr_number": pr["number"],
        "timeline": (
            [timeline_entry("created", "PO dibuat dari " + pr["number"],
                            actor.get("name", "Admin"), f"{len(items)} item · Rp {total_amount:,.0f}")]
            + ([timeline_entry("submitted_for_approval", f"Menunggu persetujuan {required_role}",
                               actor.get("name", "Admin"),
                               f"deviasi harga +{price_deviation['max_deviation_pct']}%" if price_deviation["flagged"] else "nilai melebihi batas")]
               if needs_approval else [])
        ),
        "created_by": actor.get("name", "Admin"), "created_by_id": actor.get("id", ""),
        "created_at": now, "updated_at": now,
    }
    await db.purchase_orders.insert_one(dict(po))
    if not needs_approval:
        await _create_inbound_tasks_for_po(po)
    else:
        # Depth #3 — notifikasi ke role approver.
        from services.notification_service import notify_po_awaiting_approval
        await notify_po_awaiting_approval(po)

    await db.purchase_requisitions.update_one({"id": pr_id}, {"$set": {
        "status": "converted", "po_id": po["id"], "po_number": po["po_number"],
        "converted_by": actor.get("name", "Admin"), "converted_at": now, "updated_at": now,
    }})
    return {"pr": safe_doc(await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})),
            "po": safe_doc(po)}


# ─── Reorder Point / Replenishment (Depth #2b) ───────────────────────────────

async def reorder_suggestions(entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Saran replenishment: produk dgn reorder_point>0 yang proyeksi stok
    (available + on_order) <= reorder_point. Menghindari double-order via on_order."""
    products = await db.products.find({"status": "active"}, {"_id": 0}).to_list(2000)

    # available per produk (Σ available_qty balances, owner-scoped bila entity_id)
    bal_q: Dict[str, Any] = {}
    if entity_id and entity_id != "all":
        bal_q["owner_entity_id"] = entity_id
    avail: Dict[str, float] = {}
    async for b in db.inventory_balances.find(bal_q, {"_id": 0, "product_id": 1, "available_qty": 1}):
        avail[b["product_id"]] = avail.get(b["product_id"], 0.0) + float(b.get("available_qty", 0) or 0)

    # on_order per produk (Σ qty-received pada PO terbuka), owner-scoped bila entity_id
    po_q: Dict[str, Any] = {"status": {"$in": list(OPEN_PO_STATUSES)}}
    if entity_id and entity_id != "all":
        po_q["entity_id"] = entity_id
    on_order: Dict[str, float] = {}
    async for po in db.purchase_orders.find(po_q, {"_id": 0, "items": 1}):
        for it in po.get("items", []):
            gap = float(it.get("quantity", 0) or 0) - float(it.get("received_qty", 0) or 0)
            if gap > 0:
                on_order[it["product_id"]] = on_order.get(it["product_id"], 0.0) + gap

    # supplier preferensi via master (match nama supplier produk → suppliers)
    suppliers = await db.suppliers.find({}, {"_id": 0}).to_list(500)
    sup_by_name = {s["name"]: s for s in suppliers}

    from services.supplier_service import resolve_price
    from datetime import datetime, timezone, timedelta
    today = datetime.now(timezone.utc).date()

    rows = []
    for p in products:
        rop = float(p.get("reorder_point", 0) or 0)
        if rop <= 0:
            continue
        av = round(avail.get(p["id"], 0.0), 2)
        oo = round(on_order.get(p["id"], 0.0), 2)
        projected = round(av + oo, 2)
        if projected > rop:
            continue
        roq = float(p.get("reorder_qty", 0) or 0)
        suggested = roq if roq > 0 else round(rop - projected, 2)
        if suggested <= 0:
            suggested = round(max(rop - projected, 0.0), 2)
        pref = sup_by_name.get(p.get("supplier", ""), {})
        pref_id = pref.get("id", "")
        # Depth #3 — harga price-list + lead-time supplier preferensi → ETA.
        resolved = await resolve_price(pref_id, p["id"], suggested) if pref_id else {}
        est_price = float(resolved.get("price", 0) or 0) if resolved.get("price", 0) else \
            float(p.get("harga_pokok", 0) or p.get("price", 0) or 0)
        lead = int(resolved.get("lead_time_days", 0) or 0) or int(pref.get("lead_time_days", 0) or 0)
        eta = (today + timedelta(days=lead)).isoformat() if lead > 0 else ""
        rows.append({
            "product_id": p["id"], "sku": p.get("sku", ""), "product_name": p.get("name", ""),
            "unit": resolved.get("unit") or p.get("base_unit", "meter"),
            "available": av, "on_order": oo, "projected": projected,
            "reorder_point": rop, "reorder_qty": roq, "suggested_qty": suggested,
            "est_price": round(est_price, 2),
            "price_source": resolved.get("source", "product_fallback"),
            "lead_time_days": lead,
            "expected_arrival_date": eta,
            "preferred_supplier_id": pref_id,
            "preferred_supplier_name": pref.get("name", p.get("supplier", "")),
        })
    rows.sort(key=lambda r: (r["projected"] - r["reorder_point"]))
    return {"items": rows, "count": len(rows),
            "entity_id": entity_id or "all", "generated_at": now_iso()}
