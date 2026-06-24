"""AR Receipt service (EPIC3B) — Penerimaan pembayaran customer + aplikasi ke SO.

Mencatat penerimaan kas dari customer lalu meng-apply-nya ke sales_orders
(`payments[]`, `paid_total`, `payment_status`). Karena credit gate &
Collection Worklist sudah membaca `payments[]`/`payment_status`, AR otomatis
ter-update tanpa perubahan lapisan lain (lihat customer_service.compute_customer_credit).

Integrasi tambahan (audit fix):
  - P0-1: setiap penerimaan KAS (amount > 0) di-posting ke `cash_transactions`
    (direction=in, ref_type=ar_receipt). Routing: tunai → kas_kecil (per entitas),
    transfer/giro/qris → kas_besar (bank gabungan).
  - P2-5: kelebihan bayar (unapplied) → `customers.deposit_balance`; deposit dapat
    dipakai mendanai alokasi via `use_deposit_amount`.
  - P2-6: void/reversal — membalik payments[], void cash, dan koreksi deposit.

Alokasi:
  - Eksplisit: payload.allocations = [{order_id, amount}].
  - Otomatis (default): FIFO ke order terbuka tertua sampai dana habis.

Idempotensi nomor: AR-##### via next_doc_number (deletion-safe).
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc, DEFAULT_ENTITY_ID

# Re-use kontrak AR yang sama dengan engine kredit (SSOT tunggal — hindari drift).
from services.customer_service import (
    _order_grand_total as order_grand_total,
    _order_paid as order_paid,
    order_payment_method,
    DEAD_STATUSES,
    NON_AR_METHODS,
)

EPS = 0.01
CASH_METHODS = {"cash", "tunai", "kontan"}


def _payment_status(grand_total: float, paid: float) -> str:
    if paid >= grand_total - EPS:
        return "paid"
    if paid > EPS:
        return "partial"
    return "unpaid"


# ─── Cash posting (P0-1) ─────────────────────────────────────────────────────
def _cash_routing(method: str) -> tuple:
    """(cash_type, force_all_entity) berdasar metode pembayaran (P0-1/P3-9).

    Tunai/kontan → kas_kecil (per entitas). Transfer/giro/qris → kas_besar (bank).
    """
    if (method or "").lower() in CASH_METHODS:
        return "kas_kecil", False
    return "kas_besar", True


async def _post_cash_in(receipt: Dict[str, Any], actor: Dict[str, Any]) -> Optional[str]:
    """Posting kas masuk untuk penerimaan AR. Mengembalikan id cash_transaction."""
    amt = round(float(receipt.get("amount", 0) or 0), 2)
    if amt <= EPS:
        return None
    cash_type, force_all = _cash_routing(receipt.get("method", ""))
    entity_id = "all" if force_all else (receipt.get("entity_id") or DEFAULT_ENTITY_ID)
    number = await next_doc_number("cash_transactions", "number", "CASH-", entity_id=entity_id)
    cdoc = {
        "id": new_id("cash"),
        "number": number,
        "cash_type": cash_type,
        "direction": "in",
        "amount": amt,
        "category": "penagihan",
        "description": f"Penerimaan {receipt.get('number')} — {receipt.get('customer_name', '')}",
        "entity_id": entity_id,
        "ref_type": "ar_receipt",
        "ref_id": receipt["id"],
        "txn_date": receipt.get("receipt_date") or now_iso(),
        "status": "posted",
        "created_by": actor.get("name", "system"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.cash_transactions.insert_one(cdoc)
    return cdoc["id"]


# ─── Deposit (P2-5) ──────────────────────────────────────────────────────────
async def get_deposit_balance(customer_id: str) -> float:
    c = await db.customers.find_one({"id": customer_id}, {"_id": 0, "deposit_balance": 1})
    return round(float((c or {}).get("deposit_balance", 0) or 0), 2)


async def _adjust_deposit(customer_id: str, delta: float) -> None:
    if abs(delta) < EPS:
        return
    await db.customers.update_one(
        {"id": customer_id},
        {"$inc": {"deposit_balance": round(delta, 2)}, "$set": {"updated_at": now_iso()}},
    )


async def list_open_orders(customer_id: str) -> List[Dict[str, Any]]:
    """Order AR terbuka (ada outstanding) untuk customer, tertua dulu (FIFO)."""
    orders = await db.sales_orders.find({"customer_id": customer_id}, {"_id": 0}).to_list(2000)
    rows = []
    for o in orders:
        if o.get("status") in DEAD_STATUSES:
            continue
        if order_payment_method(o) in NON_AR_METHODS:
            continue
        gt = order_grand_total(o)
        paid = order_paid(o)
        outstanding = round(gt - paid, 2)
        if outstanding <= EPS:
            continue
        rows.append({
            "order_id": o["id"],
            "number": o.get("number", o["id"]),
            "grand_total": round(gt, 2),
            "paid_total": round(paid, 2),
            "outstanding": outstanding,
            "payment_status": o.get("payment_status") or _payment_status(gt, paid),
            "created_at": o.get("created_at"),
        })
    rows.sort(key=lambda r: str(r.get("created_at") or ""))
    return rows


async def _apply_to_order(order_id: str, amount: float, receipt_id: str,
                          receipt_number: str, method: str, receipt_date: str) -> Dict[str, Any]:
    o = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail=f"Order {order_id} tidak ditemukan")
    gt = order_grand_total(o)
    prev_paid = order_paid(o)
    outstanding = round(gt - prev_paid, 2)
    if amount > outstanding + EPS:
        raise HTTPException(
            status_code=400,
            detail=f"Alokasi Rp {amount:,.0f} melebihi outstanding order {o.get('number')} (Rp {outstanding:,.0f})",
        )
    payments = list(o.get("payments") or [])
    payments.append({
        "id": new_id("pay"),
        "amount": round(float(amount), 2),
        "receipt_id": receipt_id,
        "receipt_number": receipt_number,
        "method": method,
        "date": receipt_date,
        "created_at": receipt_date,
    })
    new_paid = round(prev_paid + amount, 2)
    status = _payment_status(gt, new_paid)
    await db.sales_orders.update_one(
        {"id": order_id},
        {"$set": {"payments": payments, "paid_total": new_paid,
                  "payment_status": status, "updated_at": now_iso()}},
    )
    return {"order_id": order_id, "order_number": o.get("number", order_id),
            "applied": round(float(amount), 2), "outstanding_after": round(gt - new_paid, 2),
            "payment_status": status}


async def create_receipt(payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    customer = await db.customers.find_one({"id": payload.get("customer_id")}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")

    amount = round(float(payload.get("amount", 0) or 0), 2)              # kas baru diterima
    use_deposit_amount = round(float(payload.get("use_deposit_amount", 0) or 0), 2)  # dana dari deposit (P2-5)
    if amount < 0 or use_deposit_amount < 0:
        raise HTTPException(status_code=400, detail="Jumlah pembayaran tidak valid")

    deposit_avail = await get_deposit_balance(customer["id"])
    if use_deposit_amount > deposit_avail + EPS:
        raise HTTPException(
            status_code=400,
            detail=f"Deposit tidak cukup (tersedia Rp {deposit_avail:,.0f})")

    total_funds = round(amount + use_deposit_amount, 2)
    if total_funds <= EPS:
        raise HTTPException(status_code=400, detail="Jumlah pembayaran harus > 0")

    method = (payload.get("method") or "transfer").strip().lower()
    receipt_date = payload.get("receipt_date") or now_iso()
    entity_id = payload.get("entity_id") or customer.get("entity_id") or DEFAULT_ENTITY_ID

    receipt_id = new_id("arc")
    number = await next_doc_number("ar_receipts", "number", "AR-", entity_id=entity_id)

    # Tentukan alokasi (dibatasi total dana = kas baru + deposit dipakai)
    explicit = payload.get("allocations") or []
    allocations: List[Dict[str, Any]] = []
    if explicit:
        total_alloc = round(sum(float(a.get("amount", 0) or 0) for a in explicit), 2)
        if total_alloc > total_funds + EPS:
            raise HTTPException(status_code=400, detail="Total alokasi melebihi dana (kas + deposit)")
        for a in explicit:
            amt = round(float(a.get("amount", 0) or 0), 2)
            if amt <= 0:
                continue
            allocations.append(await _apply_to_order(
                a["order_id"], amt, receipt_id, number, method, receipt_date))
    else:
        remaining = total_funds
        for oo in await list_open_orders(customer["id"]):
            if remaining <= EPS:
                break
            take = min(remaining, oo["outstanding"])
            if take <= EPS:
                continue
            allocations.append(await _apply_to_order(
                oo["order_id"], take, receipt_id, number, method, receipt_date))
            remaining = round(remaining - take, 2)

    applied_total = round(sum(a["applied"] for a in allocations), 2)
    unapplied = round(total_funds - applied_total, 2)
    # Perubahan deposit: deposit terpakai berkurang, sisa tak teralokasi masuk deposit (P2-5).
    deposit_delta = round(unapplied - use_deposit_amount, 2)

    doc = {
        "id": receipt_id,
        "number": number,
        "customer_id": customer["id"],
        "customer_name": customer.get("name", ""),
        "entity_id": entity_id,
        "receipt_date": receipt_date,
        "method": method,
        "amount": amount,
        "used_deposit": use_deposit_amount,
        "total_funds": total_funds,
        "applied_total": applied_total,
        "unapplied_amount": unapplied,
        "deposit_delta": deposit_delta,
        "allocations": allocations,
        "notes": payload.get("notes", ""),
        "status": "posted",
        "created_by": actor.get("id"),
        "created_by_name": actor.get("name", ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.ar_receipts.insert_one(doc)

    # P0-1 — posting kas masuk (hanya untuk kas baru; deposit bukan kas baru).
    cash_txn_id = await _post_cash_in(doc, actor)
    if cash_txn_id:
        doc["cash_txn_id"] = cash_txn_id
        await db.ar_receipts.update_one({"id": receipt_id}, {"$set": {"cash_txn_id": cash_txn_id}})

    # P2-5 — sesuaikan saldo deposit customer.
    await _adjust_deposit(customer["id"], deposit_delta)

    return safe_doc(doc)


async def void_receipt(receipt_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Batalkan penerimaan AR (P2-6): balik payments[], void kas, koreksi deposit."""
    r = await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Receipt tidak ditemukan")
    if r.get("status") == "void":
        raise HTTPException(status_code=409, detail="Receipt sudah di-void")

    # 1) Balik payments[] tiap order yang terdampak → recompute paid_total/status.
    reversed_orders: List[Dict[str, Any]] = []
    for alloc in (r.get("allocations") or []):
        oid = alloc.get("order_id")
        o = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
        if not o:
            continue
        payments = [p for p in (o.get("payments") or []) if p.get("receipt_id") != receipt_id]
        gt = order_grand_total(o)
        paid = round(sum(float(p.get("amount", 0) or 0) for p in payments), 2)
        status = _payment_status(gt, paid)
        await db.sales_orders.update_one(
            {"id": oid},
            {"$set": {"payments": payments, "paid_total": paid,
                      "payment_status": status, "updated_at": now_iso()}},
        )
        reversed_orders.append({"order_id": oid, "outstanding_after": round(gt - paid, 2),
                                "payment_status": status})

    # 2) Void cash_transaction terkait (saldo kas tak lagi menghitungnya).
    await db.cash_transactions.update_many(
        {"ref_type": "ar_receipt", "ref_id": receipt_id, "status": {"$ne": "void"}},
        {"$set": {"status": "void", "updated_at": now_iso()}},
    )

    # 3) Koreksi deposit (balik deposit_delta yang sempat diterapkan).
    delta = round(float(r.get("deposit_delta", 0) or 0), 2)
    if abs(delta) > EPS:
        await _adjust_deposit(r["customer_id"], -delta)

    await db.ar_receipts.update_one(
        {"id": receipt_id},
        {"$set": {"status": "void", "voided_by": actor.get("name", ""),
                  "voided_at": now_iso(), "updated_at": now_iso(),
                  "reversed_orders": reversed_orders}},
    )
    return safe_doc(await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0}))


async def list_receipts(customer_id: Optional[str] = None,
                        scope: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = dict(scope or {})
    if customer_id:
        query["customer_id"] = customer_id
    rows = await db.ar_receipts.find(query, {"_id": 0}).to_list(2000)
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return [safe_doc(r) for r in rows]


async def get_receipt(receipt_id: str) -> Optional[Dict[str, Any]]:
    return safe_doc(await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 0}))
