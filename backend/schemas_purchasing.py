"""Purchasing / Procurement request schemas (di-reexport oleh `schemas.py`).

Dipisah dari `schemas.py` untuk menjaga batas ukuran file (compliance ≤800 baris).
Mencakup: Purchase Order + Amend, Blanket/Contract PO + Call-off, Supplier +
Supplier Price-List, Cash Transaction, PO Payment/Close, Vendor Bill (3-way),
Landed Cost, Input Tax (Faktur Masukan), RFQ, QC 4-point, Purchase Return,
Goods Receipt (GR/roll). Kontrak field TIDAK berubah (kode menang)."""
from typing import List, Optional
from pydantic import BaseModel


# ─── Purchase Order Schemas ──────────────────────────────────────────────────

class POItemCreate(BaseModel):
    product_id: str
    quantity: float
    unit: str = "meter"
    price: float = 0.0
    discount_percent: float = 0       # P0-1 — diskon per item dari supplier (0–100%)


class PurchaseOrderCreate(BaseModel):
    supplier_id: str = ""             # Fase 3 — FK ke suppliers (opsional; fallback manual)
    supplier_name: str = ""           # snapshot/manual (backward compat bila tanpa supplier_id)
    supplier_contact: str = ""
    warehouse_id: str
    items: List[POItemCreate]
    expected_delivery_date: str = ""
    notes: str = ""
    created_by: str = "Admin"
    entity_id: str = ""
    order_discount_percent: float = 0  # P0-1 — diskon level order (0–100%)
    tax_mode: str = ""                # P0-1 — "" = ikut config | "ppn" (PPN Masukan) | "non_ppn"


class PurchaseOrderAmend(BaseModel):
    """Phase 7.2 — amandemen PO (revisi item/supplier/tanggal/catatan) + re-approval.
    `items` opsional: bila None → item tidak diubah. `reason` WAJIB (jejak audit)."""
    reason: str                       # WAJIB — alasan amandemen (audit)
    items: Optional[List[POItemCreate]] = None
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_contact: Optional[str] = None
    warehouse_id: Optional[str] = None
    expected_delivery_date: Optional[str] = None
    notes: Optional[str] = None
    order_discount_percent: Optional[float] = None
    tax_mode: Optional[str] = None
    amended_by: str = "Admin"


# ─── Blanket / Contract PO Schemas (P2 — call-off) ───────────────────────────

class BlanketPOItemCreate(BaseModel):
    product_id: str
    contract_qty: float                # 1.c — komitmen kuantitas per item
    contract_price: float = 0.0        # harga sepakat (default call-off; 3.b boleh override)
    unit: str = ""                     # default = base_unit produk


class BlanketPOCreate(BaseModel):
    """P2 — kontrak Blanket/Contract PO. Tidak memicu penerimaan; call-off yang menariknya."""
    supplier_id: str = ""
    supplier_name: str = ""
    supplier_contact: str = ""
    warehouse_id: str                  # gudang default untuk call-off
    items: List[BlanketPOItemCreate]
    contract_value_cap: float = 0.0    # 1.c — plafon nilai GROSS (Rp); 0 = Σ qty×harga
    valid_from: str = ""
    valid_until: str = ""              # "" = open (tak kadaluarsa)
    notes: str = ""
    created_by: str = "Admin"
    entity_id: str = ""


class CallOffItemCreate(BaseModel):
    product_id: str
    quantity: float
    unit: str = ""
    price: float = 0.0                 # 0 = pakai harga kontrak; >0 & beda = override (3.b)
    discount_percent: float = 0


class CallOffCreate(BaseModel):
    """P2 — call-off (release) terhadap Blanket PO → menjadi PO anak normal (2.a)."""
    items: List[CallOffItemCreate]
    warehouse_id: str = ""             # default ikut kontrak
    expected_delivery_date: str = ""
    notes: str = ""
    price_override_reason: str = ""    # WAJIB bila ada override harga (3.b)
    order_discount_percent: float = 0
    tax_mode: str = ""
    created_by: str = "Admin"


class BlanketCloseRequest(BaseModel):
    reason: str = ""


# ─── Procurement Schemas (Fase 3 — Supplier Master + Pengelolaan Kas) ─────────

class SupplierCreate(BaseModel):
    name: str
    npwp: str = ""
    pic_name: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    goods_type: str = ""              # jenis barang yang dipasok (benang/kain/bahan printing)
    payment_term_code: str = ""
    lead_time_days: int = 0           # Depth #3 — estimasi lead time default supplier (hari)
    entity_id: str = ""
    notes: str = ""
    created_by: str = "Admin"


# ─── Depth #3: Supplier Price-List (koleksi supplier_price_lists, prefix spl_) ─

