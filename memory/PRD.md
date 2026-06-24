# PRD — Product Requirements Document
## Kain Nusantara WMS/ERP Platform

**Versi:** 1.0  
**Tanggal Mulai:** November 2025  
**Last Updated:** 22 Jun 2026 (F1a Pricelist per-Entitas + Dashboard Konsolidasi SELESAI)  
**Status:** Active Development

> ### 🔄 PROGRES MULTI-ENTITY (F0) — ✅ SELESAI 100%
> - ✅ F0-A Entity master & identity (21 Jun 2026).
> - ✅ F0-B Context propagation & isolasi (21 Jun) — 13 endpoint komersial, iter_51 91/91.
> - ✅ F0-C Migrasi + Gate + scoping operasional (22 Jun) — wms/shipments/inventory, GATE 0 FAIL.
> - ✅ F0-D Penomoran per-entitas (22 Jun) — `CODE/PREFIX-NNNNN` via `number_sequences` atomik.
> - ✅ F0-E Buku GL terpisah per PT + PKP per-entitas (22 Jun).
> - ✅ F0-F Provisioning "Add New Entity" (22 Jun). testing_agent iter_52 **64/64 PASS**.
> - ➕ Enhancement: **EntityBadge** (pill warna per PT) di Orders/Suppliers/Vendor-Bills.
>
> ### 🔄 PROGRES F1 (PRICELIST & VARIAN)
> - ✅ **F1a Pricelist per-Entitas** (22 Jun 2026) — `entity_prices` (SCOPED), harga jual per-PT
>   dengan **histori + tanggal efektif** (valid_from/valid_until), resolver `pricelist_service`
>   (fallback ke `products.price` global). Terintegrasi di `POST /api/sales-orders` (harga item ikut
>   entitas) & `GET /api/products` (global_price + price_source). UI **"Pricelist per-PT"** (grid +
>   Set Harga modal + Riwayat + Export/Import CSV). RBAC modul `pricelist` (admin/manager manage,
>   sales view). testing_agent iter_53 **16/16 PASS**. Gate scoping LULUS (entity_prices SCOPED).
> - ✅ **F1b Varian Produk (Template → Variant)** (22 Jun 2026, ADDITIVE/non-destruktif) —
>   `product_templates` (SHARED) + `products.template_id`/`variant_attrs`. `product_template_service`
>   (generate varian CARTESIAN dari axis Warna×Grade×Lebar → SKU otomatis, idempoten; assign/detach;
>   delete non-destruktif = lepas tautan, produk tetap utuh). Router `/api/product-templates/*`. UI
>   **"Template & Varian"** (kelola template + axes editor + Generate massal + Assign). Unique index
>   `products.sku`. testing_agent iter_54 **20/20 PASS + FE smoke**.
> - ➕ Enhancement: **Dashboard Konsolidasi Grup vs Per-PT** (`GET /api/gl/consolidation`,
>   `ConsolidationDashboard.jsx`) — toggle ringkasan keuangan gabungan vs per-PT memakai buku F0-E.
> - ⬜ Berikutnya: **F2 (Multi-bucket Stock: WIP/In-transit + Pending SO/Hold)** → F3 (MTO/aftersales)
>   → F4 (POS mobile) → F5 (ekspedisi/omnichannel).

---

## 1. PRODUCT VISION

### Mission Statement
Membangun ERP + WMS platform modern untuk industri tekstil tradisional Indonesia (Batik, Tenun, Songket, Lurik, Ulos) yang:
- AI-assisted untuk insights & automation
- RFID-ready untuk real-time tracking
- Integration-friendly untuk third-party systems
- Menjadi alternatif modern dari Microsoft Business Central

### Target Users
- **Kain Nusantara Internal:** Warehouse operators, sales team, managers, admins
- **Future (SaaS):** Textile companies di Indonesia (SME → Enterprise)

---

## 2. FEATURE INVENTORY (What's Built)

### 2.1 Core Authentication & Identity ✅
**Status:** COMPLETED  
**Delivery:** November 2025

**Features:**
- Login/logout dengan role-based access (admin, sales, manager, warehouse)
- Demo accounts untuk setiap role
- Session management dengan token
- Permission matrix editable dari Admin Panel
- Audit trail terintegrasi

**Tech Stack:**
- Backend: FastAPI + JWT + Bcrypt
- Frontend: React 19 + Axios

**Gaps Known:**
- No JWT refresh token
- No MFA (multi-factor authentication)
- No password reset flow
- No SSO/OAuth integration

---

### 2.2 Master Data Management ✅
**Status:** COMPLETED  
**Delivery:** November 2025

**Entities:**
1. **Products** — SKU, name, category, variant, color, motif, grade, supplier, price, UOM
2. **Customers** — Name, contact, addresses, type (Retailer/Wholesaler/Boutique)
3. **Warehouses** — Multi-warehouse dengan hierarchy (Zone → Rack → Bin)
4. **UOMs** — Unit of Measure (meter, yard, roll, pcs) dengan konversi
5. **Users** — User management dengan role assignment
6. **Document Templates** — Surat Jalan & Invoice templates
7. **Permissions** — Role-based permission matrix

