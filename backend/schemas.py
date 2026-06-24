from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from core_utils import new_id
from schemas_crm import (  # noqa: F401 — re-export CRM schemas (KN_17)
    ContactInfo, PaymentProfile, CustomerReassign, SalesTargetCreate, IncentiveTier,
    SalesIncentiveCreate, CreditOverrideCreate, CreditOverrideDecision, CollectionFollowupCreate,
)
from schemas_finance import (  # noqa: F401 — re-export Finance schemas (EPIC7)
    BankAccountCreate, BankAccountUpdate, ReconcilePayload,
)
from schemas_purchasing import (  # noqa: F401 — re-export Purchasing/Procurement schemas
    POItemCreate, PurchaseOrderCreate, PurchaseOrderAmend,
    BlanketPOItemCreate, BlanketPOCreate, CallOffItemCreate, CallOffCreate, BlanketCloseRequest,
    SupplierCreate, SupplierPriceListCreate, CashTransactionCreate,
    POPaymentCreate, POCloseRequest,
    VendorBillItemInput, VendorBillCreate, VendorBillPaymentCreate, VendorBillDecision,
    LandedCostLineInput, LandedCostCreate, LandedCostPaymentCreate, LandedCostDecision,
    InputTaxInvoiceCreate, InputTaxInvoiceCancel,
    RFQItemInput, RFQCreate, RFQQuoteLine, RFQQuoteSubmit, RFQLineAward, RFQAward, RFQDecision,
    RollDefectInput, RollInspectionInput,
    PurchaseReturnItem, PurchaseReturnCreate, PurchaseReturnDecision,
    POReceiveItem, GRRollLine, GRCompletePayload, QCDecision,
)


class CustomerAddress(BaseModel):
    id: str = Field(default_factory=lambda: new_id("addr"))
    label: str = "Alamat Utama"
    recipient_name: str
    phone: str = ""
    city: str
    address: str
    is_primary: bool = False


class CustomerCreate(BaseModel):
    name: str
    pic_name: str
    phone: str
    email: str = ""
    type: str = "Retail"
    city: str
    address: str
    npwp: str = ""
    credit_limit: float = 0
    sales_pic: str = ""
    entity_id: str = ""
    enforce_single_dye_lot: bool = False  # P0-4 — paksa alokasi 1 dye lot untuk customer ini
    lot_policy: str = ""                  # "" | prefer_single | strict_single | allow_mixed
    created_by: str = "Sales Demo"
    # --- CRM-lite (KN_17) ---
    assigned_sales_id: str = ""           # FK users role=sales — WAJIB (kunci kepemilikan)
    segment: str = "Retail"               # Retail|Wholesale|Distributor|VIP (KLASIFIKASI saja)
    tags: List[str] = Field(default_factory=list)
    contacts: List[ContactInfo] = Field(default_factory=list)
    payment_profile: Optional[PaymentProfile] = None


class BusinessEntityCreate(BaseModel):
    """Entitas legal grup (Multi-Entity — F0-A)."""
    legal_name: str
    short_name: str
    type: str = "PT"            # PT | CV
    npwp: str = ""
    address: str = ""
    city: str = ""
    default_tax_mode: str = "ppn"  # ppn | non_ppn (driver PKP/PPN)
    doc_prefix: str = ""          # mis. KSC, KANDA — untuk nomor dokumen per entitas
    logo_url: str = ""
    currency: str = "IDR"
    parent_entity_id: str = ""    # untuk konsolidasi grup (fase lanjut)
    is_group: bool = False
    coa_template: str = "id_standard"
    fiscal_year_start: str = "01-01"
    incentive_payer: str = "sales_entity"  # Model 1
    numbering_scheme: str = "per_entity_prefix"


