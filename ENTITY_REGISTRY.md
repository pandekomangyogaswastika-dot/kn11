# ENTITY REGISTRY — SSOT Map
## Kain Nusantara Platform

**WAJIB DIBACA SEBELUM MEMBUAT COLLECTION, SCHEMA, ATAU ENDPOINT BARU.**

File ini adalah satu-satunya sumber kebenaran untuk semua entitas bisnis.
Sebelum membuat apapun yang baru, tanya: **"Apakah ini sudah ada di sini?"**

**Update wajib setiap kali ada:**
- Collection baru ditambahkan
- Schema baru dibuat
- Endpoint baru untuk entitas yang sudah ada
- Component baru untuk entitas yang sudah ada

---

## 📋 QUICK LOOKUP TABLE

| Entitas | Collection | Router | Schema | Frontend Component |
|---|---|---|---|---|
| User | `users` | `routers/auth.py`, `routers/users.py` | `UserCreate` | `AdminView` (tab Users) |
| Session (Auth) | `sessions` | `routers/auth.py` | — | `LoginScreen` |
| Product | `products` | `routers/products.py` | `ProductPayload` | `ProductCard`, `AdminView` (tab Product) |
| Customer | `customers` | `routers/customers.py` | `CustomerCreate` | `CustomerPanel`, `AdminView` (tab Customer) |
| Warehouse | `warehouses` | `routers/warehouses.py` | `WarehousePayload` | `AdminView` (tab Warehouse) |
| UOM | `uoms` | `routers/uoms.py` | `UOMPayload` | `AdminView` (tab UOM) |
| Sales Order | `sales_orders` | `routers/sales_orders.py` | `SalesOrderCreate` | `SalesPortal`, `OrdersView`, `CartPanel` |
| Invoice | `invoices` | `routers/invoices.py` | `PaymentSimulationCreate` | `DocumentsView` |
| Inventory Balance | `inventory_balances` | `routers/inventory.py` | — | `InventoryStockView` |
| Inventory Roll *(IMPLEMENTED Fase 0.5)* | `inventory_rolls` | `routers/inventory.py`, `services/roll_service.py` | `RollPayload` | `InventoryStockView`, `SalesPortal` |
| Inventory Movement | `inventory_movements` | `routers/inventory.py` | — | `InventoryStockView` (tab Ledger) |
| WMS Task | `wms_tasks` | `routers/wms.py` | `WMSTaskCreate` | `ScannerTaskPanel` |
| Inbound Task | `wms_tasks` *(flow_type=inbound)* | `routers/inbound_receiving.py` | — | `InboundScanInterface` |
| Outbound Task | `wms_tasks` *(flow_type=outbound)* | `routers/outbound_picking.py` | — | `OutboundScanInterface` |
| Transfer | `warehouse_transfers` | `routers/transfers.py` | `TransferCreate` | `TransferManagement` |
| Cycle Count | `cycle_count_sessions` | `routers/cycle_count.py` | — | `CycleCount` |
| Purchase Order | `purchase_orders` | `routers/purchase_orders.py` | `PurchaseOrderCreate` | `PurchaseOrderManagement` |
| Document Template | `document_templates` | `routers/documents.py` | `TemplatePayload` | `DocumentsView`, `AdminView` (tab Templates) |
| Generated Document | `generated_documents` | `routers/documents.py` | `DocumentGenerate` | `DocumentsView` |
| Permission Settings | `permission_settings` | `routers/admin.py` | `PermissionUpdate` | `AdminView` (tab Permissions) |
| Audit Log | `audit_logs` | `routers/audit.py` | — | `AdminView` (tab Audit) |
| Onboarding | `user_onboarding` | `routers/onboarding.py` | — | `OnboardingPanel` |

---

## 🗂️ DETAIL ENTITAS

### users
```
Collection:  users
Routers:     routers/auth.py (login, me, logout)
             routers/users.py (CRUD)
Schema:      schemas.py → UserCreate, UserResponse
Component:   AdminView.jsx (tab Users), LoginScreen (CoreWidgets.jsx)
Key Fields:
  id          string   prefix "user_"
  name        string
  email       string   UNIQUE
  role        enum     admin | sales | manager | warehouse
  password_hash string  SHA256 hash (kain-nusantara::password)
  status      enum     active | inactive
  created_at  string   ISO 8601 UTC

⚠️ JANGAN BUAT: staff, karyawan, operator, employee (untuk user system)
⚠️ Auth: Bearer token via Authorization header (BUKAN cookie)
⚠️ Password: hash_password() dari core_utils.py — jangan pake bcrypt
```

### sessions
```
Collection:  sessions
Router:      routers/auth.py (auto-managed)
Key Fields:
  token       string   format: "sess_[hex12]"
  user_id     string   FK → users.id
  created_at  string

⚠️ JANGAN query sessions langsung dari router lain
⚠️ Gunakan current_user() dari dependencies.py
```

### products
```
Collection:  products
Router:      routers/products.py
Schema:      schemas.py → ProductPayload
Component:   ProductCard.jsx, AdminView.jsx (tab Product), SalesPortal.jsx
Key Fields:
  id          string   prefix "prod_"
  sku         string   UNIQUE — format: CAT-MOTIF-NNN (e.g. BTK-MEGA-001)
  name        string
  category    enum     Batik | Tenun | Lurik | Songket | Ulos | Jumputan | Endek
  variant     string
  color       string
  motif       string
  grade       enum     A | A+ | B | C
  supplier    string   (string only saat ini, bukan FK)
  base_unit   string   meter | yard | roll | pcs
  price       float    IDR per base_unit
  image       string   URL
  status      enum     active | inactive
  uom_conversions  list  [{from_unit, to_unit, factor}]
  batch_lot_rolls  list  [{batch, lot, roll_id}]
  --- METADATA SMART-SEARCH / AI-READY [PROPOSED KN_16 §8B.6] (disiapkan, diisi bertahap) ---
  description      text   deskripsi panjang (marketing/search)
  specifications   object {komposisi, lebar_cm, gramasi, perawatan, asal, ...} (key-value terstruktur)
  tags             list   [string]
  media            list   [{type: image|video, url}]  (multi-media; image lama tetap kompat)
  search_keywords  list   [string]  (untuk smart search)
  attributes       object {} facet/filter terstruktur
  ai_meta          object { embedding: [], recommender_tags: [], updated_at }  (KOSONG dulu — engine nanti)
  created_at  string
  updated_at  string

⚠️ SSOT TUNGGAL: Sales-view & Inventory-view = PROYEKSI dari products yang sama, BUKAN tabel terpisah
   (mis. GET /products?view=sales vs ?view=inventory). Cegah data ganda/konflik.
⚠️ JANGAN BUAT: items, goods, materials, kain, fabric, accessories, products_sales, products_inventory
⚠️ Stok ADA DI inventory_balances/inventory_rolls, BUKAN di products
```

### product_categories  [EPIC2 IMPLEMENTED — Master Kategori Produk]
```
Collection:  product_categories         Prefix: cat_
Router:      routers/categories.py
Schema:      routers/categories.py → CategoryPayload (inline)
Component:   features/admin/CategoryManager.jsx, AdminView.jsx (tab Kategori + dropdown form produk)
Key Fields:
  id            string   prefix "cat_"
  code          string   UNIQUE — uppercase slug (mis. BATIK)
  name          string   UNIQUE — nama kategori (mis. Batik) = nilai products.category
  base_unit     string   default UOM kategori (meter|yard|kg|roll|pcs) → default produk baru
  description   string
  sort_order    int      urutan tampil
  status        enum     active | inactive
  product_count int      DERIVED (count products by name) — tidak disimpan
  created_at    string
  updated_at    string

ℹ️ SSOT nama kategori. products.category menyimpan NAME (string), bukan id → kompat data historis.
ℹ️ Rename kategori mem-propagasi ke products.category (jaga konsistensi).
ℹ️ SO line meng-snapshot `category` (+base_unit, base_quantity) saat create; backfill historis idempotent.
⚠️ JANGAN BUAT: categories, product_category, kategori, product_groups
```

### ar_receipts  [EPIC3B IMPLEMENTED — AR Receipt / Payment Application]
```
Collection:  ar_receipts                Prefix: arc_   (number: AR-#####)
Router:      routers/ar_receipts.py
Service:     services/ar_receipt_service.py
Component:   features/crm/CollectionWorklist.jsx (modal Catat Pembayaran) + ARReceiptsList
Key Fields:
  id              string   prefix "arc_"
  number          string   UNIQUE — AR-00001 (next_doc_number, deletion-safe)
  customer_id     string   FK customers.id
  customer_name   string   snapshot
  entity_id       string   FK entities.id
  receipt_date    string   ISO
  method          enum     transfer | cash | giro | qris | ...
  amount          float    nominal diterima
  applied_total   float    total ter-alokasi ke order
  unapplied_amount float   sisa (amount - applied_total)
  allocations     array    [{order_id, order_number, applied, outstanding_after, payment_status}]
  notes           string
  status          enum     posted | void
  created_by / created_by_name / created_at / updated_at

ℹ️ EFEK SAMPING: meng-apply ke sales_orders.payments[] (+paid_total, +payment_status).
   payment_status: unpaid | partial | paid. Credit gate & Collection Worklist membaca payments[] → auto-update.
ℹ️ Alokasi eksplisit (allocations) atau auto-FIFO (order terbuka tertua) bila kosong.
ℹ️ SSOT outstanding = grand_total − Σ payments[].amount (lihat customer_service._order_paid).
⚠️ JANGAN BUAT: payments, receipts, ar_payments, collections (sebagai koleksi).
```