**Features:**
- Full CRUD untuk semua entities
- Import/export CSV (products, customers, warehouses)
- Soft-delete via status `inactive`
- Toggle form UI untuk space efficiency

**Tech Stack:**
- Backend: FastAPI routers (admin.py, products.py, customers.py, warehouses.py, uoms.py, users.py)
- Frontend: React forms dengan Shadcn UI
- Database: MongoDB collections

**Gaps Known:**
- No bulk edit
- No product image upload (URL only)
- No product bundling
- No supplier master (string only)
- No customer segmentation
- No product version history

---

### 2.3 Sales POS & Order Creation ✅
**Status:** COMPLETED  
**Delivery:** December 2025

**Features:**
- Visual product catalog dengan stock real-time
- Multi-warehouse auto-allocation (greedy algorithm)
- Customer selection (compact dropdown)
- Cart management dengan quantity adjustment
- Automatic stock reservation (3 days default)
- Order workflow: `reserved → waiting_approval → approved → confirmed → dispatched → done`
- Manual release reservation
- Search produk + filter kategori

**Tech Stack:**
- Backend: sales_orders.py router
- Frontend: SalesPortal, CartPanel, ProductCard components
- Database: sales_orders, inventory_balances collections

**Gaps Known:**
- No quotation/proposal flow
- No price negotiation field
- No customer credit check
- No payment terms configuration
- No order draft auto-save
- No multi-currency
- No backorder support

---

### 2.4 Order Management & Approval ✅
**Status:** COMPLETED  
**Delivery:** December 2025

**Features:**
- Dashboard tab dengan analytics (revenue, top customers, status distribution)
- Order list dengan filter by status
- Status timeline visual
- Search by order/customer/product
- Stats summary (Total / Reserved / Confirmed / Done / Cancelled)
- Manual reservation release untuk stuck orders
- Reservation expiry (3 days) untuk anti-hoarding

**Tech Stack:**
- Backend: sales_orders.py endpoints
- Frontend: OrdersView, OrderDashboard.jsx
- Charts: Recharts

**Gaps Known:**
- No multi-step approval workflow
- No order modification post-approval
- No partial cancellation
- No automated reservation expiry job
- No notification system
- No SLA tracker
- No export to Excel/PDF

---

### 2.5 Warehouse Management System (WMS) ✅
**Status:** COMPLETED (MVP)  
**Delivery:** January 2026

#### 2.5.1 Inventory / Stok Tab
**Features:**
- KPI cards: Total On Hand, Available, Reserved, Stok Rendah
- Search by SKU/nama/gudang
- Warehouse filter pills
- Tab Stok vs Ledger (movement history)
- Reserved details panel
- Tambah Stok manual (adjustment)

**Gaps Known:**
- No re-order point / safety stock alert
- No ABC/XYZ classification
- No inventory aging report
- No stock valuation method (FIFO/LIFO/Weighted Average)
- No bin-level inventory

#### 2.5.2 Inbound Receiving
**Features:**
- 2-panel UI: task list + scan panel
- Status filter pills (Waiting / Receiving / QC / Escalated)
- Barcode/QR scan via camera atau input
- Multi-scan per task
- Auto-advance status: `waiting_goods → receiving → qc_check`
- Escalation flow (warehouse → manager → resolve)
- Surat tanda terima auto-generate

**Gaps Known:**
- No QC checklist form
- No return-to-supplier flow
- No put-away suggestion
- No supplier rating
- No PO match validation

#### 2.5.3 Outbound Picking
**Features:**
- Mirror struktur inbound (2-panel)
- Auto-create task saat order confirmed
- Multi-scan dengan partial pick support
- Status: `created → picking → packing → staging → dispatched`
- Dispatch button hanya muncul saat picked_qty ≥ quantity
- Surat Jalan auto-generate

**Gaps Known:**
- No wave/batch picking
- No pick optimization
- No packing material tracking
- No shipment consolidation
- No carrier integration
- No proof of delivery (POD)

#### 2.5.4 Transfer Antar Gudang
**Features:**
- Workflow: `draft → waiting_approval → approved → in_transit → received`
- Approval/reject dengan alasan
- Linked ke inventory movements

**Gaps Known:**
- No transfer cost allocation
- No estimated arrival date
- No in-transit qty visibility

#### 2.5.5 Cycle Count
**Features:**
- Sesi cycle count dengan status flow
- Submit → approve/reject untuk variance
- Approval generate adjustment movement

**Gaps Known:**
- No blind count
- No cycle count schedule automation
- No variance threshold setting
- No counting by zone/bin

---

### 2.6 Purchasing ✅
**Status:** MVP COMPLETED  
**Delivery:** January 2026

**Features:**
- Purchase Order multi-item
- Auto-create inbound task saat PO created
- Status: `pending → receiving → completed / partial / cancelled`

**Gaps Known:**
- No supplier master (string only)
- No RFQ (Request for Quotation)
- No PO approval workflow
- No payment to supplier tracking
- No PO change order
- No 3-way matching (PO ↔ Receipt ↔ Invoice)

---

### 2.7 Invoicing & Payment ✅
**Status:** SIMULATED (Not Production Ready)  
**Delivery:** January 2026

