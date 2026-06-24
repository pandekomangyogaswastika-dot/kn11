"""EPIC7-C — General Ledger & Chart of Accounts (akuntansi inti).

Dua koleksi kanonik baru:
- `gl_accounts`    (prefix `gla_`) — Bagan Akun / Chart of Accounts (master).
- `journal_entries` (prefix `je_`) — Jurnal umum (double-entry, balanced).

PRINSIP:
- Setiap jurnal WAJIB seimbang: Σdebit == Σkredit (di-enforce saat create).
- Auto-posting DITURUNKAN dari SSOT yang sudah ada (idempotent by
  source_type+source_id) agar tidak double-count:
    * `sales_orders`     → pengakuan pendapatan (Dr Piutang/Kas, Cr Pendapatan + PPN Keluaran)
    * `cash_transactions`→ mutasi kas (Dr/Cr Kas/Bank vs lawan akun by ref_type)
- Trial Balance & Buku Besar diturunkan dari journal_entries (status != void).

Normal balance: asset & expense = debit; liability, equity, income = credit.
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc, DEFAULT_ENTITY_ID
from services.customer_service import (
    _order_grand_total as order_grand_total,
    order_payment_method,
    NON_AR_METHODS,
    DEAD_STATUSES,
)

EPS = 0.01

# ─── Tipe akun & normal balance ──────────────────────────────────────────────
ACCOUNT_TYPES = ["asset", "liability", "equity", "income", "expense"]
TYPE_LABELS = {
    "asset": "Aset",
    "liability": "Kewajiban",
    "equity": "Ekuitas",
    "income": "Pendapatan",
    "expense": "Beban",
}
DEBIT_TYPES = {"asset", "expense"}  # sisanya credit


def normal_balance(acc_type: str) -> str:
    return "debit" if acc_type in DEBIT_TYPES else "credit"


# ─── Default Chart of Accounts (Indonesia, ringkas namun lengkap) ────────────
# (code, name, type, parent_code, is_postable)
DEFAULT_COA: List = [
    # ASET
    ("1-0000", "ASET", "asset", "", False),
    ("1-1000", "Aset Lancar", "asset", "1-0000", False),
    ("1-1100", "Kas Besar / Bank", "asset", "1-1000", True),
    ("1-1110", "Kas Kecil", "asset", "1-1000", True),
    ("1-1200", "Piutang Usaha", "asset", "1-1000", True),
    ("1-1300", "Persediaan Barang", "asset", "1-1000", True),
    ("1-1400", "Uang Muka & Biaya Dibayar Dimuka", "asset", "1-1000", True),
    ("1-1500", "PPN Masukan", "asset", "1-1000", True),
    ("1-1900", "Aset Lancar Lainnya", "asset", "1-1000", True),
    ("1-9999", "Akun Sementara (Suspense)", "asset", "1-1000", True),
    ("1-2000", "Aset Tetap", "asset", "1-0000", False),
    ("1-2100", "Peralatan & Mesin", "asset", "1-2000", True),
    # KEWAJIBAN
    ("2-0000", "KEWAJIBAN", "liability", "", False),
    ("2-1000", "Kewajiban Lancar", "liability", "2-0000", False),
    ("2-1100", "Hutang Usaha", "liability", "2-1000", True),
    ("2-1200", "PPN Keluaran", "liability", "2-1000", True),
    ("2-1300", "Hutang Pajak Lainnya", "liability", "2-1000", True),
    ("2-1400", "Uang Muka Pelanggan", "liability", "2-1000", True),
    ("2-1500", "Hutang Insentif Penjualan", "liability", "2-1000", True),
    ("2-1900", "Kewajiban Lancar Lainnya", "liability", "2-1000", True),
    # EKUITAS
    ("3-0000", "EKUITAS", "equity", "", False),
    ("3-1000", "Modal Disetor", "equity", "3-0000", True),
    ("3-2000", "Laba Ditahan", "equity", "3-0000", True),
    ("3-3000", "Laba Tahun Berjalan", "equity", "3-0000", True),
    # PENDAPATAN
    ("4-0000", "PENDAPATAN", "income", "", False),
    ("4-1000", "Pendapatan Penjualan", "income", "4-0000", True),
    ("4-9000", "Pendapatan Lain-lain", "income", "4-0000", True),
    # BEBAN (termasuk HPP)
    ("5-0000", "BEBAN POKOK", "expense", "", False),
    ("5-1000", "Harga Pokok Penjualan", "expense", "5-0000", True),
    ("5-9000", "Beban Angkut Pembelian", "expense", "5-0000", True),
    ("6-0000", "BEBAN OPERASIONAL", "expense", "", False),
    ("6-1000", "Beban Gaji", "expense", "6-0000", True),
    ("6-2000", "Beban Sewa", "expense", "6-0000", True),
    ("6-3000", "Beban Utilitas", "expense", "6-0000", True),
    ("6-4000", "Beban Operasional Lainnya", "expense", "6-0000", True),
    ("6-5000", "Beban Insentif Penjualan", "expense", "6-0000", True),
    ("6-9000", "Beban Lain-lain", "expense", "6-0000", True),
]

# Akun kunci untuk auto-posting
ACC_KAS_BESAR = "1-1100"
ACC_KAS_KECIL = "1-1110"
ACC_PIUTANG = "1-1200"
ACC_PERSEDIAAN = "1-1300"     # F3 — Persediaan Barang (Inventory)
ACC_HUTANG = "2-1100"
ACC_PPN_OUT = "2-1200"
ACC_PENDAPATAN = "4-1000"
ACC_PENDAPATAN_LAIN = "4-9000"
ACC_HPP = "5-1000"            # F3 — Harga Pokok Penjualan (COGS)
ACC_LANDED = "5-9000"
ACC_BEBAN_OPS = "6-4000"
ACC_BEBAN_INSENTIF = "6-5000"   # F0-E — Beban Insentif Penjualan
ACC_HUTANG_INSENTIF = "2-1500"  # F0-E — Hutang Insentif Penjualan (akrual)
ACC_SUSPENSE = "1-9999"

# keyword kategori → akun (manual cash entries) untuk semantik akuntansi lebih tepat
CASH_OUT_KEYWORDS = [
    ("gaji", "6-1000"), ("payroll", "6-1000"),
    ("sewa", "6-2000"), ("rent", "6-2000"),
    ("listrik", "6-3000"), ("air", "6-3000"), ("utilitas", "6-3000"),
    ("internet", "6-3000"), ("telepon", "6-3000"),
    ("pembelian", "1-1300"), ("beli", "1-1300"), ("bahan", "1-1300"),
    ("operasional", "6-4000"),
]
CASH_IN_KEYWORDS = [
    ("modal", "3-1000"), ("capital", "3-1000"), ("investasi", "3-1000"), ("setoran modal", "3-1000"),
    ("bunga", "4-9000"), ("jasa giro", "4-9000"),
    ("penjualan tunai", "4-1000"),
]


def _cash_account(txn: Dict[str, Any]) -> str:
    return ACC_KAS_KECIL if txn.get("cash_type") == "kas_kecil" else ACC_KAS_BESAR


# ═════════════════════════════════════════════════════════════════════════════
#  CHART OF ACCOUNTS (master)
# ═════════════════════════════════════════════════════════════════════════════

async def seed_default_coa() -> int:
    """Pastikan bagan akun baku tersedia (idempotent — hanya tambah yg belum ada)."""
    existing = {a["code"] for a in await db.gl_accounts.find({}, {"_id": 0, "code": 1}).to_list(2000)}
    to_add = []
    for code, name, atype, parent, postable in DEFAULT_COA:
        if code in existing:
            continue
        to_add.append({
            "id": new_id("gla"),
            "code": code,
            "name": name,
            "type": atype,
            "normal_balance": normal_balance(atype),
            "parent_code": parent,
            "is_postable": bool(postable),
            "is_active": True,
            "system": True,           # akun baku — tak boleh dihapus
            "currency": "IDR",
            "description": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
    if to_add:
        await db.gl_accounts.insert_many(to_add)
    return len(to_add)


async def list_accounts(active_only: bool = False) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if active_only:
        q["is_active"] = True
    rows = await db.gl_accounts.find(q, {"_id": 0}).to_list(2000)
    rows.sort(key=lambda a: a.get("code", ""))
    return rows


async def get_account(code: str) -> Optional[Dict[str, Any]]:
    return await db.gl_accounts.find_one({"code": code}, {"_id": 0})


async def create_account(payload) -> Dict[str, Any]:
    code = (payload.code or "").strip()
    name = (payload.name or "").strip()
    atype = (payload.type or "").strip()
    if not code or not name:
        raise ValueError("Kode dan nama akun wajib diisi.")
    if atype not in ACCOUNT_TYPES:
        raise ValueError(f"Tipe akun harus salah satu: {', '.join(ACCOUNT_TYPES)}")
    if await db.gl_accounts.find_one({"code": code}, {"_id": 0}):
        raise ValueError(f"Kode akun '{code}' sudah dipakai.")
    if payload.parent_code:
        if not await db.gl_accounts.find_one({"code": payload.parent_code}, {"_id": 0}):
            raise ValueError("Akun induk tidak ditemukan.")
    doc = {
        "id": new_id("gla"),
        "code": code,
        "name": name,
        "type": atype,
        "normal_balance": normal_balance(atype),
        "parent_code": (payload.parent_code or "").strip(),
        "is_postable": bool(payload.is_postable if payload.is_postable is not None else True),
        "is_active": True,
        "system": False,
        "currency": payload.currency or "IDR",
        "description": (payload.description or "").strip(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.gl_accounts.insert_one(doc)
    return safe_doc(doc)


async def update_account(code: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    acc = await db.gl_accounts.find_one({"code": code}, {"_id": 0})
    if not acc:
        return None
    upd: Dict[str, Any] = {}
    for k in ["name", "description", "parent_code"]:
        if patch.get(k) is not None:
            upd[k] = str(patch[k]).strip()
    if patch.get("is_active") is not None:
        upd["is_active"] = bool(patch["is_active"])
    if patch.get("is_postable") is not None and not acc.get("system"):
        upd["is_postable"] = bool(patch["is_postable"])
    upd["updated_at"] = now_iso()
    await db.gl_accounts.update_one({"code": code}, {"$set": upd})
    return await db.gl_accounts.find_one({"code": code}, {"_id": 0})


async def delete_account(code: str) -> None:
    acc = await db.gl_accounts.find_one({"code": code}, {"_id": 0})
    if not acc:
        raise ValueError("Akun tidak ditemukan.")
    if acc.get("system"):
        raise ValueError("Akun baku sistem tidak dapat dihapus (boleh dinonaktifkan).")
    used = await db.journal_entries.count_documents(
        {"lines.account_code": code, "status": {"$ne": "void"}}
    )
    if used:
        raise ValueError(f"Akun dipakai pada {used} jurnal — tidak dapat dihapus.")
    child = await db.gl_accounts.count_documents({"parent_code": code})
    if child:
        raise ValueError("Akun memiliki sub-akun — hapus/abaikan sub-akun dahulu.")
    await db.gl_accounts.delete_one({"code": code})


# ═════════════════════════════════════════════════════════════════════════════
#  JOURNAL ENTRIES (general ledger)
# ═════════════════════════════════════════════════════════════════════════════

def _norm_lines(raw_lines: List[Dict[str, Any]], names: Dict[str, str]) -> List[Dict[str, Any]]:
    out = []
    for ln in raw_lines:
        code = str(ln.get("account_code", "")).strip()
        debit = round(float(ln.get("debit", 0) or 0), 2)
        credit = round(float(ln.get("credit", 0) or 0), 2)
        out.append({
            "account_code": code,
            "account_name": names.get(code, ln.get("account_name", "")),
            "debit": debit,
            "credit": credit,
            "description": str(ln.get("description", "") or "").strip(),
        })
    return out


async def _account_names(codes: List[str]) -> Dict[str, str]:
    rows = await db.gl_accounts.find({"code": {"$in": list(set(codes))}}, {"_id": 0, "code": 1, "name": 1}).to_list(2000)
    return {r["code"]: r["name"] for r in rows}


async def _insert_entry(*, lines: List[Dict[str, Any]], description: str, date: str,
                        source_type: str, source_id: str, entity_id: str,
                        created_by: str, source_label: str = "") -> Dict[str, Any]:
    """Insert jurnal seimbang. Caller MEMASTIKAN balance (helper auto-post)."""
    names = await _account_names([l["account_code"] for l in lines])
    norm = _norm_lines(lines, names)
    total_debit = round(sum(l["debit"] for l in norm), 2)
    total_credit = round(sum(l["credit"] for l in norm), 2)
    number = await next_doc_number("journal_entries", "number", "JE-", entity_id=entity_id)
    doc = {
        "id": new_id("je"),
        "number": number,
        "date": date or now_iso(),
        "description": description,
        "source": source_type,
        "source_type": source_type,
        "source_id": source_id,
        "source_label": source_label,
        "lines": norm,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "status": "posted",
        "entity_id": entity_id or DEFAULT_ENTITY_ID,
        "created_by": created_by or "system",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.journal_entries.insert_one(doc)
    return safe_doc(doc)


async def create_manual_entry(payload, actor: Dict[str, Any],
                              entity_id: Optional[str] = None) -> Dict[str, Any]:
    raw = [ln.model_dump() if hasattr(ln, "model_dump") else dict(ln) for ln in (payload.lines or [])]
    if len(raw) < 2:
        raise ValueError("Jurnal minimal 2 baris (debit & kredit).")
    codes = [str(l.get("account_code", "")).strip() for l in raw]
    if any(not c for c in codes):
        raise ValueError("Setiap baris harus memilih akun.")
    accounts = {a["code"]: a for a in await db.gl_accounts.find(
        {"code": {"$in": codes}}, {"_id": 0}).to_list(2000)}
    for c in codes:
        if c not in accounts:
            raise ValueError(f"Akun '{c}' tidak ditemukan.")
        if not accounts[c].get("is_postable", True):
            raise ValueError(f"Akun '{c}' adalah header — pilih akun detail (postable).")
        if accounts[c].get("is_active") is False:
            raise ValueError(f"Akun '{c}' nonaktif.")
    names = {c: accounts[c]["name"] for c in codes}
    lines = _norm_lines(raw, names)
    for l in lines:
        if l["debit"] < 0 or l["credit"] < 0:
            raise ValueError("Nilai debit/kredit tidak boleh negatif.")
        if l["debit"] > EPS and l["credit"] > EPS:
            raise ValueError("Satu baris hanya boleh debit ATAU kredit.")
        if l["debit"] <= EPS and l["credit"] <= EPS:
            raise ValueError("Setiap baris harus punya nilai debit atau kredit.")
    total_debit = round(sum(l["debit"] for l in lines), 2)
    total_credit = round(sum(l["credit"] for l in lines), 2)
    if abs(total_debit - total_credit) > EPS:
        raise ValueError(f"Jurnal tidak seimbang: debit {total_debit:,.2f} ≠ kredit {total_credit:,.2f}.")
    eid = payload.entity_id or entity_id or DEFAULT_ENTITY_ID
    number = await next_doc_number("journal_entries", "number", "JE-", entity_id=eid)
    doc = {
        "id": new_id("je"),
        "number": number,
        "date": payload.date or now_iso(),
        "description": (payload.description or "").strip() or "Jurnal manual",
        "source": "manual",
        "source_type": "manual",
        "source_id": "",
        "source_label": "Manual",
        "lines": lines,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "status": "posted",
        "entity_id": eid,
        "created_by": actor.get("name", "system"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.journal_entries.insert_one(doc)
    return safe_doc(doc)


async def list_entries(source: Optional[str] = None, account_code: Optional[str] = None,
                       status: Optional[str] = None, limit: int = 500,
                       scope: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = dict(scope or {})
    if source:
        q["source_type"] = source
    if account_code:
        q["lines.account_code"] = account_code
    if status:
        q["status"] = status
    rows = await db.journal_entries.find(q, {"_id": 0}).sort("number", -1).to_list(limit)
    return rows


async def get_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    return await db.journal_entries.find_one(
        {"$or": [{"id": entry_id}, {"number": entry_id}]}, {"_id": 0})


async def void_entry(entry_id: str, actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    je = await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})
    if not je:
        return None
    if je.get("status") == "void":
        raise ValueError("Jurnal sudah di-void.")
    if je.get("source_type") != "manual":
        raise ValueError("Hanya jurnal manual yang dapat di-void langsung (jurnal otomatis mengikuti dokumen sumber).")
    await db.journal_entries.update_one(
        {"id": entry_id},
        {"$set": {"status": "void", "voided_by": actor.get("name", "system"),
                  "voided_at": now_iso(), "updated_at": now_iso()}},
    )
    return await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})


# ═════════════════════════════════════════════════════════════════════════════
#  AUTO-POSTING (idempotent, derived from SSOT)
# ═════════════════════════════════════════════════════════════════════════════

async def _already_posted(source_type: str, source_id: str) -> bool:
    return bool(await db.journal_entries.find_one(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}},
        {"_id": 0, "id": 1}))


def _balanced_pair(debit_acc: str, credit_acc: str, amount: float, desc: str) -> List[Dict[str, Any]]:
    return [
        {"account_code": debit_acc, "debit": amount, "credit": 0.0, "description": desc},
        {"account_code": credit_acc, "debit": 0.0, "credit": amount, "description": desc},
    ]


async def post_sales_order(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pengakuan pendapatan: Dr Piutang/Kas = grand_total; Cr Pendapatan = DPP; Cr PPN Keluaran."""
    if order.get("status") in DEAD_STATUSES:
        return None
    sid = order.get("id")
    if not sid or await _already_posted("sales_order", sid):
        return None
    grand = round(order_grand_total(order), 2)
    if grand <= EPS:
        return None
    dpp = round(float(order.get("dpp", order.get("net_subtotal", order.get("total_amount", 0))) or 0), 2)
    ppn = round(float(order.get("ppn_amount", order.get("tax", 0)) or 0), 2)
    is_cash = order_payment_method(order) in NON_AR_METHODS
    debit_acc = ACC_KAS_BESAR if is_cash else ACC_PIUTANG
    num = order.get("number", sid)
    lines = [{"account_code": debit_acc, "debit": grand, "credit": 0.0,
              "description": f"{'Tunai' if is_cash else 'Piutang'} {num}"}]
    # Cr pendapatan + PPN; sisa pembulatan → suspense agar selalu seimbang
    rev = dpp if dpp > EPS else round(grand - ppn, 2)
    lines.append({"account_code": ACC_PENDAPATAN, "debit": 0.0, "credit": rev,
                  "description": f"Penjualan {num}"})
    if ppn > EPS:
        lines.append({"account_code": ACC_PPN_OUT, "debit": 0.0, "credit": ppn,
                      "description": f"PPN Keluaran {num}"})
    diff = round(grand - (rev + (ppn if ppn > EPS else 0)), 2)
    if abs(diff) > EPS:
        if diff > 0:
            lines.append({"account_code": ACC_PENDAPATAN_LAIN, "debit": 0.0, "credit": diff, "description": "Pembulatan"})
        else:
            lines.append({"account_code": ACC_PENDAPATAN_LAIN, "debit": -diff, "credit": 0.0, "description": "Pembulatan"})
    return await _insert_entry(
        lines=lines, description=f"Pengakuan penjualan {num}", date=order.get("created_at") or now_iso(),
        source_type="sales_order", source_id=sid, entity_id=order.get("entity_id", ""),
        created_by="system", source_label=num)