### incentive_rates  [EPIC4 IMPLEMENTED — Incentive Engine v2 rate matrix]
```
Collection:  incentive_rates             Prefix: irate_
Router:      routers/incentive_rates.py
Service:     services/sales_force_service.py (_compute_commission_per_sku)
Component:   features/crm/IncentiveRatesEditor.jsx (matrix entity×category)
Key Fields:
  id                      string  prefix "irate_"
  entity_id               string  FK entities.id | "all" (fallback semua entitas)
  category                string  = products.category / SO line snapshot
  incentive_unit          string  UOM dasar per_unit_amount (default meter)
  per_unit_amount         float   Rp per incentive_unit
  discount_threshold_type enum    pct | rp_per_unit  (basis ambang diskon line)
  discount_threshold      float   ambang diskon (>= → mekanik aktif)
  discount_mechanic       enum    tier_factor | potong_rp | cutoff
  discount_factor         float   tier_factor: komisi × faktor bila diskon > ambang
  discount_potong_rp      float   potong_rp: kurangi per_unit_amount (Rp/unit)
  margin_cap_pct          float   komisi/line ≤ X% margin line (margin-aware, WAC EPIC3)
  status                  enum    active | inactive
  created_at / updated_at

ℹ️ UNIK per (entity_id, category). Lookup engine: entity spesifik → fallback "all".
ℹ️ Mode strategi di system_settings.commission.strategy (per_sku default | achievement_tiered arsip).
ℹ️ Engine on-collection: iterasi line terbayar (pro-rata partial payment), cap by margin.
⚠️ JANGAN BUAT: incentive_rate, commission_rates, rates, sku_rates (sebagai koleksi).
```

### bank_accounts  [EPIC7-B IMPLEMENTED — Kas & Bank multi-akun + rekonsiliasi]
Koleksi kanonik `bank_accounts` (prefix `bank_`). Master akun kas/bank; mutasi tetap
di `cash_transactions` (SSOT kas) dgn field opsional `account_id`.
```
Collection:  bank_accounts                Prefix: bank_
Router:      routers/bank.py
Service:     services/bank_service.py
Component:   features/finance/BankAccountsView.jsx
Key Fields:
  id                string  prefix "bank_"
  name              string  nama tampilan akun
  account_type      enum    bank | cash
  bank_name         string  nama bank (kosong utk cash)
  account_number    string  no rekening
  entity_id         string  FK entities.id | "all"
  opening_balance   float   saldo awal
  currency          string  default IDR
  is_active         bool
  created_at / updated_at

Saldo akun (derived) = opening_balance + Σ(in) − Σ(out) cash_transactions
  posted (status≠void) dengan account_id = akun tsb.
Rekonsiliasi: cash_transactions.reconciled (bool) + reconciled_at.
ℹ️ Endpoint: GET /api/bank-accounts, POST /api/bank-accounts,
  PATCH /api/bank-accounts/{id}, GET /api/bank-accounts/{id}/ledger,
  POST /api/cash-transactions/{id}/reconcile. RBAC: permission "cash" (admin/manager).
⚠️ JANGAN BUAT: bank, banks, accounts, rekening (sebagai koleksi).
```

### gl_accounts  [EPIC7-C IMPLEMENTED — Chart of Accounts / Bagan Akun]
Koleksi kanonik `gl_accounts` (prefix `gla_`). Master bagan akun double-entry.
Normal balance: asset & expense = debit; liability, equity, income = credit.
```
Collection:  gl_accounts                  Prefix: gla_
Router:      routers/gl.py
Service:     services/gl_service.py
Component:   features/finance/ChartOfAccounts.jsx
Key Fields:
  id                string  prefix "gla_"
  code              string  UNIK, mis. "1-1100"
  name              string  nama akun
  type              enum    asset | liability | equity | income | expense
  normal_balance    enum    debit | credit (derived dari type)
  parent_code       string  FK gl_accounts.code (hierarki; "" = root)
  is_postable       bool    true = akun detail (boleh dijurnal); false = header
  is_active         bool
  system            bool    akun baku — tak boleh dihapus (boleh dinonaktifkan)
  currency          string  default IDR
  created_at / updated_at
ℹ️ Endpoint: GET/POST /api/gl/accounts, PATCH/DELETE /api/gl/accounts/{code},
  GET /api/gl/accounts/{code}/ledger. RBAC: permission "accounting" (admin/manager).
⚠️ JANGAN BUAT: accounts, coa, chart_of_accounts, akun (sebagai koleksi).
```

### journal_entries  [EPIC7-C IMPLEMENTED — General Ledger / Jurnal Umum]
Koleksi kanonik `journal_entries` (prefix `je_`). Jurnal double-entry SEIMBANG
(Σdebit == Σkredit). Auto-posting idempotent diturunkan dari SSOT
(`sales_orders` → pengakuan pendapatan; `cash_transactions` → mutasi kas) via
`POST /api/gl/sync` (source_type + source_id mencegah double-post).
```
Collection:  journal_entries              Prefix: je_
Router:      routers/gl.py
Service:     services/gl_service.py
Component:   features/finance/GeneralLedger.jsx
Key Fields:
  id                string  prefix "je_"
  number            string  JE-NNNNN (number series)
  date              string  ISO tanggal jurnal
  description       string
  source / source_type  enum  manual | sales_order | cash_transaction
  source_id         string  FK dokumen sumber ("" utk manual)
  source_label      string  label dokumen (mis. SO-0007, CASH-00001)
  lines             array   [{account_code, account_name, debit, credit, description}]
  total_debit       float   == total_credit (invarian)
  total_credit      float
  status            enum    posted | void (hanya manual yg boleh di-void)
  entity_id         string  FK entities.id
  created_by / created_at / updated_at
Laporan derived: Neraca Saldo (GET /api/gl/trial-balance) & Buku Besar per-akun
  (GET /api/gl/accounts/{code}/ledger). KPI: GET /api/gl/summary.
ℹ️ Endpoint: GET/POST /api/gl/journal, GET /api/gl/journal/{id},
  POST /api/gl/journal/{id}/void, POST /api/gl/sync. RBAC: permission "accounting".
⚠️ JANGAN BUAT: journals, general_ledger, gl, jurnal, ledger (sebagai koleksi).
```







### customers
```
Collection:  customers
Router:      routers/customers.py
Schema:      schemas.py → CustomerCreate, CustomerAddress
Component:   CustomerPanel.jsx, AdminView.jsx (tab Customer)
Key Fields:
  id          string   prefix "cust_"
  code        string   format: "CUST-NNNN"
  name        string
  pic_name    string   nama contact person
  phone       string
  email       string
  type        enum     Retailer | Wholesaler | Boutique
  city        string
  status      enum     active | inactive
  addresses   list     [{id, label, recipient_name, phone, city, address, is_primary}]
  npwp, credit_limit, sales_pic, entity_id   (sudah ada)
  --- CRM-LITE [PROPOSED KN_17] ---
  assigned_sales_id  string  FK users (salesperson pemilik) — WAJIB (kunci manajemen; sales kelola miliknya)
  segment            enum    Retail|Wholesale|Distributor|VIP  (KLASIFIKASI saja, BUKAN penentu harga)
  tags               list    [string]
  contacts           list    [{name, role, phone, email, is_primary}]
  lot_policy         enum    prefer_single|strict_single|allow_mixed (default prefer_single; KN_15)
  enforce_single_dye_lot  bool  P0-4 — bila true → alokasi SO dipaksa 1 dye_lot (dye_lot_strict)
  payment_profile    object  {allowed_methods:[kontan|tunai|tempo|dp|bertahap], default_method,
                              term_days, dp_percent, installment:{count,interval_days}}
  credit             object  {credit_limit, ar_outstanding(derived), overdue_amount(derived),
                              status: active|warning|blocked}
  customer_group_id  string? penghubung customer sama lintas-entitas (DISIAPKAN, default kosong) [KN_17 S38]
  status      enum     active | inactive | blocked
  created_by  string
  created_at  string

⚠️ scoped entity_id (customer terpisah per entitas; customer sama boleh lintas-entitas; kunci=assigned_sales_id)
⚠️ RBAC row-level: role=sales hanya lihat/kelola customer assigned_sales_id==dirinya (enforce backend)
⚠️ JANGAN BUAT: clients, buyers, pembeli, pelanggan_toko, crm_customers
```