class SupplierPriceListCreate(BaseModel):
    product_id: str
    price: float                      # harga beli per `unit`
    unit: str = ""                    # UOM; kosong → base_unit produk (UOM engine 1.13)
    min_qty: float = 0                # MOQ agar harga ini berlaku (0 = tanpa minimum)
    lead_time_days: int = 0           # lead time khusus produk; 0 = pakai default supplier
    valid_from: str = ""              # ISO/tanggal mulai berlaku; "" = sejak sekarang
    valid_until: str = ""             # ISO/tanggal kadaluarsa; "" = tanpa kadaluarsa
    currency: str = "IDR"
    notes: str = ""
    created_by: str = "Admin"


class CashTransactionCreate(BaseModel):
    cash_type: str = "kas_kecil"      # kas_kecil (per entitas) | kas_besar (gabungan)
    direction: str = "out"            # in (masuk) | out (keluar)
    amount: float
    category: str = ""                # pembelian | operasional | gaji | lain
    description: str = ""
    entity_id: str = ""               # untuk kas_kecil; kas_besar dipaksa "all"
    ref_type: str = ""                # purchase_order | manual | ...
    ref_id: str = ""
    txn_date: str = ""                # ISO; default = sekarang
    account_id: str = ""              # EPIC7B — akun kas/bank (opsional)
    created_by: str = "Admin"


# ─── Depth #1: PO Payment + Retur Beli (Purchase Return / Nota Debit) ─────────

class POPaymentCreate(BaseModel):
    amount: float
    cash_type: str = "kas_besar"      # kas_kecil | kas_besar (sumber dana)
    entity_id: str = ""               # untuk kas_kecil
    method: str = "transfer"          # transfer | tunai | giro
    notes: str = ""
    paid_at: str = ""                 # ISO; default sekarang
    created_by: str = "Admin"


class POCloseRequest(BaseModel):
    reason: str = ""                  # alasan tutup kurang (short-close)
    created_by: str = "Admin"


# ─── Fase 5.2 (P0-2): Vendor Bill + 3-Way Matching ───────────────────────────

class VendorBillItemInput(BaseModel):
    product_id: str
    billed_qty: float                 # qty yang ditagih supplier pada bill ini
    price: float = 0.0                # harga per unit (0 = ikut harga PO)
    discount_percent: float = 0       # diskon per item (0–100%)


class VendorBillCreate(BaseModel):
    po_id: str                        # PO referensi (wajib — 3-way match)
    supplier_invoice_no: str = ""     # nomor invoice asli supplier (dedupe)
    bill_date: str = ""               # ISO; default sekarang
    due_date: str = ""                # jatuh tempo (aging AP)
    match_mode: str = "received"      # received (3-way ketat) | ordered (longgar)
    items: List[VendorBillItemInput]
    order_discount_percent: float = 0
    tax_mode: str = ""                # "" ikut PO/config | "ppn" | "non_ppn"
    notes: str = ""
    entity_id: str = ""
    submit_now: bool = False          # True = langsung submit setelah dibuat
    created_by: str = "Admin"


class VendorBillPaymentCreate(BaseModel):
    amount: float
    cash_type: str = "kas_besar"      # kas_kecil | kas_besar (sumber dana)
    entity_id: str = ""
    method: str = "transfer"          # transfer | tunai | giro
    notes: str = ""
    paid_at: str = ""
    created_by: str = "Admin"


class VendorBillDecision(BaseModel):
    notes: str = ""                   # alasan reject/cancel


# ── Fase 5.4 (P0-5): Landed Cost Voucher → alokasi HPP roll ────────────────────
class LandedCostLineInput(BaseModel):
    category: str = "freight"         # freight|duty|insurance|handling|other
    description: str = ""
    amount: float = 0.0               # nominal biaya (Rp)


class LandedCostCreate(BaseModel):
    po_ids: List[str]                 # PO referensi (≥1) sumber roll yang dibebani
    provider_name: str = ""           # penyedia jasa (forwarder/bea cukai/asuransi)
    supplier_invoice_no: str = ""     # nomor invoice penyedia (dedupe)
    basis: str = "value"              # value (proporsional nilai) | quantity (panjang)
    cost_lines: List[LandedCostLineInput]
    voucher_date: str = ""            # ISO; default sekarang
    due_date: str = ""                # jatuh tempo (AP landed cost)
    notes: str = ""
    entity_id: str = ""
    submit_now: bool = False          # True = langsung submit (pending_approval)
    created_by: str = "Admin"


class LandedCostPaymentCreate(BaseModel):
    amount: float
    cash_type: str = "kas_besar"      # kas_kecil | kas_besar (sumber dana)
    entity_id: str = ""
    method: str = "transfer"          # transfer | tunai | giro
    notes: str = ""
    paid_at: str = ""
    created_by: str = "Admin"


class LandedCostDecision(BaseModel):
    notes: str = ""                   # alasan reject/cancel