async def _avg_unit_cost(product_id: str, entity_id: str = "") -> float:
    """F3 — rata-rata unit_cost roll produk (basis HPP). Tertimbang length_initial,
    fallback rata-rata sederhana, fallback 0 bila tak ada data cost."""
    q: Dict[str, Any] = {"product_id": product_id}
    if entity_id:
        q["owner_entity_id"] = entity_id
    rolls = await db.inventory_rolls.find(
        q, {"_id": 0, "unit_cost": 1, "base_unit_cost": 1, "length_initial": 1}).to_list(5000)
    if not rolls and entity_id:
        rolls = await db.inventory_rolls.find(
            {"product_id": product_id}, {"_id": 0, "unit_cost": 1, "base_unit_cost": 1, "length_initial": 1}).to_list(5000)
    tot_cost, tot_w, simple = 0.0, 0.0, []
    for r in rolls:
        c = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
        if c <= 0:
            continue
        w = float(r.get("length_initial") or 0)
        simple.append(c)
        if w > 0:
            tot_cost += c * w
            tot_w += w
    if tot_w > 0:
        return round(tot_cost / tot_w, 2)
    return round(sum(simple) / len(simple), 2) if simple else 0.0


async def post_order_cogs(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """F3 — HPP penjualan: Dr HPP / Cr Persediaan = Σ(qty × avg_unit_cost).
    Idempotent (source_type='sales_cogs'). Skip bila cost tak diketahui (0)."""
    if order.get("status") in DEAD_STATUSES:
        return None
    sid = order.get("id")
    if not sid or await _already_posted("sales_cogs", sid):
        return None
    eid = order.get("entity_id", "")
    total_cogs = 0.0
    for it in order.get("items", []):
        qty = float(it.get("base_quantity", it.get("quantity", 0)) or 0)
        if qty <= 0:
            continue
        total_cogs += qty * await _avg_unit_cost(it.get("product_id", ""), eid)
    total_cogs = round(total_cogs, 2)
    if total_cogs <= EPS:
        return None
    num = order.get("number", sid)
    lines = _balanced_pair(ACC_HPP, ACC_PERSEDIAAN, total_cogs, f"HPP penjualan {num}")
    return await _insert_entry(
        lines=lines, description=f"HPP penjualan {num}", date=order.get("created_at") or now_iso(),
        source_type="sales_cogs", source_id=sid, entity_id=eid,
        created_by="system", source_label=num)


async def post_sales_return(ret: Dict[str, Any], *, return_net: float, return_ppn: float,
                            return_cogs: float, is_cash: bool = False,
                            credit_note_number: str = "") -> Optional[Dict[str, Any]]:
    """F3 — Credit Note (retur penjualan) → GL reversal. Idempotent (source_type='sales_return').
      Dr Pendapatan (net) + Dr PPN Keluaran (ppn) / Cr Piutang|Kas (gross)
      Dr Persediaan (cogs)  / Cr HPP (cogs)   — barang balik ke stok
    """
    rid = ret.get("id")
    if not rid or await _already_posted("sales_return", rid):
        return None
    return_net = round(float(return_net or 0), 2)
    return_ppn = round(float(return_ppn or 0), 2)
    return_cogs = round(float(return_cogs or 0), 2)
    gross = round(return_net + return_ppn, 2)
    if gross <= EPS and return_cogs <= EPS:
        return None
    label = credit_note_number or ret.get("number", rid)
    lines: List[Dict[str, Any]] = []
    if gross > EPS:
        lines.append({"account_code": ACC_PENDAPATAN, "debit": return_net, "credit": 0.0,
                      "description": f"Retur penjualan {label}"})
        if return_ppn > EPS:
            lines.append({"account_code": ACC_PPN_OUT, "debit": return_ppn, "credit": 0.0,
                          "description": f"Reversal PPN Keluaran {label}"})
        credit_acc = ACC_KAS_BESAR if is_cash else ACC_PIUTANG
        lines.append({"account_code": credit_acc, "debit": 0.0, "credit": gross,
                      "description": f"{'Refund tunai' if is_cash else 'Pengurang piutang'} {label}"})
    if return_cogs > EPS:
        lines += _balanced_pair(ACC_PERSEDIAAN, ACC_HPP, return_cogs, f"Barang retur masuk stok {label}")
    return await _insert_entry(
        lines=lines, description=f"Credit Note / Retur penjualan {label}",
        date=ret.get("approved_at") or now_iso(),
        source_type="sales_return", source_id=rid, entity_id=ret.get("entity_id", ""),
        created_by="system", source_label=label)


async def post_cash_transaction(txn: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Mutasi kas: Dr/Cr Kas/Bank vs lawan akun berdasar ref_type / kategori."""
    if txn.get("status") == "void":
        return None
    tid = txn.get("id")
    if not tid or await _already_posted("cash_transaction", tid):
        return None
    amount = round(float(txn.get("amount", 0) or 0), 2)
    if amount <= EPS:
        return None
    cash_acc = _cash_account(txn)
    ref_type = txn.get("ref_type") or ""
    direction = txn.get("direction")
    desc = txn.get("description") or txn.get("category") or "Transaksi kas"
    number = txn.get("number", tid)

    if direction == "in":
        if ref_type == "ar_receipt":
            contra = ACC_PIUTANG
        else:
            contra = ACC_SUSPENSE  # default netral (tidak menggelembungkan pendapatan)
            cat = (txn.get("category") or "").lower()
            for kw, acc in CASH_IN_KEYWORDS:
                if kw in cat:
                    contra = acc
                    break
        lines = _balanced_pair(cash_acc, contra, amount, f"{number} · {desc}")
    else:  # out
        if ref_type == "vendor_bill":
            contra = ACC_HUTANG
        elif ref_type == "landed_cost":
            contra = ACC_LANDED
        else:
            contra = ACC_BEBAN_OPS
            cat = (txn.get("category") or "").lower()
            for kw, acc in CASH_OUT_KEYWORDS:
                if kw in cat:
                    contra = acc
                    break
        lines = _balanced_pair(contra, cash_acc, amount, f"{number} · {desc}")

    return await _insert_entry(
        lines=lines, description=f"Kas {direction} · {desc}", date=txn.get("txn_date") or now_iso(),
        source_type="cash_transaction", source_id=tid, entity_id=txn.get("entity_id", ""),
        created_by=txn.get("created_by", "system"), source_label=number)


async def backfill_journals() -> Dict[str, int]:
    """Posting otomatis (idempotent) seluruh SSOT yang belum berjurnal.

    Urutan: sales_orders (pendapatan) lalu cash_transactions (mutasi kas).
    Aman diulang — yang sudah posted dilewati.
    """
    await seed_default_coa()
    posted_so = posted_cash = 0
    orders = await db.sales_orders.find({}, {"_id": 0}).to_list(20000)
    for o in orders:
        if await post_sales_order(o):
            posted_so += 1
    txns = await db.cash_transactions.find(
        {"status": {"$ne": "void"}}, {"_id": 0}).sort("txn_date", 1).to_list(20000)
    for t in txns:
        if await post_cash_transaction(t):
            posted_cash += 1
    return {"sales_orders": posted_so, "cash_transactions": posted_cash,
            "total": posted_so + posted_cash}


async def post_incentive_accrual(entity_id: str, period: str,
                                 created_by: str = "system") -> Optional[Dict[str, Any]]:
    """F0-E — Akrual beban insentif penjualan per (entitas, periode).

    Model 1 (silo selling): biaya insentif ditanggung entitas SO (= entitas sales).
    Total = Σ total_incentive seluruh sales (komisi dihitung khusus entitas itu, jadi
    sales entitas lain otomatis 0). Idempotent via source_type='incentive_accrual',
    source_id=f'{entity_id}:{period}'.
      Dr Beban Insentif Penjualan / Cr Hutang Insentif Penjualan.
    """
    if not entity_id or entity_id == "all" or not period:
        raise ValueError("Akrual insentif membutuhkan entitas spesifik & periode (mis. 2026-06).")
    src_id = f"{entity_id}:{period}"
    if await _already_posted("incentive_accrual", src_id):
        return None
    await seed_default_coa()
    from services import sales_force_service as sf
    sales_users = await db.users.find(
        {"role": "sales", "status": "active"}, {"_id": 0, "id": 1}).to_list(500)
    total = 0.0
    for u in sales_users:
        c = await sf.compute_commission(u["id"], period, entity_id=entity_id)
        total += float(c.get("total_incentive", 0) or 0)
    total = round(total, 2)
    if total <= EPS:
        return None
    lines = _balanced_pair(ACC_BEBAN_INSENTIF, ACC_HUTANG_INSENTIF, total,
                           f"Akrual insentif penjualan {period}")
    return await _insert_entry(
        lines=lines, description=f"Akrual insentif penjualan {period}",
        date=now_iso(), source_type="incentive_accrual", source_id=src_id,
        entity_id=entity_id, created_by=created_by, source_label=f"INS-{period}")


async def incentive_accrual_status(entity_id: str, period: str) -> Dict[str, Any]:
    """Status akrual insentif (entitas, periode): sudah diposting? + ringkasan jurnal."""
    src_id = f"{entity_id}:{period}"
    je = await db.journal_entries.find_one(
        {"source_type": "incentive_accrual", "source_id": src_id, "status": {"$ne": "void"}},
        {"_id": 0})
    return {
        "entity_id": entity_id,
        "period": period,
        "posted": bool(je),
        "amount": round(float(je.get("total_debit", 0)), 2) if je else 0.0,
        "journal_number": je.get("number") if je else None,
        "journal_id": je.get("id") if je else None,
        "posted_at": je.get("created_at") if je else None,
    }


# ═════════════════════════════════════════════════════════════════════════════
#  REPORTS — Trial Balance & Account Ledger
# ═════════════════════════════════════════════════════════════════════════════

async def trial_balance(as_of: Optional[str] = None,
                        scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Neraca saldo: saldo debit/kredit per akun (akun postable yg punya mutasi).

    `scope` = fragmen filter entitas untuk journal_entries (buku terpisah per PT).
    """
    accounts = await db.gl_accounts.find({}, {"_id": 0}).to_list(2000)
    amap = {a["code"]: a for a in accounts}
    q: Dict[str, Any] = {"status": {"$ne": "void"}, **(scope or {})}
    if as_of:
        q["date"] = {"$lte": as_of}
    entries = await db.journal_entries.find(q, {"_id": 0, "lines": 1}).to_list(50000)

    agg: Dict[str, Dict[str, float]] = {}
    for je in entries:
        for ln in je.get("lines", []):
            code = ln.get("account_code")
            if not code:
                continue
            a = agg.setdefault(code, {"debit": 0.0, "credit": 0.0})
            a["debit"] += float(ln.get("debit", 0) or 0)
            a["credit"] += float(ln.get("credit", 0) or 0)

    rows: List[Dict[str, Any]] = []
    tot_debit = tot_credit = 0.0
    for code, v in agg.items():
        acc = amap.get(code, {})
        net = round(v["debit"] - v["credit"], 2)
        nb = acc.get("normal_balance", normal_balance(acc.get("type", "asset")))
        debit_bal = net if net > 0 else 0.0
        credit_bal = -net if net < 0 else 0.0
        rows.append({
            "code": code,
            "name": acc.get("name", code),
            "type": acc.get("type", ""),
            "type_label": TYPE_LABELS.get(acc.get("type", ""), ""),
            "normal_balance": nb,
            "debit": round(v["debit"], 2),
            "credit": round(v["credit"], 2),
            "debit_balance": round(debit_bal, 2),
            "credit_balance": round(credit_bal, 2),
        })
        tot_debit += debit_bal
        tot_credit += credit_bal
    rows.sort(key=lambda r: r["code"])
    return {
        "as_of": as_of or now_iso(),
        "rows": rows,
        "total_debit": round(tot_debit, 2),
        "total_credit": round(tot_credit, 2),
        "balanced": abs(tot_debit - tot_credit) < 0.5,
        "account_count": len(rows),
    }


async def account_ledger(code: str, as_of: Optional[str] = None,
                         scope: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Buku besar 1 akun: baris jurnal yg menyentuh akun + running balance (per entitas via `scope`)."""
    acc = await db.gl_accounts.find_one({"code": code}, {"_id": 0})
    if not acc:
        return None
    q: Dict[str, Any] = {"status": {"$ne": "void"}, "lines.account_code": code, **(scope or {})}
    if as_of:
        q["date"] = {"$lte": as_of}
    entries = await db.journal_entries.find(q, {"_id": 0}).to_list(50000)
    nb = acc.get("normal_balance", normal_balance(acc.get("type", "asset")))
    sign = 1 if nb == "debit" else -1

    flat: List[Dict[str, Any]] = []
    for je in entries:
        for ln in je.get("lines", []):
            if ln.get("account_code") != code:
                continue
            flat.append({
                "entry_id": je.get("id"),
                "number": je.get("number"),
                "date": je.get("date"),
                "description": ln.get("description") or je.get("description"),
                "source_type": je.get("source_type"),
                "source_label": je.get("source_label", ""),
                "debit": round(float(ln.get("debit", 0) or 0), 2),
                "credit": round(float(ln.get("credit", 0) or 0), 2),
            })
    flat.sort(key=lambda r: (r.get("date") or "", r.get("number") or ""))
    running = 0.0
    total_debit = total_credit = 0.0
    for r in flat:
        running += sign * (r["debit"] - r["credit"])
        r["running_balance"] = round(running, 2)
        total_debit += r["debit"]
        total_credit += r["credit"]
    flat.reverse()  # terbaru dulu
    return {
        "account": {"code": acc["code"], "name": acc["name"], "type": acc.get("type"),
                    "type_label": TYPE_LABELS.get(acc.get("type", ""), ""),
                    "normal_balance": nb},
        "lines": flat,
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "balance": round(running, 2),
        "count": len(flat),
    }


async def gl_summary(scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """KPI ringkas untuk header GL (per entitas via `scope`)."""
    tb = await trial_balance(scope=scope)
    posted = await db.journal_entries.count_documents({"status": {"$ne": "void"}, **(scope or {})})
    accounts = await db.gl_accounts.count_documents({})
    return {
        "journal_count": posted,
        "account_count": accounts,
        "total_debit": tb["total_debit"],
        "total_credit": tb["total_credit"],
        "balanced": tb["balanced"],
    }


# ═════════════════════════════════════════════════════════════════════════════
#  KONSOLIDASI GRUP vs PER-PT (Multi-Entity F0-E enhancement)
#  Memanfaatkan buku terpisah per entitas (scope journal_entries.entity_id) untuk
#  menyajikan ringkasan P&L + neraca tiap PT, lalu menjumlahkannya jadi gabungan.
# ═════════════════════════════════════════════════════════════════════════════

_CONS_SUM_FIELDS = [
    "revenue", "cogs", "opex", "expense", "gross_profit", "net_income",
    "assets", "liabilities", "equity", "retained_earnings", "equity_total",
    "cash", "ar", "ap", "inventory", "ppn_out", "journal_count",
]


async def _entity_financials(entity_id: str, as_of: Optional[str] = None) -> Dict[str, Any]:
    """Ringkasan keuangan satu buku (entity_id) dari trial balance terisolasi."""
    scope = {"entity_id": entity_id}
    tb = await trial_balance(as_of=as_of, scope=scope)
    revenue = cogs = opex = 0.0
    assets = liabilities = equity = 0.0
    cash = ar = ap = ppn_out = inventory = 0.0
    for r in tb["rows"]:
        t = r.get("type")
        code = r.get("code", "")
        debit_net = round(r["debit_balance"] - r["credit_balance"], 2)
        credit_net = round(r["credit_balance"] - r["debit_balance"], 2)
        if t == "income":
            revenue += credit_net
        elif t == "expense":
            if code.startswith("5"):
                cogs += debit_net
            else:
                opex += debit_net
        elif t == "asset":
            assets += debit_net
        elif t == "liability":
            liabilities += credit_net
        elif t == "equity":
            equity += credit_net
        if code in (ACC_KAS_BESAR, ACC_KAS_KECIL):
            cash += debit_net
        elif code == ACC_PIUTANG:
            ar += debit_net
        elif code == "1-1300":
            inventory += debit_net
        elif code == ACC_HUTANG:
            ap += credit_net
        elif code == ACC_PPN_OUT:
            ppn_out += credit_net
    revenue = round(revenue, 2)
    cogs = round(cogs, 2)
    opex = round(opex, 2)
    expense = round(cogs + opex, 2)
    gross_profit = round(revenue - cogs, 2)
    net_income = round(revenue - expense, 2)
    equity = round(equity, 2)
    journal_count = await db.journal_entries.count_documents(
        {"status": {"$ne": "void"}, "entity_id": entity_id})
    return {
        "revenue": revenue, "cogs": cogs, "opex": opex, "expense": expense,
        "gross_profit": gross_profit, "net_income": net_income,
        "net_margin": round(net_income / revenue * 100, 1) if revenue > 0 else 0.0,
        "assets": round(assets, 2), "liabilities": round(liabilities, 2),
        "equity": equity, "retained_earnings": net_income,
        "equity_total": round(equity + net_income, 2),
        "cash": round(cash, 2), "ar": round(ar, 2), "ap": round(ap, 2),
        "inventory": round(inventory, 2), "ppn_out": round(ppn_out, 2),
        "journal_count": journal_count, "balanced": tb["balanced"],
    }


async def consolidation(entity_ids: List[str], as_of: Optional[str] = None) -> Dict[str, Any]:
    """Konsolidasi grup: ringkasan keuangan per-PT + total gabungan.

    `entity_ids` = entitas dalam cakupan baca user (admin/manager = semua aktif).
    Jurnal ber-entity_id 'all' (kas/bank grup) ditampilkan sebagai baris 'Grup /
    Kas Bersama' agar penjumlahan baris == total konsolidasi (faithful)."""
    ents = {e["id"]: e for e in await db.business_entities.find(
        {"id": {"$in": list(entity_ids)}}, {"_id": 0}).to_list(200)}
    rows: List[Dict[str, Any]] = []
    for eid in entity_ids:
        e = ents.get(eid, {})
        if e.get("is_group"):
            continue
        fin = await _entity_financials(eid, as_of)
        raw_pkp = e.get("is_pkp")
        is_pkp = (e.get("default_tax_mode") in ("ppn", "pkp")) if raw_pkp is None else bool(raw_pkp)
        rows.append({
            "entity_id": eid,
            "entity_name": e.get("legal_name") or e.get("short_name") or eid,
            "short_name": e.get("short_name") or e.get("doc_prefix") or eid,
            "currency": e.get("currency", "IDR"),
            "is_pkp": is_pkp,
            "is_shared": False,
            **fin,
        })
    rows.sort(key=lambda r: r["revenue"], reverse=True)
    # Bucket grup (kas/bank bersama, entity_id == 'all')
    shared = await _entity_financials("all", as_of)
    if shared["journal_count"] > 0:
        rows.append({
            "entity_id": "all", "entity_name": "Grup / Kas Bersama", "short_name": "Grup",
            "currency": "IDR", "is_pkp": None, "is_shared": True, **shared,
        })
    cons = {f: round(sum(float(r.get(f, 0) or 0) for r in rows), 2) for f in _CONS_SUM_FIELDS}
    cons["journal_count"] = int(cons["journal_count"])
    cons["net_margin"] = round(cons["net_income"] / cons["revenue"] * 100, 1) if cons["revenue"] > 0 else 0.0
    cons["balanced"] = all(r.get("balanced", True) for r in rows)
    cons["entity_count"] = len([r for r in rows if not r.get("is_shared")])
    return {"as_of": as_of or now_iso(), "entities": rows, "consolidated": cons}