### warehouses
```
Collection:  warehouses
Router:      routers/warehouses.py
Schema:      schemas.py → WarehousePayload
Component:   AdminView.jsx (tab Warehouse)
Key Fields:
  id          string   prefix "wh_" (contoh: wh_jakarta, wh_bandung)
  code        string   format: "WH-XXX"
  name        string
  city        string
  lat, lng    float    koordinat GPS
  active      bool
  zones       list     [{id, name, racks: [{id, name, bins: [{id, code, capacity}]}]}]
  created_at  string

⚠️ Hierarchy: Zone → Rack → Bin
⚠️ JANGAN BUAT: gudang, depot, storage_location sebagai collection terpisah
⚠️ Zone/Rack/Bin adalah EMBEDDED dalam warehouse document
```

### uoms
```
Collection:  uoms
Router:      routers/uoms.py
Schema:      schemas.py → UOMPayload
Component:   AdminView.jsx (tab UOM)
Default UOMs:
  uom_meter  → MTR (length, precision 2)
  uom_yard   → YRD (length, precision 2)
  uom_roll   → RLL (volume, precision 0)
  uom_pcs    → PCS (count, precision 0)
Key Fields:
  id, code, name, base_type (length|volume|weight|count), precision, status

⚠️ JANGAN BUAT: satuan, unit_ukur, measurement
```

### sales_orders
```
Collection:  sales_orders
Router:      routers/sales_orders.py
Schema:      schemas.py → SalesOrderCreate, SalesOrderItemIn
Component:   SalesPortal.jsx, OrdersView.jsx, CartPanel.jsx
Status Lifecycle:
  reserved → waiting_approval → approved → confirmed → dispatched → done
  (cancelled tersedia di setiap stage)
Key Fields:
  id          string   prefix "so_"
  number       string  format: "SO-NNNNN"  (FIELD = "number", BUKAN "order_number")
  customer_id  string  FK → customers.id
  customer_name string SNAPSHOT (denormalized)
  items        list    [{product_id, product_name, sku, quantity, unit, price, subtotal,
                          discount_percent, discount_amount, line_total}]
                        (FIELD item = "quantity" & "price"; BUKAN "qty"/"unit_price")
                        subtotal = price×quantity (GROSS, invarian); line_total = subtotal−discount_amount
  allocations  list    [{warehouse_id, warehouse_name, warehouse_city, product_id, quantity}]
                        SNAPSHOT fulfillment (top-level, dipakai render dokumen)
  status       enum    (lihat lifecycle di atas)
  total_amount float    = Σ items.subtotal (GROSS — invarian verify_data_integrity L4)
  # Fase 1B — breakdown diskon + PPN (field TERPISAH agar total_amount tetap GROSS):
  items_discount_total   float
  order_discount_percent float   order_discount_amount float   discount_total float
  net_subtotal float   = total_amount − discount_total (= DPP base)
  dpp float   ppn_rate float   ppn_mode enum(excluded|included)   is_pkp bool
  ppn_amount float   grand_total float  (= yang dibayar customer)
  payment_term_code string   payment_term_name string   payment_status enum(pending|paid_partial|paid)
  # Fase 1B — approval dinamis (dari approval_rules):
  approval_required bool   required_approval_role string|null   approval_amount float
  sales_name   string
  shipping_address_id string
  reservation_expires_at string  UTC ISO
  created_at, updated_at string

⚠️ JANGAN BUAT: orders, customer_orders, so_list, penjualan
⚠️ Stock reservation terjadi di inventory_balances SAAT order dibuat
⚠️ Dispatch flow: sales_orders.confirm → wms.outbound_from_order → outbound_picking.dispatch
⚠️ Fase 1B: pricing dihitung services/config_service.compute_order_pricing (PPN ikut PKP entitas);
   approval via evaluate_approval + role_satisfies. INVARIAN: total_amount & item.subtotal tetap GROSS.
```

### invoices
```
Collection:  invoices
Router:      routers/invoices.py
Schema:      schemas.py → PaymentSimulationCreate
Key Fields:
  id, number ("INV-NNNNN-NN"), order_id, order_number, customer_id, customer_name, entity_id,
  amount (= grand_total order), status (paid), method, created_by, created_at
  # Fase 1B — snapshot pajak untuk Faktur/Invoice:
  total_amount, discount_total, net_subtotal, dpp, ppn_rate, ppn_mode, ppn_amount, grand_total,
  payment_term_code, payment_term_name

⚠️ SIMULATED payment — belum real gateway
⚠️ amount default = order.grand_total (server-authoritative); jangan embed _id sub-dok (RC ObjectId)
⚠️ JANGAN BUAT: bills, tagihan, faktur sebagai collection terpisah
```

### inventory_balances
```
Collection:  inventory_balances
Router:      routers/inventory.py
Component:   InventoryStockView.jsx
Key Fields:
  id           string   prefix "bal_"
  product_id   string   FK → products.id
  warehouse_id string   FK → warehouses.id
  owner_entity_id string FK → business_entities.id   [IMPLEMENTED Fase 0.5 — kepemilikan, 3-key]
  on_hand_qty  float    total fisik (= Σ bucket fisik)
  available_qty / reserved_qty / committed_qty / picked_qty / packed_qty / quarantine_qty / blocked_qty / damaged_qty  float (bucket fisik)
  on_order_qty / in_transit_inbound_qty / in_transit_transfer_qty / in_transit_intercompany_qty / in_transit_sales_qty  float (pipeline/transit)
  owned_qty / incoming_qty / atp_qty  float (derived)
  in_transit_qty float  legacy alias (= Σ transit)
  updated_at   string

⚠️ UNIQUE per (product_id + warehouse_id + owner_entity_id)  [IMPLEMENTED Fase 0.5]
   Balance = PROYEKSI/cache yang diturunkan dari inventory_rolls (SSOT fisik) via roll_service.rebuild_balance().
   [KN_15 §3.4] Bucket DETAIL: fisik (available/reserved/committed/picked/packed/quarantine/blocked/damaged→on_hand)
   + transit (on_order/in_transit_*) + derived (owned/incoming/atp). Status: IMPLEMENTED Fase 0.5.
⚠️ JANGAN pindahkan stok dengan update langsung — selalu buat inventory_movements + rebuild_balance
⚠️ JANGAN BUAT: stock, stok, stock_levels, inventory_count, stock_units, rolls (lepas)
```

### inventory_rolls  [IMPLEMENTED Fase 0.5 — koleksi baru, SSOT fisik]
```
Collection:  inventory_rolls            Prefix: roll_
Router:      routers/inventory.py (atau routers/rolls.py saat coding)
Component:   InventoryStockView.jsx (+ stock-breakdown matrix), SalesPortal (visibilitas)
Status:      DRAFT / PROPOSED (belum ada di DB/kode). Lihat KN_15.
Key Fields:
  id               string   prefix "roll_"  (1 dokumen = 1 roll fisik)
  product_id       string   FK → products.id  (katalog SHARED)
  owner_entity_id  string   FK → business_entities.id  (KEPEMILIKAN — wajib utk internal)
  ownership_type   enum     internal | supplier_consignment | reseller_consignment
                            (DEFAULT internal; konsinyasi DISIAPKAN, default OFF — KN_16 G1)
  consignor_ref    object?  {type: supplier|customer, id, name}  (bila konsinyasi)
  warehouse_id     string   FK → warehouses.id  (LOKASI gudang — netral)
  bin_id           string   lokasi detail (Zone→Rack→[Level]→Bin)
  lot              string   dye-lot generik (WAJIB) — penentu warna/celup (gate: harus terisi)
  dye_lot          string   P0-4 — dye lot AKTUAL tekstil (default = `lot` agar backward-compatible)
  batch            string   batch produksi/pembelian
  roll_no          string   nomor/serial roll fisik (label)
  length_initial   float    panjang awal aktual (catch weight)
  length_remaining float    sisa panjang (0 ≤ x ≤ length_initial)
  unit             string   base unit (meter|yard|...)
  grade            enum     A | A+ | B | C | BS   (BS = barang sisa/seconds)
  qc_grade         string   P0-4 — grade hasil keputusan QC (saat accept; = grade)
  defects          list     P0-4 — profil cacat tekstil [string] (mis. ["belang","noda"])
  status           enum     on_order|in_transit_inbound|receiving|quarantine|available|reserved|
                            committed|picked|packed|cross_dock|in_transit_sales|sold|
                            in_transit_transfer|in_transit_intercompany|blocked|damaged|returned|scrapped
  tracking_mode    enum     rfid | barcode | document | manual   (stok visible TANPA RFID — KN_15 §7B)
  earmarked_for    object?  {type: sales_order|special_order, id}  (pegging supply↔demand)
  location_type    enum     warehouse_bin|transit_in|transit_out|cross_dock|drop_ship|transit_transfer
  reserved_ref     object   {type: sales_order|transfer, id}
  unit_cost        float?   HPP final per BASE unit (P0-5: base + Σ landed cost; NULLABLE bila tak ada harga PO)
  base_unit_cost   float?   P0-5 — HPP dasar per unit dari harga PO saat GR (sebelum landed cost)
  landed_cost_total float   P0-5 — Σ biaya landed cost yang dialokasikan ke roll ini (audit; default 0)
  landed_cost_refs list     P0-5 — daftar voucher landed cost (LCV-NNNNN) yang sudah di-apply
  acquired         object   {via: po|transfer|initial|adjustment|return, ref_id, date}
  grade            string?  Grade tekstil (A|A+|B|C|BS) — P0-4 / di-set objektif oleh inspeksi 4-Point (6.2)
  defects          list     profil cacat; P0-4 free-text atau 6.2 [{point_value 1..4, count, note}]
  inspection       object?  Fase 6.2 — {points, grade, defects[], gsm_actual?, width_actual?, thresholds, inspected_by, inspected_at}
  rfid_tag_id      string?  FK → rfid_tags (Fase 5)
  is_remnant       bool     true bila roll = sisa potongan (BS)
  created_at, updated_at, created_by, created_by_name

⚠️ SSOT fisik stok. inventory_balances = PROYEKSI yang di-rebuild dari sini.
⚠️ Reservasi terjadi di LEVEL ROLL (atomic find_one_and_update status available→reserved).
⚠️ Penjualan owner-scoped: roll hanya boleh dijual entitas pemiliknya (owner_entity_id == SO.entity_id).
⚠️ JANGAN BUAT: stock_units, rolls (lepas), stock — gunakan inventory_rolls (namespace inventory_*).
```