**Features:**
- Auto-generate invoice saat order confirmed
- Invoice number unik per tahun
- Payment status: `pending / paid`
- Simulate payment endpoint

**Gaps Known:**
- Payment SIMULATED only (no real gateway)
- No partial payment
- No payment method selection
- No invoice email automation
- No aging receivable report
- No credit note / refund flow
- No tax (PPN 11%) configuration

---

### 2.8 Documents & Print Center ✅
**Status:** COMPLETED (HTML Print)  
**Delivery:** February 2026

**Features:**
- Template engine untuk Surat Jalan & Invoice
- Field customization (header, footer, columns)
- Preview before print
- Label printer untuk produk (barcode + SKU + nama)
- Print Center dengan batch label generation

**Gaps Known:**
- No PDF generation native (HTML print only)
- No watermark (DRAFT, COPY, PAID)
- No multi-language
- No digital signature
- No document archive/audit trail

---

### 2.9 Reporting & Analytics ✅
**Status:** BASIC COMPLETED  
**Delivery:** February 2026

**Features:**
- 6 report types: stock-aging, reservation-funnel, order-velocity, top-customers, warehouse-utilization, summary
- Dashboard tab dengan timeframe selector (7/30/90 hari)
- Visual progress bar untuk status distribution

**Gaps Known:**
- No custom dashboard per role/user
- No export report to Excel/PDF
- No scheduled reports (email weekly)
- No drill-down interactivity
- No comparative period (this month vs last month)
- No forecasting
- No COGS / profit margin report

---

### 2.10 Smart Guidelines (Onboarding Tour) ✅
**Status:** COMPLETED  
**Delivery:** May 2026

**Features:**
- 7 tour berbeda dengan role-based access filter
- Auto-navigate per step
- Polling target sampai muncul (2.5s timeout)
- Optional steps + center placement untuk info-only
- CSS selector support
- Tooltip viewport clamping
- Highlight tanpa blur (pulse ring animation)

**Tech Stack:**
- Frontend: GuidedTour.jsx component, tourDefinitions.js

**Gaps Known:**
- No interactive practice mode
- No video tooltip option
- No analytics (tour completion tracking)
- No multi-language

---

### 2.11 Escalation Management ✅
**Status:** BASIC COMPLETED  
**Delivery:** January 2026

**Features:**
- Escalation per task (inbound/outbound/transfer)
- Reason + resolution notes
- Linked ke audit log

**Gaps Known:**
- No SLA timer
- No escalation routing logic
- No escalation root cause analytics

---

### 2.12 Audit Trail ✅
**Status:** COMPLETED  
**Delivery:** November 2025

**Features:**
- Setiap aksi tercatat (user, action, resource, timestamp, details)
- Filter & search di Admin > Audit tab
- Immutable (tidak bisa edit/hapus)

**Gaps Known:**
- No retention policy
- No tamper detection (cryptographic hash)
- No export untuk audit eksternal

---