class LoginRequest(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    name: str
    email: str
    role: str
    password: str = "demo12345"


class GenericPatch(BaseModel):
    data: Dict[str, Any]


class ProductPayload(BaseModel):
    sku: str
    name: str
    category: str = "Kain"
    variant: str = "Regular"
    color: str = "Natural"
    motif: str = "Polos"
    grade: str = "A"
    supplier: str = "Internal"
    base_unit: str = "meter"
    price: float = 0
    harga_pokok: float = 0
    gramasi: float = 0
    lebar: float = 0                      # Sub-fase 1.13 — lebar kain (meter), utk konversi kg (catch-weight)
    kg_per_meter: float = 0               # Fase 8 — faktor catch-weight eksplisit (kg/m); 0 = turunkan dari gramasi×lebar
    reorder_point: float = 0              # Depth #2b — ambang batas saran beli (0 = nonaktif)
    reorder_qty: float = 0               # Depth #2b — qty saran beli per replenishment (0 = pakai gap)
    image: str = "https://images.unsplash.com/photo-1774679817333-decf0d988dd5?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85"
    description: str = ""                  # F3 — deskripsi produk (tampil di popup detail POS)
    status: str = "active"
    uom_conversions: List[Dict[str, Any]] = []
    template_id: str = ""                 # F1b — tautan ke product_templates (opsional)
    variant_attrs: Dict[str, Any] = {}    # F1b — nilai axis varian (warna/grade/lebar)


class ProductTemplateCreate(BaseModel):
    """F1b — Template katalog (induk) + konfigurasi axis varian."""
    name: str
    category: str = "Kain"
    fabric_type: str = ""
    motif: str = "Polos"
    description: str = ""
    image: str = ""
    base_unit: str = "meter"
    base_price: float = 0.0
    harga_pokok: float = 0.0
    gramasi: float = 0.0
    lebar: float = 0.0
    supplier: str = "Internal"
    sku_prefix: str = ""
    axes: List[Dict[str, Any]] = []       # [{key,label,options:[{code,label,value}]}]


class ProductTemplatePatch(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    fabric_type: Optional[str] = None
    motif: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    base_unit: Optional[str] = None
    base_price: Optional[float] = None
    harga_pokok: Optional[float] = None
    gramasi: Optional[float] = None
    lebar: Optional[float] = None
    supplier: Optional[str] = None
    sku_prefix: Optional[str] = None
    status: Optional[str] = None
    axes: Optional[List[Dict[str, Any]]] = None


class VariantGenerateIn(BaseModel):
    """F1b — generate varian massal (cartesian dari axis)."""
    axes: Optional[List[Dict[str, Any]]] = None   # override axis template (opsional)
    base_price: Optional[float] = None
    sku_prefix: Optional[str] = None


class AssignProductsIn(BaseModel):
    product_ids: List[str] = []


class StockHoldIn(BaseModel):
    """F2 — tahan stok (soft hold / Pending SO): available → hold.
    F2b — `hold_type` membedakan tujuan hold: general | delivery (permintaan
    customer/kredit) | reservation. Surface di papan Hold Aktif."""
    product_id: str
    warehouse_id: str
    owner_entity_id: str
    quantity: float
    reason: str = ""
    hold_type: str = "general"        # general | delivery | reservation (F2b)
    ref_type: str = ""                # mis. 'sales_order' (Pending SO)
    ref_id: str = ""                  # id SO/dokumen terkait (opsional)
    expires_at: str = ""              # iso/tanggal (opsional)


class StockWipIn(BaseModel):
    """F2 — mulai proses (WIP): available → wip."""
    product_id: str
    warehouse_id: str
    owner_entity_id: str
    quantity: float
    note: str = ""


class WarehousePayload(BaseModel):
    code: str
    name: str
    city: str
    bin_code: str = "A1-01"
    bin_capacity: float = 1000
    lat: Optional[float] = None
    lng: Optional[float] = None


class UOMPayload(BaseModel):
    code: str
    name: str
    base_type: str = "length"
    precision: int = 2
    factor_to_base: float = 1.0          # Sub-fase 1.13 — meter per 1 unit (FIXED, length only)


class TemplatePayload(BaseModel):
    document_type: str
    name: str
    header: str = "Kain Nusantara"
    footer: str = "Dokumen dibuat otomatis oleh sistem."
    columns: List[str] = []
    logo_url: str = ""
    paper_size: str = "A4"
    orientation: str = "portrait"
    margin_mm: int = 12
    signature_left: str = "Dibuat Oleh"
    signature_right: str = "Disetujui Oleh"
    section_order: List[str] = ["header", "customer", "items", "allocation", "signature", "footer"]


class PermissionUpdate(BaseModel):
    matrix: Dict[str, Dict[str, List[str]]]


class WMSTaskCreate(BaseModel):
    flow_type: str = "inbound"
    source_type: str = "supplier"
    product_id: str
    quantity: float
    unit: str = "meter"
    warehouse_id: str
    bin_id: str
    batch: str
    lot: str
    roll_id: str


class ScannerScan(BaseModel):
    scan_type: str
    scan_value: str
    actor: str = "Warehouse Demo"


class SalesOrderItemIn(BaseModel):
    product_id: str
    quantity: float
    unit: str
    base_quantity: float = 0             # Sub-fase 1.8/1.13 — qty dlm base unit (forward-compat)
    discount_percent: float = 0          # Fase 1B — diskon per item (0–100%)
    price_approval_id: str = ""          # Sub-fase 1.7 — harga khusus disetujui (override harga)


class SalesTeamMember(BaseModel):
    sales_id: str = ""
    name: str = ""
    role: str = "co"            # "pic" (penanggung jawab) | "co" (co-sales)
    split_pct: float = 0        # 0–100; total seluruh anggota harus = 100 bila sales_team diisi


class SalesOrderCreate(BaseModel):
    customer_id: str
    shipping_address_id: str
    items: List[SalesOrderItemIn]
    sales_name: str = "Ayu Marketing"
    shipment_policy: str = "allow_partial_shipment"
    entity_id: str = ""
    order_discount_percent: float = 0     # Fase 1B — diskon level order (0–100%)
    payment_term_code: str = ""           # Fase 1B — term pembayaran (kode)
    allow_backorder: bool = False         # Sub-fase 1.6 — izinkan reservasi parsial + backorder
    confirm_mixed_lot: bool = False       # Sub-fase 1.7/MixedLot — konfirmasi pemenuhan lintas-lot
    source_special_order_id: str = ""     # EPIC6 — link eksplisit asal Special Order (opsional)
    sales_team: List[SalesTeamMember] = []  # F-4c — join/group sales (PIC + co-sales, split insentif custom)


class AllocationPreviewItem(BaseModel):
    product_id: str
    quantity: float
    unit: str = "meter"


class AllocationPreviewIn(BaseModel):
    """Preview pemenuhan/ATP per baris SEBELUM order dibuat (Sub-fase 1.4, READ-ONLY)."""
    items: List[AllocationPreviewItem]
    entity_id: str = ""          # entitas penjual; kosong → default/owner customer
    customer_id: str = ""        # opsional (konteks kota; tidak mengubah ATP)


class InterCompanyTransferItem(BaseModel):
    product_id: str
    quantity: float
    unit: str = "meter"


class InterCompanyTransferCreate(BaseModel):
    """Sub-fase 1.5 — minta transfer kepemilikan antar-entitas (B→E) dari preview POS.
    EXTEND warehouse_transfers (transfer_kind=inter_entity)."""
    source_entity_id: str                       # B (pemilik stok)
    dest_entity_id: str                         # E (entitas penjual yang butuh)
    items: List[InterCompanyTransferItem]
    linked_order_id: Optional[str] = None       # SO pemicu (opsional)
    transfer_price: Optional[float] = None      # Fase 4 (nullable; tidak ada dampak akuntansi sekarang)
    notes: str = ""
    requested_by: str = ""


class PaymentSimulationCreate(BaseModel):
    amount: float = 0                    # Fase 1B — opsional; default = grand_total order
    method: str = "Transfer Simulasi"
    created_by: str = "Admin Demo"


class DocumentGenerate(BaseModel):
    document_type: str
    source_id: str
    actor: str = "Admin Demo"


class BarcodeGenerate(BaseModel):
    target_type: str
    target_id: str
    label_size: str = "80x50mm"


WAREHOUSE_PRIORITY = {
    "Jakarta": ["Jakarta", "Bandung", "Surabaya"],
    "Bandung": ["Bandung", "Jakarta", "Surabaya"],
    "Surabaya": ["Surabaya", "Bandung", "Jakarta"],
    "Denpasar": ["Surabaya", "Jakarta", "Bandung"],
}


# ─── Transfer Schemas ────────────────────────────────────────────────────────

class TransferItem(BaseModel):
    product_id: str
    qty: float
    unit: str = "meter"
    batch: str = ""
    lot: str = ""
    roll_id: str = ""


class TransferCreate(BaseModel):
    source_warehouse_id: str
    dest_warehouse_id: str
    items: List[TransferItem]
    notes: str = ""
    requested_by: str = "Warehouse User"


class TransferApprove(BaseModel):
    approved_by: str = "Manager"


class TransferReject(BaseModel):
    rejected_by: str = "Manager"
    reason: str = ""


class TransferStatusUpdate(BaseModel):
    status: str  # picking, staging, dispatched, completed
    updated_by: str = "Warehouse User"


# ─── Purchasing / Procurement Schemas — DIPINDAH ke schemas_purchasing.py (re-export di header) ─


# ─── Inventory Roll Schema (Fase 0.5 — Roll-as-SSOT, KN_15) ──────────────────

class RollPayload(BaseModel):
    product_id: str
    warehouse_id: str
    owner_entity_id: str = ""        # default = entitas utama bila kosong
    lot: str
    quantity: float                  # = length_initial = length_remaining awal
    unit: str = "meter"
    grade: str = "A"
    batch: str = ""
    roll_no: str = ""
    bin_id: str = ""
    tracking_mode: str = "barcode"   # rfid | barcode | document | manual
    ownership_type: str = "internal" # internal | supplier_consignment | reseller_consignment


# ─── Configuration Foundation Schemas (Fase 1A — semua configurable) ─────────

class SettingsUpdate(BaseModel):
    scope: str = "global"            # "global" | entity_id
    tax: Optional[Dict[str, Any]] = None
    finance: Optional[Dict[str, Any]] = None
    sales: Optional[Dict[str, Any]] = None
    inventory: Optional[Dict[str, Any]] = None
    allocation: Optional[Dict[str, Any]] = None   # Sub-fase 1.7 — allocation policy
    purchasing: Optional[Dict[str, Any]] = None   # Depth #3 — procurement (deviasi harga, dll)
    commission: Optional[Dict[str, Any]] = None   # EPIC4 — strategi & mekanik insentif


class PaymentTermPayload(BaseModel):
    code: str
    name: str
    type: str = "credit"             # cash | credit | dp | installment
    net_days: int = 0
    dp_percent: float = 0
    installment_count: int = 0
    sort: int = 99
    active: bool = True


class ApprovalRulePayload(BaseModel):
    doc_type: str                    # sales_order | purchase_order | transfer | discount
    entity_id: str = "all"
    min_amount: float = 0
    max_amount: Optional[float] = None
    required_role: str = ""          # "" = tidak butuh approval
    is_percent: bool = False
    sort: int = 99
    active: bool = True



# ─── Price Approval Schemas (Sub-fase 1.7 — Special Price / Approval Harga) ───

class PriceApprovalCreate(BaseModel):
    customer_id: str
    product_id: str
    requested_price: float               # harga khusus yang diajukan (per unit)
    min_quantity: float = 0              # qty minimum agar harga berlaku
    valid_until: str = ""                # "YYYY-MM-DD" atau ISO; "" = tanpa kadaluarsa
    reason: str = ""
    entity_id: str = ""                  # kosong → resolve dari entitas customer
    submit_now: bool = False             # True → langsung status pending (skip draft)


class PriceApprovalDecision(BaseModel):
    decision_notes: str = ""


# ─── Tax Invoice / Faktur Pajak Schemas (Sub-fase 1.9 — Faktur Pajak Jual) ───

class TaxInvoiceCreate(BaseModel):
    kode_transaksi: Optional[str] = "01"   # 01=normal ke ber-NPWP (default)
    faktur_date: Optional[str] = None      # ISO; default = sekarang
    nsfp: Optional[str] = None             # NSFP resmi 16-digit (opsional, diisi menyusul)


class TaxInvoiceNsfpUpdate(BaseModel):
    nsfp: str
    kode_transaksi: Optional[str] = None


class TaxInvoiceReplace(BaseModel):
    reason: Optional[str] = ""
    kode_transaksi: Optional[str] = None
    nsfp: Optional[str] = None


class TaxInvoiceCancel(BaseModel):
    reason: str


# ─── Sales Returns / Retur & Barang Sisa (Sub-fase 1.11) ─────────────────────

class SalesReturnItem(BaseModel):
    product_id:         str
    product_name:       str = ""
    quantity_returned:  float
    unit:               str = "meter"
    reason:             str = ""
    condition:          str = "ok"   # ok | damaged


class SalesReturnCreate(BaseModel):
    order_id:     str
    return_type:  str = "retur"      # retur | bs | penggantian | komplain | garansi (F3 RMA)
    items:        list[SalesReturnItem]
    notes:        str = ""
    entity_id:    str = ""
    submit_now:   bool = False       # True = langsung pending_approval


class SalesReturnDecision(BaseModel):
    notes: str = ""


# ─── Depth #2: Purchase Requisition (PR) + Reorder ───────────────────────────

class PurchaseRequisitionItem(BaseModel):
    product_id: str = ""              # opsional — kosong = item non-katalog (special order)
    description: str = ""            # wajib bila product_id kosong
    quantity: float
    unit: str = "meter"
    est_price: float = 0.0           # estimasi harga satuan (untuk evaluasi approval)
    note: str = ""


class PurchaseRequisitionCreate(BaseModel):
    items: List[PurchaseRequisitionItem]
    warehouse_id: str = ""
    entity_id: str = ""
    reason: str = ""                  # justifikasi kebutuhan
    needed_by_date: str = ""          # ISO/tanggal dibutuhkan
    source: str = "manual"            # manual | reorder | special_order
    source_ref_id: str = ""           # id special_order bila source=special_order
    preferred_supplier_id: str = ""
    notes: str = ""
    submit_now: bool = False          # True = langsung pending_approval (atau approved bila tak butuh approval)
    created_by: str = "Admin"


class PurchaseRequisitionDecision(BaseModel):
    notes: str = ""


class PurchaseRequisitionConvert(BaseModel):
    supplier_id: str = ""             # wajib (atau pakai preferred_supplier_id PR)
    warehouse_id: str = ""            # default = warehouse PR
    expected_delivery_date: str = ""
    notes: str = ""


class SpecialOrderToPR(BaseModel):
    """Jembatan Special Order → PR pengadaan (Depth #2c)."""
    est_price: float = 0.0            # estimasi biaya pengadaan per unit (default target_price)
    warehouse_id: str = ""
    needed_by_date: str = ""
    notes: str = ""
    submit_now: bool = False


class EntityPriceCreate(BaseModel):
    """F1a — Harga jual per-entitas (per base unit) dengan tanggal efektif."""
    product_id: str
    sell_price: float
    entity_id: str = ""               # kosong = entitas aktif
    valid_from: str = ""              # 'YYYY-MM-DD'/iso; kosong = sekarang
    valid_until: str = ""             # kosong = tanpa kadaluarsa
    is_listed: bool = True
    note: str = ""


class EntityPricePatch(BaseModel):
    sell_price: Optional[float] = None
    valid_until: Optional[str] = None
    is_listed: Optional[bool] = None
    note: Optional[str] = None