### inventory_movements
```
Collection:  inventory_movements
Router:      routers/inventory.py
Component:   InventoryStockView.jsx (tab Ledger)
Movement Types:
  initial_stock | inbound_receiving | outbound_dispatch |
  transfer_out | transfer_in | cycle_count_adjustment | reservation | release_reservation
  [PROPOSED KN_15] + ownership_transfer_out | ownership_transfer_in (inter-company, owner berubah)
  [PROPOSED KN_15] + remnant_created | quarantine_in | quarantine_out | scrap
Key Fields:
  id, product_id, warehouse_id, movement_type, quantity, unit,
  batch, lot, roll_id, source_document, timestamp
  [PROPOSED KN_15] + owner_entity_id (wajib), roll_id (FK inventory_rolls),
                     from_owner_entity_id & to_owner_entity_id (utk ownership_transfer)

⚠️ APPEND-ONLY — tidak pernah update/delete movement yang sudah ada
⚠️ JANGAN BUAT: stock_history, gerakan_stok, stock_log
```

### system_settings  [Fase 1A IMPLEMENTED — Configuration Foundation]
```
Collection:  system_settings          Prefix: set_
Router:      routers/settings.py       Service: services/config_service.py
Component:   SettingsPanel.jsx (Admin → Pengaturan)
Key Fields:
  id, scope ("global" | entity_id),
  tax       {ppn_rate, ppn_mode(excluded|included), efaktur_enabled, is_pkp(derived)}
  finance   {base_currency, fiscal_year_end_month, default_payment_term_code}
  sales     {quotation_enabled, allow_partial_shipment, allow_order_discount, allow_item_discount}
  inventory {default_uom, min_cut_qty, intercompany_transfer_required}
  created_at, updated_at

⚠️ Effective settings = global di-override per-entitas (config_service.get_effective_settings).
⚠️ SEMUA configurable — JANGAN hardcode PPN/term/currency di kode.
⚠️ JANGAN BUAT: settings, config, configuration (lepas) — gunakan system_settings.
```

### payment_terms  [Fase 1A IMPLEMENTED]
```
Collection:  payment_terms             Prefix: pterm_
Router:      routers/settings.py
Component:   SettingsPanel.jsx (tab Term Pembayaran)
Key Fields:
  id, code (UNIQUE), name, type (cash|credit|dp|installment),
  net_days, dp_percent, installment_count, sort, active, created_at, updated_at

⚠️ JANGAN BUAT: terms, payment_term (singular) — gunakan payment_terms.
```

### approval_rules  [Fase 1A IMPLEMENTED]
```
Collection:  approval_rules            Prefix: aprule_
Router:      routers/settings.py       Service: config_service.evaluate_approval()
Component:   SettingsPanel.jsx (tab Matriks Approval)
Key Fields:
  id, doc_type (sales_order|purchase_order|transfer|discount), entity_id ("all"|entity_id),
  min_amount, max_amount (null = tak terhingga), required_role ("" = tanpa approval),
  is_percent (utk discount), sort, active, created_at, updated_at

⚠️ Matriks CONFIGURABLE menyesuaikan flow. Rule entitas-spesifik diutamakan, fallback "all".
⚠️ JANGAN BUAT: approval_matrix, approvals (lepas) — gunakan approval_rules.
```

### approval_requests  [Sub-fase 1.6+ IMPLEMENTED — Approval Request per Dokumen]
```
Collection:  approval_requests         Prefix: appreq_
Router:      routers/approval_requests.py
Component:   features/approvals/ApprovalInbox.jsx
Key Fields:
  id, entity_id, doc_type (sales_order|purchase_order|transfer|price_approval),
  doc_id, doc_number, requester_id, requester_name, required_role,
  amount, status (pending|approved|rejected), notes, decided_by, decided_at,
  created_at, updated_at
⚠️ JANGAN BUAT: approval_queue, approvals (lepas) — gunakan approval_requests.
```

### price_approvals  [Sub-fase 1.7 IMPLEMENTED — Special Price / Approval Harga]
```
Collection:  price_approvals           Prefix: pra_
Router:      routers/price_approvals.py
Service:     services/storage_service.py (upload bukti — Emergent Object Storage)
Component:   features/sales/PriceApprovals.jsx
Consumed by: routers/sales_orders.py (get_effective_special_price → override harga item)
Key Fields:
  id, entity_id, customer_id, customer_name, product_id, sku, product_name,
  normal_price (snapshot harga produk), requested_price (harga khusus/unit),
  min_quantity, unit, reason, valid_from, valid_until ("" = tanpa kadaluarsa),
  status (draft|pending|approved|rejected), attachments[] (bukti),
  requested_by, requested_by_name, approved_by, approved_by_name,
  decision_notes, decided_at, created_at, updated_at
Attachment item:
  id (att_), storage_path, original_filename, content_type, size,
  uploaded_by, uploaded_at, is_deleted (soft-delete; storage tak punya delete API)
Status flow:  draft → pending → approved | rejected
RBAC:
  sales   → create/update/delete pengajuan SENDIRI (row-level)
  manager → approve/reject; admin → semua
Konsumsi SO:
  item.price_approval_id valid (approved, berlaku, qty ≥ min_quantity) → price = requested_price.
  INVARIAN tetap: item.subtotal = price × quantity.

⚠️ Special Price = price_approvals (BUKAN koleksi 'special_prices'/'price_lists' lepas).
⚠️ JANGAN BUAT: special_prices, nego_harga, price_overrides — gunakan price_approvals.
```


### shipments  [Sub-fase 1.8 IMPLEMENTED — Status SO diperluas + Partial Shipment]
```
Collection:  shipments               Prefix: shp_   (No. Surat Jalan: SJ-#####)
Router:      routers/outbound_picking.py (GET /shipments, GET /shipments/{id}/surat-jalan)
Service:     services/shipment_service.py (dispatch_task), services/fulfillment_status.py
Component:   features/wms/OutboundScanInterface.jsx, features/orders/OrderDetailPanel.jsx
Key Fields:
  id, shipment_no (SJ-#####), order_id, order_number, task_id, allocation_id,
  warehouse_id, warehouse_name, warehouse_city, product_id, product_name, sku,
  qty (BASE UNIT), unit, rolls[] ({roll_id, lot, length, unit}),
  is_partial, status (dispatched), created_by, created_at
Dibuat saat:  dispatch task outbound (parsial/penuh) — 1 record per event dispatch.
INVARIAN (verify_data_integrity L4-SHIP):
  shipped_qty ≤ quantity per task · Σ shipments.qty == Σ task.shipped_qty per order ·
  status SO ⟺ progres task (picked / partially_shipped / shipped / done).
SSOT-safe (KN_15 §10): pengiriman = roll committed → in_transit_sales (BUKAN $inc balance);
  mark-delivered → roll in_transit_sales → 'delivered' (keluar dari owned_qty).
Status SO (Sub-fase 1.8): confirmed → partially_picked → picked → partially_shipped
  → shipped → done (manual via /sales-orders/{id}/mark-delivered).
⚠️ Status 'dispatched' di SO DEPRECATED → gunakan shipped/done. Task tetap pakai 'dispatched'.
```