# ── Fase 5.5 (P0-3): Faktur Pajak Masukan (Input VAT) dari Vendor Bill ─────────
class InputTaxInvoiceCreate(BaseModel):
    vendor_bill_id: str               # Vendor Bill sumber (posted/paid, ber-PPN)
    nsfp: str                         # Nomor Seri Faktur Pajak supplier (16-digit; dedupe)
    faktur_date: str = ""             # tanggal faktur pajak supplier (default = bill_date)
    kode_transaksi: str = "01"        # kode transaksi faktur (default 01)
    notes: str = ""
    created_by: str = "Admin"


class InputTaxInvoiceCancel(BaseModel):
    reason: str                       # alasan pembatalan (wajib)


# ── Fase 6.1 (P1): RFQ / Quotation ────────────────────────────────────────────
class RFQItemInput(BaseModel):
    product_id: str
    quantity: float
    unit: str = "meter"
    note: str = ""
    line_id: str = ""


class RFQCreate(BaseModel):
    source: str = "manual"            # "manual" | "pr"
    pr_id: str = ""                   # bila source=pr
    title: str = ""
    entity_id: str = ""
    warehouse_id: str
    items: List[RFQItemInput] = []    # diabaikan bila source=pr (ditarik dari PR)
    supplier_ids: List[str] = []      # supplier yang diundang
    needed_by_date: str = ""
    due_date: str = ""                # batas akhir penawaran
    notes: str = ""
    created_by: str = "Admin"


class RFQQuoteLine(BaseModel):
    line_id: str
    price: float = 0
    available: bool = True
    note: str = ""


class RFQQuoteSubmit(BaseModel):
    supplier_id: str
    lines: List[RFQQuoteLine] = []
    valid_until: str = ""
    lead_time_days: int = 0
    note: str = ""


class RFQLineAward(BaseModel):
    line_id: str
    supplier_id: str
    price: float = 0


class RFQAward(BaseModel):
    mode: str = "full"                # "full" | "line"
    full_supplier_id: str = ""        # bila mode=full
    line_awards: List[RFQLineAward] = []  # bila mode=line


class RFQDecision(BaseModel):
    reason: str = ""


# ── Fase 6.2 (P1): QC 4-Point Inspection per roll ─────────────────────────────
class RollDefectInput(BaseModel):
    point_value: int                  # 1..4 (severity 4-point)
    count: int = 0                    # jumlah defect pada nilai poin ini
    note: str = ""


class RollInspectionInput(BaseModel):
    defects: List[RollDefectInput] = []
    gsm_actual: Optional[float] = None    # gramasi aktual (dicatat saja)
    width_actual: Optional[float] = None  # lebar aktual (dicatat saja)
    note: str = ""


class PurchaseReturnItem(BaseModel):
    product_id: str
    quantity: float
    unit: str = "meter"
    price: float = 0.0
    reason: str = ""                  # cacat | salah_kirim | kelebihan | lain
    condition: str = "damaged"        # damaged | ok


class PurchaseReturnCreate(BaseModel):
    supplier_id: str = ""
    po_id: str = ""                   # opsional — retur bisa tanpa PO referensi
    warehouse_id: str = ""
    items: List[PurchaseReturnItem]
    reason: str = ""
    notes: str = ""
    entity_id: str = ""
    submit_now: bool = False
    created_by: str = "Admin"


class PurchaseReturnDecision(BaseModel):
    notes: str = ""


class POReceiveItem(BaseModel):
    product_id: str
    actual_qty: float
    batch: str = ""
    lot: str = ""
    dye_lot: str = ""                     # P0-4 — dye lot aktual (warna/celup) per terima
    grade: str = ""                       # P0-4 — grade aktual saat terima ("" = default A)
    roll_id: str = ""
    bin_id: str = ""


class GRRollLine(BaseModel):
    """P0-4 — satu roll fisik saat Goods Receipt (panjang + dye lot + grade per roll).
    Fase 8 (catch-weight): `weight` = berat aktual roll (kg, opsional). Untuk PO yang
    dibeli per kg, isi `weight`; `length` (meter aktual) opsional → diturunkan dari faktor."""
    length: float = 0                     # panjang roll (base/meter; utk PO per-panjang)
    weight: float = 0                     # berat roll (kg) — catch-weight aktual (opsional)
    dye_lot: str = ""
    grade: str = "A"
    defects: List[str] = []


class GRCompletePayload(BaseModel):
    """P0-4 — body opsional saat selesaikan GR. Bila `rolls` diisi → multi-roll
    dengan dye_lot/grade per roll; bila kosong → satu roll pakai dye_lot/grade default."""
    dye_lot: str = ""
    grade: str = ""
    rolls: List[GRRollLine] = []


class QCDecision(BaseModel):
    """Depth #3a + P0-4 — keputusan inspeksi QC untuk 1 inbound task (qty dalam unit task)."""
    accept_qty: float = 0.0
    reject_qty: float = 0.0
    reject_disposition: str = "damaged"   # damaged | return
    accept_grade: str = "A"               # P0-4 — grade aktual untuk qty diterima (A|A+|B|C|BS)
    defects: List[str] = []               # P0-4 — profil cacat (mis. ["belang", "noda"])
    reason: str = ""
