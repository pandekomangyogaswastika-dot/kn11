"""Notification service — pembuatan notifikasi + generator dari event REAL.

Tidak ada data mock: notifikasi dihitung dari kondisi nyata di
`inventory_balances` (stok menipis) dan `sales_orders` (reservasi mendekati
kedaluwarsa 3 hari). Dedupe berbasis `ref` agar tidak menumpuk duplikat.
"""
from typing import Any, Dict, Optional
from datetime import datetime, timezone, timedelta
from db import db
from core_utils import new_id, now_iso, safe_doc
from services.inventory_service import product_summary

LOW_STOCK_THRESHOLD = 100.0  # meter — ambang batas default stok menipis


async def _has_unread(notif_type: str, ref: str) -> bool:
    return bool(await db.notifications.find_one(
        {"type": notif_type, "ref": ref, "read": False}, {"_id": 1}
    ))


async def create_notification(
    *, notif_type: str, title: str, body: str, severity: str = "info",
    link: str = "", entity_id: Optional[str] = None, recipient_role: str = "all",
    recipient_user: Optional[str] = None, ref: str = "", dedupe: bool = True,
    action_type: str = "", action_id: str = "", action_role: str = "",
) -> Optional[Dict[str, Any]]:
    """Buat 1 notifikasi. Return None bila di-dedupe (sudah ada yang belum dibaca).

    `action_type`/`action_id`/`action_role` → aksi inline (mis. approve PO langsung
    dari kartu notifikasi). `action_role` = role minimum yang boleh aksi.
    """
    if dedupe and ref and await _has_unread(notif_type, ref):
        return None
    doc = {
        "id": new_id("ntf"), "entity_id": entity_id,
        "recipient_role": recipient_role, "recipient_user": recipient_user,
        "type": notif_type, "title": title, "body": body, "link": link,
        "severity": severity, "ref": ref, "read": False, "created_at": now_iso(),
        "action_type": action_type, "action_id": action_id, "action_role": action_role,
    }
    await db.notifications.insert_one(doc)
    return safe_doc(doc)


async def notify_po_awaiting_approval(po: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Depth #3 — notifikasi ke role approver saat PO masuk waiting_approval.

    Ditujukan ke `required_approval_role` (mis. manager). Dedupe via ref po_appr:<id>.
    Menyertakan alasan deviasi harga bila ada + aksi approve inline.
    """
    role = po.get("required_approval_role") or "manager"
    dev = po.get("price_deviation") or {}
    extra = ""
    if dev.get("flagged"):
        extra = f" Harga di atas price-list (+{dev.get('max_deviation_pct')}%)."
    return await create_notification(
        notif_type="po_approval", ref=f"po_appr:{po.get('id', '')}",
        title=f"PO menunggu persetujuan: {po.get('po_number', '')}",
        body=(f"{po.get('supplier_name', '')} · Rp {float(po.get('total_amount', 0)):,.0f}.{extra} "
              f"Perlu persetujuan {role}."),
        severity="warning" if dev.get("flagged") else "info",
        link="purchase-approval", entity_id=po.get("entity_id"), recipient_role=role,
        action_type="po_approve", action_id=po.get("id", ""), action_role=role,
    )


async def generate_system_notifications() -> int:
    """Pindai kondisi nyata sistem & buat notifikasi. Return jumlah yang dibuat."""
    created = 0

    # 1) Stok menipis (dari inventory_balances via product_summary)
    products = await db.products.find({"status": "active"}, {"_id": 0}).to_list(300)
    for product in products:
        summary = await product_summary(product["id"])
        if summary["available_qty"] < LOW_STOCK_THRESHOLD:
            note = await create_notification(
                notif_type="low_stock", ref=f"low_stock:{product['id']}",
                title=f"Stok menipis: {product['name']}",
                body=(f"Available {summary['available_qty']:.0f} "
                      f"{product.get('base_unit', 'meter')} (< {LOW_STOCK_THRESHOLD:.0f}). "
                      f"Pertimbangkan buat PO ulang."),
                severity="warning", link="operations", recipient_role="all",
            )
            if note:
                created += 1

    # 2) Reservasi mendekati kedaluwarsa (<= 24 jam) dari sales_orders
    soon = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    orders = await db.sales_orders.find(
        {"status": {"$in": ["reserved", "waiting_approval", "approved"]},
         "reservation_expires_at": {"$lte": soon}}, {"_id": 0}
    ).to_list(200)
    for order in orders:
        note = await create_notification(
            notif_type="reservation_expiring", ref=f"resv:{order['id']}",
            title=f"Reservasi akan kedaluwarsa: {order.get('number', '')}",
            body=(f"Order {order.get('number', '')} ({order.get('customer_name', '')}) "
                  f"reservasinya mendekati batas 3 hari. Segera approve/konfirmasi."),
            severity="warning", link="orders", entity_id=order.get("entity_id"),
            recipient_role="all",
        )
        if note:
            created += 1

    # 3) Order menunggu persetujuan (actionable, dari sales_orders)
    pending = await db.sales_orders.find({"status": "waiting_approval"}, {"_id": 0}).to_list(200)
    for order in pending:
        note = await create_notification(
            notif_type="order_approval", ref=f"appr:{order['id']}",
            title=f"Order menunggu persetujuan: {order.get('number', '')}",
            body=(f"{order.get('customer_name', '')} · Rp {float(order.get('total_amount', 0)):,.0f}. "
                  f"Memerlukan persetujuan manajer."),
            severity="info", link="orders", entity_id=order.get("entity_id"),
            recipient_role="all",
        )
        if note:
            created += 1

    # 4) Order split antar gudang (informasi fulfillment)
    splits = await db.sales_orders.find(
        {"is_split_warehouse": True, "status": {"$nin": ["cancelled", "expired", "done"]}}, {"_id": 0}
    ).to_list(200)
    for order in splits:
        note = await create_notification(
            notif_type="order_split", ref=f"split:{order['id']}",
            title=f"Order split antar gudang: {order.get('number', '')}",
            body=(f"Order {order.get('number', '')} dipenuhi dari beberapa gudang. "
                  f"Koordinasikan pengiriman gabungan."),
            severity="info", link="operations", entity_id=order.get("entity_id"),
            recipient_role="all",
        )
        if note:
            created += 1

    # 5) PO menunggu persetujuan (Depth #3 — approver notification, deduped)
    pending_po = await db.purchase_orders.find(
        {"status": "waiting_approval"}, {"_id": 0}).to_list(200)
    for po in pending_po:
        note = await notify_po_awaiting_approval(po)
        if note:
            created += 1

    return created