### tax_invoices  [Sub-fase 1.9 IMPLEMENTED — Faktur Pajak Jual]
```
Collection:  tax_invoices             Prefix: fkt_   (No. Internal: FKT-##### + NSFP resmi 16-digit)
Router:      routers/tax_invoices.py (GET /tax-invoices, POST /sales-orders/{id}/tax-invoice,
             PATCH /tax-invoices/{id}/nsfp, POST .../replace, POST .../cancel, GET .../document)
Service:     services/tax_invoice_service.py (issue/replace/cancel/set_nsfp/render_faktur_html)
Component:   features/finance/TaxInvoices.jsx, features/orders/OrderDetailPanel.jsx
Key Fields:
  id, number (FKT-#####), nsfp (16-digit resmi, opsional/menyusul), kode_transaksi (01..09),
  status (normal|pengganti|batal), replaces_id, replaced_by_id, cancel_reason, replace_reason,
  faktur_date, order_id, order_number, entity_id,
  seller_name, seller_npwp, seller_address (snapshot entitas PKP),
  customer_id, customer_name, customer_npwp, customer_address, has_customer_npwp (snapshot),
  items[] ({product_name, sku, quantity, unit, price, subtotal, discount_amount, line_total}),
  total_amount, discount_total, net_subtotal, dpp, ppn_rate, ppn_mode, ppn_amount, grand_total,
  is_pkp, created_by, created_at, updated_at
Dibuat saat:  MANUAL (opsional — pajak TIDAK wajib) dari Order detail; PKP-only + ppn_amount>0; idempotent (1 aktif/order).
INVARIAN (verify_data_integrity L4-FKT):
  PPN == DPP × rate · Grand == DPP + PPN · ref order valid · normal/pengganti ⟹ is_pkp & ppn>0 ·
  ≤1 faktur aktif (bukan batal & belum diganti) per order · nomor unik · rantai pengganti (replaces_id valid).
⚠️ Penomoran HYBRID: FKT-##### internal + NSFP resmi diisi menyusul (alokasi DJP/Coretax e-Faktur).
⚠️ JANGAN BUAT: faktur, faktur_pajak, bills, tagihan — gunakan tax_invoices.
```



### wms_tasks
```
Collection:  wms_tasks
Routers:     routers/wms.py (generic CRUD)
             routers/inbound_receiving.py (inbound-specific ops)
             routers/outbound_picking.py (outbound-specific ops)
Schema:      schemas.py → WMSTaskCreate, ScannerScan
Components:  ScannerTaskPanel.jsx (generic)
             InboundScanInterface.jsx (inbound)
             OutboundScanInterface.jsx (outbound)
flow_type:   inbound | outbound
Status Inbound:
  waiting_goods → receiving → qc_check → completed | escalated
  [Depth #3a] QC Hold aktif (config.purchasing.qc_on_receipt=True, default):
    waiting_goods → receiving → qc_check → (complete) → qc_pending
      → (qc-decision) → completed | qc_rejected
Status Outbound:
  created → picking → packing → staging → dispatched | escalated
Key Fields:
  id, flow_type, source_type, product_id, product_name, sku,
  quantity, unit, warehouse_id, bin_id, batch, lot, roll_id,
  status, scanned_items: [{scan_value, scan_type, timestamp, actor}],
  source_document (PO id atau SO id), escalation_info, created_at
  [Depth #3a QC] quarantine_qty, qc_status (pending|passed|partial|rejected),
  qc_accept_qty, qc_reject_qty, qc_reject_disposition (damaged|return),
  qc_reason, qc_by, qc_at

⚠️ Depth #3a — QC Hold/Quarantine saat GR:
  • inbound_receiving.complete → roll dibuat status `quarantine` (BUKAN available)
    + roll.qc_task_id = task.id; task → `qc_pending`; TIDAK auto-fulfill.
  • Endpoints (routers/inbound_receiving.py + services/qc_service.py):
    GET  /api/inbound/qc/queue             — antrian qc_pending + quarantine_qty
    POST /api/inbound/tasks/{id}/qc-decision {accept_qty, reject_qty,
         reject_disposition: damaged|return, reason}
  • Accept → roll quarantine→available + auto_fulfill_backorders.
  • Reject damaged → roll quarantine→`damaged`.
  • Reject return  → roll quarantine→`returned_supplier` (keluar on_hand) +
    buat purchase_returns (Nota Debit, stock_adjusted=True, source=qc_reject).
  • SSOT: semua transisi level ROLL (split bila parsial) → rebuild_balance.

⚠️ SATU collection untuk inbound DAN outbound — dibedakan oleh flow_type
⚠️ JANGAN BUAT: inbound_tasks, outbound_tasks, receiving_tasks sebagai collection terpisah
```

### warehouse_transfers
```
Collection:  warehouse_transfers
Router:      routers/transfers.py
Schema:      schemas.py → TransferCreate, TransferApprove, TransferReject
Component:   TransferManagement.jsx
Status Lifecycle:
  draft → waiting_approval → approved → picking → staging → dispatched → received | rejected
Key Fields:
  id, transfer_number, source_warehouse_id, dest_warehouse_id,
  items: [{product_id, product_name, qty, unit, batch, lot, roll_id}],
  status, requested_by, approved_by, notes, created_at, updated_at
  [PROPOSED KN_15] + transfer_kind (intra_entity | inter_entity),
                     source_entity_id, dest_entity_id, transfer_price?, linked_order_id?

⚠️ [PROPOSED KN_15] Inter-company (beda entitas) = EXTEND koleksi ini (transfer_kind=inter_entity),
   BUKAN koleksi baru. Memicu ownership_transfer movement + (Fase 4) AR/AP antar entitas. Lihat KN_15 §7.
⚠️ JANGAN BUAT: transfers, stock_transfer, pemindahan_barang, inter_entity_transfers
```

### cycle_count_sessions
```
Collection:  cycle_count_sessions
Router:      routers/cycle_count.py
Component:   CycleCount.jsx
Status Lifecycle:
  draft → in_progress → submitted → approved | rejected
Key Fields:
  id, session_number, warehouse_id, status,
  items: [{id, product_id, expected_qty, actual_qty, variance, status}],
  submitted_by, approved_by, created_at

⚠️ Approval generate inventory_movements (cycle_count_adjustment)
⚠️ JANGAN BUAT: stock_count, physical_count, stock_opname
```

### purchase_orders
```
Collection:  purchase_orders
Router:      routers/purchase_orders.py
Schema:      schemas.py → PurchaseOrderCreate, POItemCreate, POReceiveItem
Component:   PurchaseOrderManagement.jsx
Status Lifecycle:
  [waiting_approval →] pending → receiving → completed | partial | cancelled
  (waiting_approval hanya jika total_amount memicu approval_rules; lihat Fase 1B)
Key Fields:
  id, po_number (format: PO-NNNNN), supplier_name, supplier_contact,
  warehouse_id, items: [{product_id, quantity, unit, price, subtotal, received_qty}],
  status, expected_delivery_date, notes, created_by, created_at, total_amount
  # Fase 1B — approval dinamis:
  approval_required bool   required_approval_role string|null
  approval_status enum(not_required|pending|approved)   approval_amount float   approved_by string
  # Depth #3 — guard penyimpangan harga:
  approval_reason string(amount_threshold|price_deviation|amount_threshold+price_deviation|"")
  price_deviation {flagged bool, threshold_pct, max_deviation_pct, items:[{sku,price,ref_price,unit,deviation_pct}]}
  last_received_at string|null   # Depth #3 — timestamp penerimaan (scorecard)
  # Setting terkait: settings.purchasing.price_deviation_approval_percent (default 10.0)

⚠️ Supplier adalah STRING saat ini — belum ada supplier master collection
⚠️ Supplier: gunakan FK `supplier_id` → suppliers.id (Fase 3). `supplier_name`/
   `supplier_npwp`/`supplier_contact` = SNAPSHOT saat PO dibuat (backward compat;
   PO lama tanpa supplier_id tetap valid via string).
⚠️ PO tanpa approval → langsung buat wms_tasks (inbound). PO butuh approval → wms_tasks
   dibuat HANYA setelah /purchase-orders/{id}/approve (role_satisfies dari approval_rules).
   /purchase-orders/{id}/reject → status 'rejected' (tanpa task).
⚠️ Depth 1A — status lifecycle: waiting_approval → pending → receiving → partial → completed
   (dihitung dari Σ received_qty vs quantity ± toleransi via recompute_po_status).
   /purchase-orders/{id}/close → 'closed_short' (tutup kurang; batalkan task terbuka).
⚠️ Depth 1C — keuangan/AP: field amount_paid, returned_amount, outstanding, payment_status
   (unpaid|partial|paid), payments[]. /purchase-orders/{id}/pay → cash_transaction(out,
   ref_type=purchase_order) + update AP. /purchase-orders/payables/summary → AP + aging.
⚠️ JANGAN BUAT: po, pembelian, supplier_orders, procurement
```

### suppliers
```
Collection:  suppliers          Prefix: sup_
Router:      routers/suppliers.py
Schema:      schemas.py → SupplierCreate, SupplierPriceListCreate, GenericPatch
Component:   SuppliersView.jsx (Pembelian → Pemasok) + SupplierDetailPanel.jsx
Status:      active | inactive (soft delete via DELETE)
Key Fields:
  id, code (format: SUP-NNNNN), name, npwp, pic_name, phone, email, address,
  city, goods_type (jenis barang), payment_term_code, lead_time_days (Depth #3),
  entity_id, notes, status, created_by, created_at, updated_at
Endpoints:   GET/POST /suppliers · GET/PATCH/DELETE /suppliers/{id}
             # Depth #3 — Supplier Intelligence:
             GET /suppliers/{id}/scorecard       (metrik dari PO + penerimaan + retur)
⚠️ entity_id = default scoped (ent_ksc); supplier bisa dipakai lintas-entitas.
⚠️ JANGAN BUAT: vendor, vendors, pemasok
```