### 2.13 Multi-Entity & Roll-as-SSOT Inventory Ownership ✅
**Status:** COMPLETED (Fase 0 + Fase 0.5 — Session #014–#016)  
**Delivery:** Jun 2026

**Features:**
- `business_entities` collection (ent_ksc / ent_kanda); `entity_id` scoped pada transaksi (SO, PO, customers)
- Master data (products, warehouses, uoms) SHARED antar entitas
- Entity Switcher di TopBar (persist localStorage); filter inventory per entitas
- Notification Center (in-app); generator REAL (low_stock, reservation_expiring, order_approval, order_split) + dedupe
- `inventory_rolls` = SSOT fisik stok: setiap roll punya `owner_entity_id`, `lot`, `status` (available/reserved/committed/damaged)
- `inventory_balances` = proyeksi 3-key (product+warehouse+owner_entity) + 8 bucket (available/reserved/committed/picked/packed/quarantine/blocked/damaged)
- Reservasi SO OWNER-SCOPED di level roll (D3): create→reserved, approve→committed, cancel→available. Konservasi panjang terjaga.
- WMS: kolom Pemilik, tab Rolls, InitialStockForm +Pemilik/Lot/Grade, ProductDetail Ownership Matrix

**Gaps Known:**
- No multi-tenancy isolasi penuh (masih shared DB)
- HPP/unit_cost ditunda Fase 4

---

### 2.14 Configuration Foundation & Consumption ✅
**Status:** COMPLETED (Fase 1A + Fase 1B — Session #017–#018)  
**Delivery:** Jun 2026

**Features (Fase 1A — Config Foundation):**
- `system_settings`, `payment_terms`, `approval_rules` collections + `config_service` (compute_tax, evaluate_approval, effective_settings)
- Admin Panel → Pengaturan tab: edit settings, payment terms, approval rules

**Features (Fase 1B — Config Consumption):**
- PPN otomatis (DPP/PPN/Grand Total, ikut PKP/non-PKP entitas, mode excluded/included) di Sales Order + Invoice + dokumen
- Diskon per-item & per-order (dikontrol toggle settings), term pembayaran dipilih saat buat SO
- Approval SO & PO DINAMIS dari `approval_rules` (role_satisfies; auto-approve di bawah threshold)
- PO inbound task ditunda sampai PO di-approve
- INVARIAN-SAFE: `item.subtotal=price×qty` & `total_amount=Σsubtotal` tetap GROSS; breakdown di field terpisah (INV-DB3 gate)

**Gaps Known:**
- Auto-reservation expiry job belum ada (cron/scheduler)
- Partial payment belum produksi (hanya simulasi)

---

### 2.15 ATP & Fulfillment Modes (Sub-fase 1.4) ✅
**Status:** COMPLETED — READ-ONLY (Session #019)  
**Delivery:** Jun 2026

**Features:**
- `services/fulfillment_service.py`: classifier mode pemenuhan per item SO — waterfall `from_stock → from_incoming(ATP) → inter_company → backorder` (primary_mode by severity)
- `POST /api/sales-orders/preview-allocation` (READ-ONLY, tidak mutasi stok)
- `GET /api/inventory/status-board` (per produk × entitas × gudang + indikator inter-company)
- CartPanel `FulfillmentInfo`: badge mode + ATP/Stok/Incoming/Inter-Co + backorder + penjelasan per item (debounce 350ms)
- Menu "Status Stok" (`InventoryStatusBoard.jsx`): tabel per produk + expand entitas/gudang + metrik + search

**Gaps Known:**
- Preview-allocation READ-ONLY; create_order masih owner-scoped (409 bila stok sendiri kurang)
- Mode inter_company dan backorder INFORMASIONAL di POS (eksekusi butuh sub-fase berikut)

---

### 2.16 Inter-Company Transfer Flow (Sub-fase 1.5) ✅
**Status:** COMPLETED — MUTASI STOK (Session #020)  
**Delivery:** Jun 2026

**Features:**
- `POST /api/transfers/inter-company`: buat transfer antar-entitas (`transfer_kind: inter_entity`) — roll-reserve di entitas sumber, status `pending_approval`
- `POST /api/transfers/{id}/approve` (manager/admin): pindah kepemilikan roll B→E (owner_entity_id dipindah ke dest_entity + rebuild_balance kedua entitas), status `completed`
- `POST /api/transfers/{id}/reject`: lepas reservasi roll sumber, status `rejected`
- `DELETE /api/transfers/{id}`: cancel + lepas reservasi bila masih waiting
- `GET /api/transfers?transfer_kind=inter_entity`: list transfer antar-entitas
- Frontend management: `InterCompanyTransfers.jsx` (list + approve + reject + badge status)
- POS integration: tombol "Minta Transfer dari {entity}" di CartPanel bila mode `inter_company`; badge "Transfer diminta — menunggu approval" setelah request
- Navigation: `interco-transfers` untuk role warehouse/manager/admin

**Test:** `test_reports/iteration_8.json` backend 36/36 (100%). Skenario KSC→Kanda: ownership movement + stock conservation + preview mode changes.

**Gaps Known:**
- create_order TETAP owner-scoped; inter-company transfer TERPISAH dari create_order (user minta transfer dulu, tunggu approval, baru buat SO)
- ✅ Backorder lifecycle — DONE (Sub-fase 1.6, lihat 2.17)

---

### 2.17 Backorder Lifecycle (Sub-fase 1.6) ✅
**Status:** COMPLETED — MUTASI STOK + AUTO-FULFILL (Session ini)
**Delivery:** Jun 2026

**Features:**
- SSOT `roll_service.allocate_and_reserve_rolls(allow_partial)`: reservasi parsial roll (default raise 409 → backward-compatible).
- `POST /api/sales-orders` param `allow_backorder` (opt-in): reservasi stok tersedia + sisa jadi backorder. Status SO baru `waiting_stock`; per item `reserved_qty`/`backorder_qty`; order field `backorders[]` + `has_backorder`.
- **Perbaikan SSOT KRITIS:** `POST /api/inbound/tasks/{id}/complete` (GR) kini membuat `inventory_rolls` (BUKAN `$inc` balance) + `rebuild_balance` → invarian `balance == Σ rolls` tetap utuh.
- `services/backorder_service.auto_fulfill_backorders()`: FIFO + owner-scoped, dipanggil otomatis setelah GR → SO `waiting_stock` ter-reservasi (kembali `reserved` saat terpenuhi penuh).
- cancel/release-reservation/expire_old_reservations menangani `waiting_stock` (lepas roll + clear backorder).
- Invarian gate baru `verify_data_integrity.py` L4-BO (INV-BO-1/2/3).
- Frontend: CartPanel checkbox "Izinkan Backorder"; OrdersView stat Backorder + filter + status pill `waiting_stock`; `OrderDetailPanel.jsx` banner backorder + breakdown per item.

**Test:** `tests/test_backorder_16.py` 7/7 + testing_agent_v3 `test_reports/iteration_9.json` (backend 96% / frontend 100% / data integrity 100% — 0 bug). Gate: integrity 88 PASS/0 FAIL, compliance 57/0/0.

**Gaps Known:**
- Allocation policy R1/R2 configurable belum (Sub-fase 1.7).
- ✅ Approval-with-backorder + decouple status + auto-commit — DONE (Sub-fase 1.6.1).
- Pengiriman parsial FISIK terhadap backorder (Surat Jalan porsi reserved + multi-shipment, hormati `shipment_policy`) — BELUM (follow-up, butuh konfirmasi user).

---

## 3. FEATURE BACKLOG (Prioritized)

### 🔴 CRITICAL (Q2 2026)
1. **Auto-reservation expiry job** (cron hourly)
2. ✅ **Discount field** per item di POS — DONE (Fase 1B, item + order level, settings-gated)
3. ✅ **Tax 11% PPN** configurable di settings — DONE (Fase 1B, ikut PKP/non-PKP entitas, mode excluded/included)
4. **Master data validation** (SKU unique, harga ≥0, email regex)
5. **Order draft auto-save** ke localStorage

> Catatan Fase 1B: konfigurasi (system_settings/payment_terms/approval_rules) kini DIKONSUMSI di
> Sales Order + Invoice (PPN/DPP/grand_total + term pembayaran) dan approval SO/PO dinamis dari
> approval_rules. Sebagian dari #9 (partial payment) juga sebagian tercakup (payment_status pending/partial/paid).

### 🟡 HIGH (Q3 2026)
6. **Supplier Master** sebagai entitas terpisah
7. **QC Form** dengan checklist (defect type, sample count, pass/fail)
8. **Quotation flow** (Sales → Quotation → Order)
9. **Partial payment + payment method**
10. **Safety stock & reorder point** alert
11. **Notification system** (in-app + email)
12. **Export to Excel** untuk Orders, Inventory, Reports

### 🟢 MEDIUM (Q4 2026)
13. **Approval workflow multi-step** (bertingkat)
14. **Aging receivable report**
15. **Carrier integration** (JNE, J&T, Sicepat)
16. **Bulk edit** master data
17. **Drill-down report** interaktivity
18. **JWT refresh token + session timeout**
19. **Password reset via email**
20. **PDF native generation** (weasyprint)

### ⚪ LOW (2027+)
21. **Real-time updates** via WebSocket
22. **Backend test suite** (pytest)
23. **API rate limiting**
24. **Image upload service** (S3-compatible)
25. **Multi-tenancy support**

---

## 4. MODULES ROADMAP (End-to-End ERP)

### Tier 1 — Operational Backbone (2026-2027)
- **Finance & Accounting (GL)** — General Ledger, COA, Trial Balance, Financial Statements
- **Accounts Payable / Receivable (AP/AR)** — Supplier bills, customer invoices, aging reports
- **Logistics / Shipping** — Carrier master, shipment consolidation, POD, route planning
- **Production / Manufacturing** *(opsional)* — BOM, Work Orders, production scheduling

### Tier 2 — Growth Enablers (2027+)
- **CRM** — Lead management, sales pipeline, customer 360°
- **HRIS** — Employee master, attendance, payroll, leave management
- **Business Intelligence (BI)** — Custom dashboards, predictive analytics, forecasting
- **E-Commerce / B2B Portal** — Self-service customer portal, online ordering

### Tier 3 — Strategic (2028+)
- **Supply Chain Optimization** — Demand forecasting (ML), auto-replenishment, supplier scoring
- **Sustainability / ESG Tracking** — Carbon footprint, material origin traceability
- **Document Management System (DMS)** — Upload, tag, version control, e-signature
- **AI Assistant** — Natural language queries, auto-categorization, demand forecasting

---

## 5. TECH STACK

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **Database:** MongoDB (Motor async driver)
- **Auth:** JWT (python-jose) + Bcrypt
- **Cache/Real-time:** Redis (planned, not yet implemented)
- **MQTT:** aiomqtt (RFID integration, planned)
- **Scheduler:** APScheduler (planned)

### Frontend
- **Framework:** React 19
- **Styling:** TailwindCSS + Shadcn/UI
- **State:** Zustand (client state, planned), TanStack Query (server state, planned)
- **Charts:** Recharts (current), Apache ECharts (planned for advanced)
- **Icons:** Lucide React

### Database
- **Primary:** MongoDB
- **Collections:** 25+ (users, products, customers, warehouses, sales_orders, inventory_balances, inventory_movements, purchase_orders, inbound_tasks, outbound_tasks, transfers, cycle_count, invoices, document_templates, permission_settings, audit_logs, etc)

### Infrastructure
- **Backend Server:** Uvicorn (port 8001)
- **Frontend Dev Server:** Webpack Dev Server (port 3000)
- **Deployment:** Kubernetes (current preview environment)

---

## 6. KEY METRICS (Current Baseline)

| Metric | Target | Current Status |
|---|---|---|
| **Order Cycle Time** (created → dispatched) | <3 hari | Manual testing only |
| **Stock Accuracy** (sistem vs fisik) | >95% | Seed data only |
| **Order Fulfillment Rate** | >90% | Not measured |
| **Reservation Expiry Rate** | <5% | Manual expiry (no cron) |
| **User Adoption** | 60% | Demo accounts only |
| **Tour Completion Rate** | 30% | No analytics yet |
| **Page Load Time** (P95) | <2s | Not measured |

---

## 7. KNOWN TECHNICAL DEBT

1. **Seed data inline** di server.py (238 lines) — consider external seed script
2. **No automated tests** — backend & frontend zero test coverage
3. **No CI/CD pipeline** — manual deployment
4. **Simulated payment** — not production-ready
5. **No error monitoring** (Sentry, Rollbar)
6. **No performance monitoring** (APM)
7. **No database backups** automated
8. **No rate limiting** on API endpoints
9. **HTML print only** (no native PDF)
10. **No WebSocket** — polling for real-time updates

---

## 8. COMPLIANCE & GOVERNANCE

### Standards Enforced
- **KN_00:** Agent Quick Start (mandatory entry point)
- **KN_01:** System Overview (business context)
- **KN_02–KN_07, KN_09–KN_11:** standar ASPIRATIF (techstack/security/db/realtime/RFID/API/perf/testing/quality) — **DIHAPUS** (tidak mencerminkan kode nyata). Kontrak NYATA = `memory/ENGINEERING_GUARDRAILS.md` + `FRONTEND_GUARDRAILS.md`.
- **KN_08:** UI/UX Standards (design system)
- **KN_12:** Development Protocols (workflow)
- **KN_13:** Navigation Map (menu structure)

### Quality Gates
- **Gate 1 (Pre-Code):** PRD check, plan check, existing code discovery, nav map check
- **Gate 2 (During Code):** Tech stack patterns, security standards, DB standards, API standards, file size limits
- **Gate 3 (Post-Code):** validate_compliance.py, testing agent, linter clean, screenshot/curl verified, docs updated

---

## 9. CHANGELOG

### v1.3 — 17 Jun 2026 (Cleanup: Discovery module removed + docs trimmed)
- **Modul Discovery (E-Questionnaire / assessment online-form) DIHAPUS TOTAL** atas permintaan user.
  - Backend dihapus: `routers/discovery.py`, `services/discovery_questions.py`, `discovery_pdf.py`, `discovery_attachments.py`; `server.py` import+register dibersihkan.
  - Frontend dihapus: seluruh `features/discovery/` (20 file) + `index.js` disederhanakan (Root = App, tanpa route `/discovery/*`).
  - Gate disinkronkan: `verify_contract.py` (canonical), `health_check.py` (2 cek discovery), `validate_compliance.py` (canonical + prefix `discovery_`).
  - Koleksi `discovery_sessions/answers/attachments` di-drop dari DB + dihapus dari ENTITY_REGISTRY.
  - `reportlab`/`openpyxl` DIPERTAHANKAN (masih dipakai `routers/admin.py`).
- **Dokumen stale dihapus:** `CLEANUP_ANALYSIS.md` (klaim doc "missing" yang kini ada), `FRONTEND_MENU_ANALYSIS.md` (klaim App.js 1684 baris; kini 214), `docs/DISCOVERY_MODULE.md`.
- Dokumen assessment (COMPREHENSIVE_ERP_ASSESSMENT 1–4, EXECUTIVE_SUMMARY_DECK, SYSTEM_ANALYSIS, KN_DEVELOPMENT_PLAN_FROM_ASSESSMENT) DIPERTAHANKAN (keputusan user 2c).

### v1.2 — Session #020 (Sub-fase 1.5 — Inter-Company Transfer Flow DONE)
- **Sub-fase 1.5 LENGKAP (MUTASI)**: Inter-company transfer flow nyata sudah diimplementasikan di repo KN6.
  - Backend: `POST /api/transfers/inter-company` (buat transfer antar entitas, `transfer_kind: inter_entity`, roll-reserve sumber); `POST /api/transfers/{id}/approve` (pindah kepemilikan B→E, rebuild_balance kedua entitas, status completed); `POST /api/transfers/{id}/reject` (lepas reservasi, status rejected); `DELETE /api/transfers/{id}` (cancel + lepas reservasi).
  - Frontend: `features/transfers/InterCompanyTransfers.jsx` (265 baris) management page (list+approve+reject); `SalesPortal.jsx handleRequestTransfer`; CartPanel tombol "Minta Transfer dari {entity}".
  - Navigation: route `interco-transfers` untuk warehouse/manager/admin.
  - Test: `test_reports/iteration_8.json` backend 36/36 (100%). Gates: data_integrity 85/0/0, health 22/0, sweep 0×5xx.
- Session ini: import repo KN6 ke env baru, verifikasi sistem, baca semua dokumen, update dokumentasi.

### v1.2 — 15 Jun 2026 (Repo Import KN4 + Technical Debt Paydown)
- Repo KN4 di-import ke `/app` (preserve `.env`); backend dep `reportlab`/`openpyxl` di-install (fix import discovery).
- **Frontend modularization:** monster files dipecah — InventoryStockView 503→216, TransferManagement 548→266 (+ colocated sub-components); DiscoveryAdmin 485→192; QuestionField 438→171; tourDefinitions 341→55; App.css 527→9; LoginScreen di-extract dari CoreWidgets.
- **UX loading/empty migration:** `ux_audit` **15 ERROR → 0** (loading/empty states di OrdersView, OrderDashboard, SalesPortal, DocumentsView, AdminView, ProductDetail).
- **Guardrail/doc sync:** ENTITY_REGISTRY discovery_* detail; validate_compliance known_collections+valid_prefixes; ux_audit FORM_HINTS.
- Gates: validate_compliance **54/0/0**, semua data/contract gates hijau. Regression test: backend 19/19, frontend 0 bug.
- Sisa backlog non-error: ux_audit 19 WARN (W1 tabular-nums, W2 native select).

### v1.1 — 29 Mei 2026 (Discovery E-Questionnaire v2.1)
- Modul Discovery: opsi **"Lainnya" (isian bebas)** pada pertanyaan single/multi choice
- Modul Discovery: **kolom Catatan** (note) per pertanyaan — tampil di Summary + PDF
- Progress dibuat **value-aware** (catatan saja tidak menghitung progress)
- Tested: backend curl (save/progress/PDF) + frontend (client, summary) — semua pass

### v1.8 — Session #027 (Fix dependency WMS scanner + input numerik)
- **WMS scanner `@zxing/browser` FIXED**: `@zxing/browser@0.1.5` + `@zxing/library@0.21.3` (pasangan kompatibel Node 20; versi 0.22 butuh Node 24). `BrowserMultiFormatReader` kini ter-resolve; 0 "Module not found". File terdampak: `OutboundScanInterface`, `InboundScanInterface`, `ScannerTaskPanel` (dynamic import).
- **Form produk**: input numerik (price, harga_pokok, gramasi, lebar) → `type="number"` (UX mobile).
- **Craco**: `ignoreWarnings` untuk redam warning benign "Failed to parse source map" dari @zxing (dev-only). Compile: 0 error, source-map warning 0.

### v1.7 — Session #027 (1.13 polish — validasi konversi + transparansi kg/m)
- **Validasi UI editor konversi** (`AdminView.validateConversions`): blokir simpan bila baris konversi punya unit "Dari"/"Ke" kosong, faktor ≤ 0, atau from==to; pesan error inline Indonesia (`admin-product-error`), tidak ada create/update saat invalid.
- **Transparansi catch-weight**: baris info `admin-product-kgm-info` menampilkan kg/m terhitung ("1 meter ≈ 0.300 kg") saat gramasi & lebar terisi, atau hint untuk mengisinya.
- **Verified**: testing_agent iteration_12 (100% 6/6, tanpa pembuatan data).
- ⚠️ Pre-existing (di luar lingkup): `@zxing/browser` di-import 3 file WMS scanner tapi belum ada di package.json — fitur scanner WMS akan gagal sampai `yarn add @zxing/browser`. Tidak memengaruhi Admin/POS.

### v1.6 — Session #027 (1.13 lanjutan — UI editor uom_conversions + kg/catch-weight)
- **Master Data Produk (Admin > Product)**: ditambah field **Lebar (meter)**, **editor `uom_conversions`** (tambah/hapus baris from/to/factor), dan **mode EDIT** (klik Edit di list produk → form ter-isi termasuk uom_conversions → Update via PATCH; tombol Batal Edit). Backend CRUD produk sudah ada sebelumnya.
- **kg / catch-weight**: ProductPayload + update_product ditambah `lebar`. Engine `uom_service._catch_weight`: kg ↔ base via `kg/meter = gramasi(gsm) × lebar(m) / 1000` (butuh gramasi & lebar > 0). FE `utils/uom.js`: unit `kg` muncul otomatis bila gramasi & lebar terisi; harga di-skala (price/meter ÷ kg-per-meter).
- Seed demo: `prod_batik_mega` di-set gramasi=200, lebar=1.5 (kg/m=0.3) via `sync_product_uom_examples` (idempotent).
- **Verified**: unit test 12 pass (incl. kg), curl E2E (3 kg → base 10 m, price/kg 616.667, subtotal ≈ 1.850.000), testing_agent iteration_11 (100% 5/5 — editor + edit-mode + kg cart). Gates: data_integrity 96 PASS/0 FAIL, api_contract OK, ux_audit 0/0, compliance 0 FAIL.

### v1.5 — Session #027 (Sub-fase 1.13 — UOM Conversion Engine + 1.10 closed)
- **Sub-fase 1.10 (pengiriman parsial fisik): DITUTUP.** Sudah diimplementasi di Sub-fase 1.8 (dispatch parsial UI, record `shipments` + No. Surat Jalan SJ-#####, multi-shipment tracking, status SO terderivasi). Keputusan user: partial shipment TETAP DIPERBOLEHKAN (tanpa enforcement `shipment_policy`).
- **Sub-fase 1.13 — UOM Conversion Engine (backend + POS selling): SELESAI & terverifikasi.**
  - Engine baru `services/uom_service.py` (pure-fn): `convert/to_base/from_base`. Resolusi: unit sama → FIXED (uoms.factor_to_base + kanonik) → VARIABLE (`product.uom_conversions`) → 1-hop via base → else 400.
  - Units: meter(base,1.0), yard(0.9144), cm(0.01), inch(0.0254) FIXED + roll→meter VARIABLE per produk. (kg/catch-weight DITUNDA — butuh field lebar.)
  - `uoms` ditambah `factor_to_base`; `sync_uom_factors()` + `sync_product_uom_examples()` (batik roll=50m) idempotent saat startup.
  - `create_order`: hitung `base_quantity` via engine; **reservasi/alokasi/backorder pakai base_quantity**; harga di-skala (price/meter × faktor, presisi tinggi) → keputusan 1a. Preview-allocation & preview-lots ikut konversi ke base.
  - GR/inbound: roll length disimpan dalam base unit (konversi bila unit≠base).
  - Invarian `verify_data_integrity` INV-BO-1 → bandingkan `base_quantity`. Unit test `tests/test_uom_1_13.py` (9 pass).
  - **FE POS cart**: dropdown unit per baris (`cart-item-unit-select-<id>`) + tampil ekuivalen base ("≈ 9,14 meter (base) · Rp.../yard"); harga preview di-skala. Util `utils/uom.js` (mirror engine, display-only).
  - **Verified**: curl E2E (10 yard→base 9.14/price 169.164; 1 roll→base 50; 5 meter backward-compat) + testing_agent iteration_10 (100% 6/6 cart flow). Gates: data_integrity 96 PASS, api_contract OK, ux_audit 0/0, compliance 0 FAIL.
  - **DEFERRED**: editor `uom_conversions` per produk di UI (belum ada layar Master Data produk untuk create/edit — konversi saat ini via seed/API).

### v1.4 — Session #027 (KNSelect Searchable/Typeahead Enhancement)
- `KNSelect.jsx` kini auto-render **combobox searchable** (Popover + cmdk Command) saat `options.length >= 6` atau prop `searchable=true`; daftar pendek tetap pakai Radix Select (tanpa regresi). API pemanggil tidak berubah (nol caller diubah).
- Pencarian inline berfungsi pada dropdown Customer (6 opsi) & Produk (8 opsi). Opsi kosong tetap mengirim `""` ke parent. Testid: trigger=`<id>`, search=`<id>-search`, popover=`<id>-popover`, opsi=`<id>-option-<value|empty>`.
- Suppressor benign "ResizeObserver loop" overlay dev ditambahkan di `index.js` (tak berdampak prod).
- **Verified (testing_agent iteration_9): 100% frontend** — filter & select jalan, opsi empty→"", select kecil tanpa regresi, 0 console.error, 0 blank screen.

### v1.3 — Session #027 (KNSelect Empty-Value Crash Fix + RCA)
- **ROOT CAUSE (validated handoff):** Radix UI `@radix-ui/react-select` v2.2.2 has a hard runtime guard — `<Select.Item>` throws `"A <Select.Item /> must have a value prop that is not an empty string."`. A prior session migrated ~20 files from native `<select>` (where `<option value="">` is valid) to `<KNSelect>` (Radix). Callers passing `{ value: "", label: "-- Pilih --" }` crashed those pages to a blank screen. Confirmed via Radix source line 892.
- **FIX:** `KNSelect.jsx` now maps `"" ↔ "__empty__"` sentinel internally (value + options inbound, reversed on `onValueChange`). Fully backward-compatible; no caller changes needed.
- **Verified (testing_agent iteration_8):** 0 Radix errors / 0 blank screens across 9 KNSelect pages. Phase 1.11 (Sales Returns) + 1.12 (Special Orders) render seeded data and forms work.
- **Bonus fixes found during verification:**
  - Auth token localStorage key bug: `SpecialOrders.jsx`, `ApprovalInbox.jsx`, `ApprovalRulesSettings.jsx` read `"token"` (never written) instead of `"kn_token"` → standardized to `kn_token`.
  - RBAC gap: `approval` + `settings` permission modules were missing from ALL roles in `permissions_config.py`, making Approval Inbox (`/api/approval-requests` needs `approval.view/approve`) and Approval Rules (`/api/approval-rules` needs `settings.view/manage`) return 403 for everyone. Added `approval`+`settings` to admin (full) and manager (approval + settings.view). Auto-synced to DB via `sync_permission_modules()`. Endpoints now 200.
- Gates all green: ux_audit 0/0, data_integrity 96 PASS, api_contract OK, compliance 61 PASS / 0 FAIL (5 pre-existing naming/size WARN).

### v1.2 — Session #016 (Fase 0.5 ENABLER — Roll-as-SSOT Inventory Ownership)
- Implementasi fondasi kepemilikan stok per entitas di level ROLL (`inventory_rolls` = SSOT fisik; `inventory_balances` = proyeksi 3-key product+warehouse+owner_entity_id, bucket detail).
- Reservasi sales order OWNER-SCOPED di level roll (create→reserved, approve→committed, cancel→available) + konservasi panjang terjaga.
- Visibilitas owner+lot+roll (read-only): tab Rolls, kolom Pemilik, Ownership Matrix di ProductDetail.
- Gates: data_integrity 72/0/0 (+L4-ROLL), POC 18/18, testing_agent backend 19/20 (1 false-positive). available 3055 / reserved 220 terjaga.
- Backlog Fase 1: inter-company transfer flow, allocation policy configurable, mixed-lot UI, ATP (blocking: Info-Needed I1–I6 di KN_16).

### v1.0 — 23 Mei 2026 (Initial PRD)
- Created PRD based on existing codebase inventory
- Documented 12 completed feature modules
- Defined backlog priorities (Critical → Low)
- Outlined ERP roadmap (Tier 1-3)
- Established baseline metrics
- Documented technical debt

---

**Maintained by:** Development Team  
**Review Cycle:** Quarterly  
**Next Review:** August 2026