### supplier_price_lists
```
Collection:  supplier_price_lists   Prefix: spl_
Router:      routers/suppliers.py
Schema:      schemas.py → SupplierPriceListCreate (PATCH via GenericPatch)
Service:     services/supplier_service.py → resolve_price()
Component:   SupplierPriceList.jsx (tab di SupplierDetailPanel)
Status:      active | inactive (soft delete via DELETE)
Key Fields:
  id, supplier_id (FK → suppliers.id), supplier_name (snapshot),
  product_id (FK → products.id), sku, product_name (snapshot),
  price (per unit), unit (UOM; default base_unit produk — ikut UOM engine 1.13),
  min_qty (MOQ), lead_time_days (0=pakai default supplier),
  valid_from, valid_until ("" = open), currency (IDR), entity_id, notes,
  status, created_by, created_at, updated_at
Endpoints:   GET/POST /suppliers/{id}/price-list ·
             PATCH/DELETE /supplier-price-list/{entry_id} ·
             GET /supplier-price-list/resolve?supplier_id=&product_id=&qty=
Dipakai:     auto-isi harga di PO create + PR→PO convert (Depth #3).
⚠️ JANGAN BUAT: price_list, harga, vendor_prices
```

### cash_transactions
```
Collection:  cash_transactions  Prefix: cash_
Router:      routers/cash.py
Schema:      schemas.py → CashTransactionCreate
Component:   CashManagementView.jsx (Pembelian → Pengelolaan Kas)
cash_type:   kas_kecil (per entitas) | kas_besar (gabungan, entity_id="all")
direction:   in (masuk) | out (keluar)   ·   status: posted | void
Key Fields:
  id, number (format: CASH-NNNNN), cash_type, direction, amount, category,
  description, entity_id, ref_type, ref_id, txn_date, status, created_by,
  created_at, updated_at
Endpoints:   GET /cash-transactions · GET /cash-transactions/summary ·
             POST /cash-transactions · POST /cash-transactions/{id}/void
Invarian:    saldo = Σ(amount where direction=in) − Σ(amount where direction=out)
             untuk status≠void.
⚠️ JANGAN BUAT: kas, petty_cash, cash
```

### purchase_returns
```
Collection:  purchase_returns  Prefix: pret_
Router:      routers/purchase_returns.py · Service: services/purchase_return_service.py
Schema:      schemas.py → PurchaseReturnCreate, PurchaseReturnItem, PurchaseReturnDecision
Component:   PurchaseReturns.jsx (Pembelian → Retur Beli)
Status:      draft → pending_approval → approved | rejected
Key Fields:
  id, number (PRET-NNNNN), supplier_id, supplier_name, po_id, po_number,
  warehouse_id, warehouse_name, entity_id, items[{product_id, sku, product_name,
  quantity, unit, price, subtotal, reason, condition}], total_amount, reason,
  status, debit_note_number (DN-NNNNN saat approved), stock_adjusted,
  created_by, approved_by, rejected_by, ...
Endpoints:   GET/POST /purchase-returns · GET /purchase-returns/{id} ·
             POST /{id}/submit · /{id}/approve · /{id}/reject
Efek approve: KURANGI inventory_rolls available (FIFO, status→returned_supplier),
             movement return_out, terbitkan Nota Debit, KURANGI AP (PO.returned_amount).
⚠️ JANGAN BUAT: retur_beli, debit_notes, po_returns, vendor_returns
```

### purchase_requisitions
```
Collection:  purchase_requisitions  Prefix: pr_
Router:      routers/purchase_requisitions.py · Service: services/purchase_requisition_service.py
Schema:      schemas.py → PurchaseRequisitionCreate, PurchaseRequisitionItem,
             PurchaseRequisitionDecision, PurchaseRequisitionConvert, SpecialOrderToPR
Component:   PurchaseRequisitions.jsx, ReorderSuggestions.jsx (Pembelian)
Status:      draft → pending_approval → approved → converted | rejected | cancelled
Key Fields:
  id, number (PR-NNNNN), entity_id, warehouse_id, warehouse_name,
  items[{product_id (opsional), sku, product_name, description, quantity, unit,
  est_price, subtotal, note}], total_est_amount, source (manual|reorder|special_order),
  source_ref_id, preferred_supplier_id, preferred_supplier_name, reason,
  needed_by_date, status, approval_required, required_approval_role, approval_status,
  po_id, po_number (saat converted), created_by, approved_by, rejected_by, ...
Endpoints:   GET/POST /purchase-requisitions · GET /purchase-requisitions/{id} ·
             GET /purchase-requisitions/reorder-suggestions ·
             POST /{id}/submit · /{id}/approve · /{id}/reject · /{id}/cancel ·
             POST /{id}/convert-to-po · POST /special-orders/{id}/create-pr (jembatan OD)
Depth #2a:   PR → approval (matriks 'purchase_requisition') → konversi ke PO (catalog only)
Depth #2b:   reorder-suggestions berbasis products.reorder_point/reorder_qty + on_order (anti double-order)
Depth #2c:   jembatan Special Order → PR (item non-katalog) + on_order/ATP (status_board)
⚠️ JANGAN BUAT: requisitions, pr_list, permintaan_pembelian, material_requests
```

### vendor_bills  [Fase 5.2 P0-2 IMPLEMENTED — Vendor Bill + 3-Way Matching]
```
Collection:  vendor_bills      Prefix: vbill_
Router:      routers/vendor_bills.py · Service: services/vendor_bill_service.py
Schema:      schemas.py → VendorBillCreate, VendorBillItemInput,
             VendorBillPaymentCreate, VendorBillDecision
Component:   VendorBillsView.jsx (Pembelian → Tagihan Supplier) +
             VendorBillCreateModal.jsx + VendorBillDetailPanel.jsx
Status:      draft → pending_approval → posted → paid (+ cancelled)
Key Fields:
  id, bill_number (VB-NNNNN), supplier_invoice_no (dedupe per supplier),
  po_id, po_number, supplier_id, supplier_name, supplier_npwp,
  warehouse_id, warehouse_name, entity_id, bill_date, due_date,
  match_mode (received|ordered),
  items[{product_id, sku, product_name, unit, billed_qty, quantity(=billed_qty),
    price, po_price, discount_percent, discount_amount, subtotal, line_total,
    ordered_qty, received_qty, already_billed_qty, remaining_qty,
    match{qty_status, price_status, price_variance_pct, messages[]}}],
  total_amount (GROSS Σ subtotal), items_discount_total, order_discount_percent,
  order_discount_amount, discount_total, net_subtotal, dpp, ppn_rate, ppn_mode,
  is_pkp, ppn_amount, grand_total, tax_mode,
  match_status (matched|warning|blocked), match_exceptions[], within_tolerance,
  approval_required, required_approval_role, approval_status, approved_by,
  amount_paid, outstanding, payment_status (unpaid|partial|paid), payments[],
  timeline[], created_by, created_by_id, created_at, updated_at
Endpoints:   GET/POST /vendor-bills · GET /vendor-bills/{id} ·
             GET /vendor-bills/payables/summary ·
             GET /purchase-orders/{id}/billing-context ·
             POST /vendor-bills/{id}/submit · /{id}/approve · /{id}/reject ·
             POST /vendor-bills/{id}/pay · /{id}/cancel
3-Way Match: PO (ordered) ↔ GR (received_qty) ↔ Bill (billed_qty). Toleransi
             settings.purchasing.bill_qty_tolerance_percent (default 0) &
             bill_price_tolerance_percent (default 5). blocked = over-billing di
             luar toleransi (tak bisa submit). warning = variance dalam toleransi
             (butuh approval manager). matched = bersih (auto-post).
Efek post:   AP berbasis bill. sync_po_billing() update PO.billed_total/unbilled_total.
Pay:         cash_transaction(out, ref_type=vendor_bill) + update AP bill.
⚠️ JANGAN BUAT: bills, tagihan, vendor_invoice, ap_bills, supplier_bills, vendor_invoices
```

### landed_cost_vouchers  [Fase 5.4 P0-5 IMPLEMENTED — Landed Cost → alokasi HPP roll]
```
Collection:  landed_cost_vouchers   Prefix: lcv_
Router:      routers/landed_cost.py · Service: services/landed_cost_service.py
Schema:      schemas.py → LandedCostCreate, LandedCostLineInput,
             LandedCostPaymentCreate, LandedCostDecision
Component:   LandedCostView.jsx (Pembelian → Landed Cost) +
             LandedCostCreateModal.jsx + LandedCostDetailPanel.jsx
Status:      draft → pending_approval → applied → paid (+ cancelled)
Key Fields:
  id, voucher_number (LCV-NNNNN), provider_name, supplier_invoice_no (dedupe),
  po_ids[], po_numbers[], entity_id,
  basis (value|quantity), effective_basis,
  cost_lines[{category(freight|duty|insurance|handling|other), description, amount}],
  total_cost, voucher_date, due_date, target_roll_count,
  allocation_preview[], allocations[{roll_id, roll_no, product_id, length, weight,
    base_unit_cost, current_unit_cost, alloc_amount, per_unit, new_unit_cost}],
  approval_required(true), required_approval_role(manager), approval_status,
  approved_by, approved_at, applied_at,
  amount_paid, payment_status (n/a|unpaid|partial|paid), payments[],
  timeline[], created_by, created_by_id, created_at, updated_at
Endpoints:   GET/POST /landed-costs · GET /landed-costs/{id} ·
             GET /landed-costs/payables/summary ·
             GET /purchase-orders/{id}/landed-cost-context ·
             POST /landed-costs/{id}/submit · /{id}/approve · /{id}/reject ·
             POST /landed-costs/{id}/pay · /{id}/cancel
Alokasi:     biaya total dibagi ke roll (acquired.ref_id ∈ po_ids). Basis value =
             base_unit_cost × length; quantity = length. Fallback value→quantity bila
             Σbobot=0; lalu bagi rata. Σalloc == total_cost (sisa pembulatan ke roll akhir).
Efek apply:  HANYA saat APPROVE (manager+, SoD pembuat≠approver, idempotent via status).
             roll.unit_cost += per_unit (additive); roll.landed_cost_total += alloc;
             roll.landed_cost_refs += voucher_number.
Pay:         cash_transaction(out, ref_type=landed_cost) (opsional, setelah applied).
⚠️ JANGAN BUAT: landed_costs, import_costs, freight_vouchers, biaya_impor, hpp_adjustments
```

### tax_invoices_in  [Fase 5.5 P0-3 IMPLEMENTED — Faktur Pajak Masukan / Input VAT]
```
Collection:  tax_invoices_in   Prefix: fpm_   (No. internal FPM-NNNNN)
Router:      routers/input_tax.py · Service: services/input_tax_service.py
Schema:      schemas.py → InputTaxInvoiceCreate, InputTaxInvoiceCancel
Component:   InputTaxView.jsx (Pembelian → Faktur Pajak Masukan) + InputTaxCreateModal.jsx
Status:      recorded → cancelled
Sumber:      Vendor Bill (status posted|paid, ppn_amount>0). DPP/PPN/supplier disalin dari bill.
Key Fields:
  id, number (FPM-NNNNN), nsfp (NSFP supplier), nsfp_digits (dedupe key), kode_transaksi,
  status (recorded|cancelled), faktur_date, period (YYYY-MM),
  vendor_bill_id, bill_number, supplier_invoice_no, po_id, po_number,
  supplier_id, supplier_name, supplier_npwp, entity_id,
  dpp, ppn_rate, ppn_mode, ppn_amount, grand_total,
  notes, timeline[], cancel_reason, cancelled_by, cancelled_at,
  created_by, created_by_id, created_at, updated_at
Dedupe:      NSFP (digit-only) unik di antara faktur status=recorded → 409 bila ganda.
             1 Vendor Bill → max 1 faktur masukan aktif (vendor_bills.input_faktur_status).
Endpoints:   GET/POST /input-tax-invoices · GET /input-tax-invoices/{id} ·
             GET /input-tax-invoices/eligible-bills · POST /input-tax-invoices/{id}/cancel ·
             GET /tax/vat-summary?period=YYYY-MM (Rekap PPN Masukan vs Keluaran)
Rekap PPN:   /tax/vat-summary → keluaran (tax_invoices, status≠batal) vs masukan
             (tax_invoices_in, status=recorded) per period; net = keluaran−masukan →
             >0 kurang_bayar (setor), <0 lebih_bayar (kredit), =0 nihil.
Efek:        create → vendor_bills.input_faktur_id/number/status='recorded'/nsfp.
             cancel → unset flag bill (eligible lagi), NSFP bisa dipakai ulang.
⚠️ JANGAN BUAT: faktur_masukan, input_vat, ppn_masukan, vat_in, purchase_tax_invoices
```

### rfqs  [Fase 6.1 P1 IMPLEMENTED — RFQ / Quotation (sourcing)]
```
Collection:  rfqs   Prefix: rfq_   (No. RFQ-NNNNN)
Router:      routers/rfq.py · Service: services/rfq_service.py
Schema:      schemas.py → RFQCreate, RFQItemInput, RFQQuoteSubmit, RFQQuoteLine, RFQAward, RFQLineAward, RFQDecision
Component:   RFQView.jsx (Pembelian → RFQ / Quotation) + RFQCreateModal.jsx + RFQDetailPanel.jsx
Status:      draft → open → awarded | cancelled
Sumber:      PR approved (tarik item) | manual (pilih produk). Undang N supplier.
Key Fields:
  id, rfq_number (RFQ-NNNNN), title, entity_id, source ("manual"|"pr"), pr_id, pr_number,
  warehouse_id, warehouse_name, status, needed_by_date, due_date, notes,
  items[] { line_id, product_id, sku, product_name, quantity, unit, note },
  suppliers[] { supplier_id, supplier_name, quote_status ("pending"|"quoted"), quoted_at,
                valid_until, lead_time_days, note, lines[]{line_id,price,available,note}, total },
  award { mode ("full"|"line"), full_supplier_id, line_awards[]{line_id,supplier_id,price},
          po_ids[], po_numbers[], awarded_by, awarded_at },
  timeline[], created_by, created_by_id, created_at, updated_at
Endpoints:   GET/POST /rfqs · GET /rfqs/{id} · GET /rfqs/{id}/compare ·
             POST /rfqs/{id}/send · POST /rfqs/{id}/quote · POST /rfqs/{id}/award ·
             POST /rfqs/{id}/cancel
Compare:     matriks item×supplier + lowest_per_line + total/supplier + recommended_full +
             recommended_line_awards (harga termurah per baris).
Award:       FULL (1 supplier → 1 PO) | LINE (split → 1 PO per supplier). Reuse pricing P0-1
             (compute_order_pricing) + approval threshold + inbound tasks. PO.source_rfq_id/number.
             Upsert supplier_price_lists dari harga pemenang (source=rfq_award, min_qty=0).
             Bila pr_id → PR.status='converted', po_id=PO pertama.
⚠️ JANGAN BUAT: quotations, tenders, bid_requests, penawaran, request_for_quote
```

### document_templates
```
Collection:  document_templates
Router:      routers/documents.py
Schema:      schemas.py → TemplatePayload
Component:   DocumentsView.jsx, AdminView.jsx (tab Templates)
document_type: surat_jalan | invoice
Key Fields:
  id, document_type, name, header, footer, columns, logo_url,
  paper_size, orientation, margin_mm, signature_left, signature_right,
  section_order, status, created_by, created_at

⚠️ JANGAN BUAT: templates, print_templates, doc_config
```

### generated_documents
```
Collection:  generated_documents
Router:      routers/documents.py
Schema:      schemas.py → DocumentGenerate
Key Fields:
  id, document_type, source_id (order_id atau po_id),
  html_content, generated_by, generated_at

⚠️ Dokumen disimpan sebagai HTML string untuk print
```

### permission_settings
```
Collection:  permission_settings
Router:      routers/admin.py
Schema:      schemas.py → PermissionUpdate
Component:   AdminView.jsx (tab Permissions)
Struktur:    {id: "default", matrix: {role: {module: [actions]}}}

⚠️ Hanya ADA 1 document dengan id="default"
⚠️ Fallback: DEFAULT_PERMISSIONS dari permissions_config.py
```

### audit_logs
```
Collection:  audit_logs
Router:      routers/audit.py (read-only list)
Ditulis:     dependencies.py → audit() helper
Component:   AdminView.jsx (tab Audit)
Key Fields:
  id, actor (user name), role, action, entity_type, entity_id,
  before, after, reason, timestamp

⚠️ APPEND-ONLY — tidak pernah update atau delete
⚠️ Gunakan audit() helper dari dependencies.py, BUKAN insert langsung
```

### user_onboarding
```
Collection:  user_onboarding
Router:      routers/onboarding.py
Component:   OnboardingPanel.jsx
Key Fields:
  id (= user_id), tasks: [{id, title, completed, completed_at}]

⚠️ Satu document per user
```

---

<!-- Discovery module (koleksi discovery_sessions/answers/attachments) dihapus 2026-06-17 — fitur assessment online-form. -->



---

## 🚨 FORBIDDEN — NAMA YANG PERNAH MENYEBABKAN DUPLIKAT

Jangan pernah buat collection atau schema dengan nama berikut
(karena sudah ada atau sudah pernah jadi sumber duplikat):

```
❌ items           → gunakan products
❌ goods           → gunakan products
❌ materials       → gunakan products
❌ accessories     → gunakan products
❌ kain            → gunakan products
❌ stock           → gunakan inventory_balances
❌ stok            → gunakan inventory_balances
❌ stock_levels    → gunakan inventory_balances
❌ orders          → gunakan sales_orders
❌ customer_orders → gunakan sales_orders
❌ penjualan       → gunakan sales_orders
❌ inbound_tasks   → gunakan wms_tasks (flow_type=inbound)
❌ outbound_tasks  → gunakan wms_tasks (flow_type=outbound)
❌ receiving_tasks → gunakan wms_tasks (flow_type=inbound)
❌ transfers       → gunakan warehouse_transfers
❌ stock_transfer  → gunakan warehouse_transfers
❌ po              → gunakan purchase_orders
❌ pembelian       → gunakan purchase_orders
❌ bills           → gunakan invoices
❌ tagihan         → gunakan invoices
❌ templates       → gunakan document_templates
❌ staff           → gunakan users
❌ operator        → gunakan users
❌ gudang          → gunakan warehouses
❌ depot           → gunakan warehouses
```

---

## 📐 BASE SCHEMA TEMPLATE

Setiap document baru WAJIB punya field-field ini:
```python
{
    "id":           new_id("prefix"),   # dari core_utils.new_id()
    "created_at":   now_iso(),           # dari core_utils.now_iso()
    "updated_at":   now_iso(),
    "created_by":   user["id"],          # dari token auth
    "created_by_name": user["name"],    # snapshot
    # ... business fields
}
```

Prefix ID yang sudah digunakan:
```
user_   → users
sess_   → sessions
prod_   → products
cust_   → customers
wh_     → warehouses
uom_    → uoms
so_     → sales_orders
bal_    → inventory_balances
roll_   → inventory_rolls            [Fase 0.5 IMPLEMENTED]
mov_    → inventory_movements
wms_    → wms_tasks
trf_    → warehouse_transfers
cc_     → cycle_count_sessions
po_     → purchase_orders
tmpl_   → document_templates
doc_    → generated_documents
inv_    → invoices
audit_  → audit_logs
addr_   → customer addresses (embedded)
ent_    → business_entities         [Fase 0 IMPLEMENTED]
ntf_    → notifications             [Fase 0 IMPLEMENTED]
set_    → system_settings           [Fase 1A IMPLEMENTED]
pterm_  → payment_terms             [Fase 1A IMPLEMENTED]
aprule_ → approval_rules            [Fase 1A IMPLEMENTED]
```
> Prefix PLANNED (lihat bagian PLANNED ENTITIES): `pra_` price_approvals (= "special price"),
> `sord_` special_orders, `bank_` bank_accounts, `cpl_` customer_price_lists, `sret_` sales_returns, `fkt_` tax_invoices.

---

## 🆕 PLANNED ENTITIES (IA KN_14 — belum diimplementasi)

> **Sumber:** `KN_14_INFORMATION_ARCHITECTURE.md`. Entitas berikut **direncanakan**
> per fase roadmap. Didaftarkan di sini lebih dulu (Navigation-First + SSOT) agar
> tidak terjadi duplikat/drift saat coding. Status: **[PLANNED]** — belum ada di DB/kode.
> Saat diimplementasi: pindahkan ke bagian DETAIL di atas + daftarkan ke `verify_contract.py`.

### Lapis Fundamental — Multi-Entity  (✅ IMPLEMENTED Fase 0)
```
Collection: business_entities            Prefix: ent_    Fase 0  [IMPLEMENTED]
  id, legal_name, short_name, type(PT|CV), npwp, address, city,
  default_tax_mode(ppn|non_ppn), doc_prefix, logo_url, status, created_at, updated_at
⚠️ entity_id (FK) ditambahkan ke koleksi TRANSAKSI (scoped): sales_orders, invoices,
   tax_invoices, purchase_orders, cash_transactions, journal_entries, bank_accounts,
   tax_records, fiscal_periods, price_approvals, sales_returns, special_orders.
   Master SHARED (products, warehouses, uoms, document_templates) TIDAK wajib entity_id.
   customers & suppliers = default scoped (opsi shared). JANGAN buat: tenant, company.
```

### Platform  (✅ `notifications` IMPLEMENTED Fase 0)
```
Collection: notifications    Prefix: ntf_    Fase 0  [IMPLEMENTED]
  id, entity_id, recipient_role|recipient_user, type, title, body,
  link(navigation_target), severity(info|warning|critical), ref, read, read_at, created_at
⚠️ JANGAN buat: notif, alerts (gunakan notifications)
```

### Sales (Fase 1)
```
customer_price_lists   Prefix: cpl_   — harga khusus per customer/kategori/produk + periode [DEPRIORITAS: harga manual/nego]
price_approvals        Prefix: pra_   — special price (negosiasi harga + upload bukti + approval Finance/Admin)
Collection:  sales_returns   Prefix: sret_  — retur/tukar/Barang Sisa (BS) cacat + dampak stok
Collection:  special_orders  Prefix: sord_  — Special Order (SKU belum ada → MD + Purchasing) + estimasi
tax_invoices           Prefix: fkt_   — Faktur Pajak (nomor, DPP, PPN, status) per entitas
sales_targets          Prefix: starg_ — target sales per salesperson per periode (penjualan/pencairan/customer baru) [KN_17]
sales_incentives       Prefix: sinc_  — komisi/bonus per sales per periode (basis sales|pencairan|tiered) [KN_17]
campaigns              Prefix: camp_  — product focus / campaign + target per sales (advanced) [KN_17]
collection_followups   Prefix: cfu_   — jejak follow-up penagihan jatuh tempo [KN_17 S39]
credit_overrides       Prefix: cro_   — bypass blokir kredit via approval Finance + bukti (case-by-case) [KN_17 S37]
⚠️ KPI salesperson = DERIVED (dari sales_orders/invoices/payments/customers), BUKAN koleksi.
⚠️ JANGAN buat: discounts, faktur, returns_generic, salespersons (pakai users role=sales), leads/crm_* (fase lanjut)
```

### Procurement (Fase 3)
```
suppliers          Prefix: sup_    — master pemasok (nama, npwp, kontak, jenis barang, entity_id?)
bom_printing       Prefix: bom_    — BOM benang + bahan printing per produk/order
cash_transactions  Prefix: cash_   — kas kecil per entitas + kas besar gabungan
⚠️ purchase_orders.supplier_name (string) → refactor jadi FK suppliers.id
⚠️ Approval pembelian = workflow state + attachment pada purchase_orders (bukan koleksi baru)
⚠️ JANGAN buat: vendor, procurement, kas (pakai suppliers/cash_transactions)
```

### Finance (Fase 4)
```
chart_of_accounts  Prefix: coa_    — COA fleksibel (Aktiva/Hutang/Modal/Pendapatan/Beban)
journal_entries    Prefix: je_     — jurnal/GL double-entry (auto-posting dari invoice/kas)
bank_accounts      Prefix: bank_   — rekening per entitas (MULTI-rekening/entitas), entity_id,
                                    bank_name, account_no, account_name, branch,
                                    designation(ppn|non_ppn|both), is_active, is_default
                                    ⚠️ SO + destination_bank_account_id (dipilih saat buat SO; KN_16 §8B.3).
                                       Invoice PPN→akun ppn/both; non-PPN→non_ppn/both.
tax_records        Prefix: tax_    — rekap PPN/PPH (export Coretax = fase lanjut)
fiscal_periods     Prefix: fper_   — periode + closing (28/30/31) + lock
⚠️ AR aging/Outstanding = DERIVED dari invoices + credit_limit; denda 1–3% pada invoices
⚠️ JANGAN buat: ledger, accounts, gl (pakai journal_entries/chart_of_accounts/bank_accounts)
```

### Warehouse & RFID (Fase 5)
```
inventory_classifications Prefix: icls_ — klasifikasi fast/slow/dead (>3 bln) + analitik tren
warehouse_locations   Prefix: loc_  — master lokasi RFID hierarki (Zone→Rack→Level→Bin)
rfid_tags             Prefix: tag_  — registrasi tag ↔ item/lot/roll
rfid_devices          Prefix: dev_  — printer/reader/handheld/gate/server
rfid_events           Prefix: evt_  — log scan/gate (green/red) + alarm → notifications
⚠️ warehouses: tambah level "Level" (Zone→Rack→Level→Bin) — enhancement embedded
⚠️ JANGAN buat: rfid (terlalu generik), locations, tags_generic
```

### HRD (Fase 2)
```
hr_employees       Prefix: emp_    — data karyawan, jabatan, divisi, entity_id
attendance_records Prefix: att_    — absensi (import fingerprint CSV/API), telat, durasi
kpi_records        Prefix: kpi_    — KPI design (jumlah & kualitas desain)
design_gallery     Prefix: dsg_    — gallery motif kain + AI Gemini auto-tag (Emergent LLM key)
⚠️ employees/employee/staff/karyawan = TERLARANG (alias→users di verify_contract.py).
   Domain HRD WAJIB pakai 'hr_employees' (karyawan ≠ user login/auth).
```

---

**Versi:** 1.1  
**Dibuat:** 28 Mei 2026 · **Update IA:** 15 Jun 2026 (planned entities KN_14)  
**Update wajib:** Setiap kali ada entitas baru ditambahkan  
**IA induk:** `KN_14_INFORMATION_ARCHITECTURE.md` (SSOT triangle: KN_14 ⇄ KN_13 ⇄ ENTITY_REGISTRY)
