# Development Plan — Kain Nusantara (WMS/ERP) — Smart Guidelines + Seed + Documentation + Discovery E‑Questionnaire (v2.5)

> ## 📌 STATUS GROUNDED (per 22 Jun 2026) — baca ini dulu
> **SELESAI & TERVERIFIKASI (gate hijau):** EPIC 1–3 · EPIC 7-A/B/C (AR Aging, Kas/Bank, CoA+GL) · Purchasing 7.2 (PO Amendment) · F0-A (entity identity) · **F-1** (pricelist/varian/special-price) · **F-2/F-2b** (stock buckets + ATP) · **F-3** (Special Order MTO + Aftersales/Credit Note + GL posting) · **F-4** (Mobile POS dedicated + POS advanced best-seller/FBT/substitusi + join/group sales split insentif) · **F-6** (Mobile-First Sales: shell `features/sales/mobile/*` + `useIsMobile`; sales@viewport≤768px dapat tampilan mobile-first 5 tab + escape-hatch "Tampilan Desktop"; testing iter_64 27/27; diverifikasi ulang Session #051 — FE compile difix via yarn resolutions wds 4.15.2).
> **PRIORITAS NYATA berikutnya (grounded):** **F-0 Multi-Entity SELESAI 100%** — F0-A/B/C/D/E/F semua HIJAU (gate `verify_entity_scoping.py` HIJAU di `seed_reset.sh` [5/5]). **F0-E SELESAI (22 Jun 2026):** (1) `reporting.py` ter-scope per-entitas (6 endpoint: summary/funnel/velocity/top-customers/warehouse-util/stock-aging — invarian aditif ksc+kanda==all terverifikasi); (2) **CoA SHARED by-code** (gl_accounts direklasifikasi SHARED di `entity_scope.py`; buku/saldo per-PT hidup di `journal_entries.entity_id`); (3) **Insentif→GL** akrual per-entitas (Model 1: pembayar = entitas SO) via akun baru `6-5000 Beban Insentif` / `2-1500 Hutang Insentif` + `POST /api/crm/sales/incentive/post-gl` (idempotent) & `GET /api/crm/sales/incentive/gl-status`; (4) PKP/PPN per-entitas via `config_service`. Berikutnya = keputusan owner (F-5 / EPIC 7 lanjutan / konsolidasi F0-G).
> **ASPIRATIF (BUKAN kontrak — jangan dikerjakan tanpa keputusan owner):** F-5 (carrier/CRM omnichannel), EPIC 7 lanjutan jauh (Closing/P&L/Neraca, SMTP, FX). Semua ini ditandai eksplisit "ASPIRATIF" di tempatnya.
> **Aturan emas:** kode menang atas prosa; verifikasi = GATES (`seed_reset.sh`, dst), bukan baca ulang dokumen.


---
---

# 🟢 F-0 — MULTI-ENTITY FOUNDATION (SELESAI 100% — F0-A/B/C/D/E/F) — acuan: `memory/MULTI_ENTITY_ARCHITECTURE.md`
> **STATUS GROUNDED (diverifikasi 22 Jun 2026 via `verify_entity_scoping.py` — di `seed_reset.sh` [5/5], HIJAU):**
>
> **✅ Sudah jadi & GATE HIJAU:** F0-A (entity identity) · F0-B (scope helpers, STATIC ✅) · **F0-C (DB CHECK ✅)** · F0-D (penomoran per-entitas `KSC/SO-…`, `KANDA/SO-…`) · **F0-E (finance per-entitas ✅ — lihat di bawah)** · F0-F (provisioning: `entity_provisioning_service.py`, `routers/entities.py`, `AdminView.jsx`).
> **✅ F0-E SELESAI (22 Jun 2026) — keputusan D2 di-resolve = Model 1 (selling==home) + CoA SHARED + insentif di buku entitas SO:**
>   - **Reporting per-entitas:** `routers/reporting.py` memakai `entity_ctx`+`resolve_list_scope` (sales_orders→entity_id, inventory→owner_entity_id). Invarian aditif **ksc+kanda==all** terbukti (orders_today 3+1=4, monthly_rev 42.775jt+36.55jt=79.325jt). Exemption gate `→ F0-E` dihapus.
>   - **CoA SHARED by-code:** `gl_accounts` direklasifikasi **SHARED** di `entity_scope.py` (keluar dari SCOPED_COLLECTIONS) — bukan stamp-ke-primary lagi. Buku & saldo terpisah hidup di `journal_entries.entity_id` (sudah ter-scope di `gl.py`/`gl_service.py`). Trial balance per-PT seimbang; 'all'=jumlah. Gate DB-CHECK kini HIJAU tanpa false-fail gl_accounts.
>   - **Insentif→GL (Model 1):** akun baru `6-5000 Beban Insentif Penjualan` + `2-1500 Hutang Insentif Penjualan`; `gl_service.post_incentive_accrual(entity,period)` idempotent (Dr Beban / Cr Hutang di buku entitas SO) + `incentive_accrual_status`. Endpoint `POST /api/crm/sales/incentive/post-gl` & `GET /api/crm/sales/incentive/gl-status` (RBAC manager/admin; sales 403; entity 'all' 400). FE: panel `sf-incentive-gl` di `SalesForceDashboard.jsx` (gated entitas spesifik).
>   - **Pajak PKP per-entitas:** `config_service.get_effective_settings(entity_id)` → is_pkp dari `business_entities` (ent_ksc PPN 11%, ent_kanda non-PKP 0%).
>   - **Bukti gate:** seed_reset 4/4 HIJAU (incl F0-C), health_check 21/0/0, endpoint_sweep 0×5xx, ux_audit 0 ERROR, verify_api_contract 0 ERROR, validate_compliance 0 FAIL, esbuild 0. testing_agent iter_63: BE 38/39 (1 = path typo test-script, bukan bug), FE app loads 0 console error, semua role login.
>
> **Mekanisme inti:** `EntityContext` dependency + `scope_query`/`stamp_entity` + FE Entity Switcher (`X-Entity-Id`) + config resolver (global+override).
>
> **DoD F-0:** ✅ TERPENUHI (trial balance per-entitas seimbang; PPN ikut PKP entitas; insentif terbukukan di buku entitas SO).
>
> **Berikutnya (ASPIRATIF — butuh keputusan owner):** konsolidasi grup + eliminasi intercompany (F0-G/H), F-5, EPIC 7 lanjutan.

## 📋 SALES MODULE GAP BACKLOG (urut sesudah F-0; ref diskusi 13 poin)
- **F-1 ✅ SELESAI & TERVERIFIKASI (22 Jun 2026)** Pricelist/diskon governance (diskon dikelola MD, bukan input bebas sales) + special-price (approval) + **varian template→variant** (warna/motif/grade).
  - **F1a** Pricelist per-entitas vs global (`/pricelist*`, `pricelist_service`) — test **16/16**. UI `PricelistView.jsx`.
  - **F1b** Template→variant kartesian Warna×Grade×Lebar (idempotent, assign/detach) (`/product-templates*`) — test **20/20**. UI `ProductTemplatesView.jsx`.
  - **Special-price approval** draft→submit→approve/reject + effective lookup + attachments (`/price-approvals*`) — smoke **5/5** (SoD: sales 403, admin approve). UI `PriceApprovals.jsx`.
- **F-2 ✅ SELESAI & TERVERIFIKASI (22 Jun 2026)** Stock multi-bucket + ATP future-aware + Pending SO + delivery hold.
  - **F-2a ✅ SELESAI & TERVERIFIKASI** — papan bucket per produk + operasi Hold & WIP (`/stock/buckets|holds|wip|hold|wip/start`). Backend 20/20. Stale-perm warehouse/manager difix di `bootstrap.sync_permission_modules` (auto-merge AKSI default).
  - **F-2b ✅ SELESAI & TERVERIFIKASI** — **ATP future-aware** (`GET /stock/atp`: available + incoming(horizon, PO+ETA) − pending demand) + **Pending SO board** (`GET /stock/pending-so`: backorder dicocokkan ke incoming PO → coverage covered/partial/uncovered + promise_date) + **Delivery hold** (`hold_type` general|delivery|reservation). UI: tab "Pending SO" + panel ATP detail per produk + selector jenis hold di StockBucketsView. Additive (reuse `backorders`/on_order/hold, tanpa koleksi baru). Demo SO-0009 (durable, pinned ent_ksc). Test: backend 18/18, frontend 7/7, POC 19/19.
- **F-3 ✅ SELESAI & TERVERIFIKASI (22 Jun 2026)** Special Order MTO (request→approve→auto-create SKU→convert ke SO) + **Aftersales/RMA** (retur/bs/penggantian/komplain/garansi berbasis SO + credit note → GL + stok balik).
  - Backend: `create_sku_from_special_order()` (idempotent) + hook auto-create saat approve + endpoint `POST /special-orders/{id}/create-sku` & `POST /special-orders/{id}/convert-to-so`. Returns approval → Credit Note + GL posting (revenue/PPN/COGS reversal). Backend test **16/16** (GL balanced) — iteration_58.
  - Frontend: `SpecialOrderDetail.jsx` chip SKU + tombol Buat SKU / Konversi ke SO + chip linked SO (gated manager/admin, idempotent). Returns: tipe komplain/garansi (`ReturnShared`/`CreateReturnForm`) + tampil Nota Kredit (`ReturnDetail` section/chip + `SalesReturns` kolom CN). UI test **17/17** — iteration_60.
  - Refactor compliance: `SpecialOrderDetail.jsx` 527→365 baris (extract `SpecialOrderShared.jsx` + `SpecialOrderInfoPanels.jsx`) → validate_compliance 0 FAIL.
  - Gate final: `seed_reset.sh` **119 PASS / 0 FAIL**, health_check 0 FAIL, endpoint sweep 0 5xx, esbuild/ux_audit/api_contract 0 ERROR.
> **F-5 = ASPIRATIF / ide roadmap jauh — BUKAN kontrak, BELUM dieksekusi.** Jangan dianggap tugas berjalan; mulai hanya setelah keputusan owner. (F-5 = carrier/logistics abstraction + CRM omnichannel.)

---
---

# 🟢 EPIC 7-C — Chart of Accounts + General Ledger ✅ SELESAI & TERVERIFIKASI (21 Jun 2026)
> Lanjutan MASTER_ROADMAP §3 EPIC 7 (Finance). Setelah 7-A (AR Aging) & 7-B (Kas & Bank), sub-fase ini menghidupkan modul akuntansi inti yang sebelumnya "coming soon" (`cs-coa`, `cs-gl`).
> Owner: lanjut EPIC 7 sesuai plan, setelah verifikasi end-to-end state restore kn11 (semua gate hijau + login Control Tower data nyata).

## Yang dikerjakan
- **Backend** `services/gl_service.py` + `routers/gl.py`:
  - Koleksi kanonik baru: `gl_accounts` (prefix `gla_`) & `journal_entries` (prefix `je_`).
  - **Chart of Accounts** baku Indonesia (35 akun, 5 tipe; normal_balance turunan; hierarki parent_code; akun sistem tak terhapus) — `seed_default_coa()` idempotent (bootstrap + seed_realistic).
  - **Jurnal manual** double-entry SEIMBANG (validasi Σdebit==Σkredit, akun postable, non-negatif).
  - **Auto-posting idempotent** dari SSOT (source_type+source_id): `sales_orders` (Dr Piutang/Kas, Cr Pendapatan + PPN Keluaran) & `cash_transactions` (Dr/Cr Kas vs lawan akun by ref_type/kategori). Tidak double-count (kas = SSOT tunggal). `POST /api/gl/sync`.
  - **Neraca Saldo** (trial balance, SEIMBANG) + **Buku Besar** per akun (running balance) + `gl/summary`.
  - Permission module **"accounting"** (admin/manager: view/create/void/manage) → auto-sync via `sync_permission_modules` (non-destruktif).
- **Frontend** `features/finance/ChartOfAccounts.jsx` + `GeneralLedger.jsx` (tabs Jurnal / Neraca Saldo / Buku Besar) + `JournalEntryModal.jsx`; nav `cs-coa`/`cs-gl` → `chart-of-accounts`/`general-ledger` (live, hapus comingSoon) + PAGE_META + route App.js.
- **Gate-keeping**: `gl_accounts`/`journal_entries` ditambah ke `verify_contract.CANONICAL_COLLECTIONS` **dan** `ENTITY_REGISTRY.md` (L0 parity).

## Bukti (semua HIJAU)
- POC `test_epic7c_gl_poc.py`: **44/0** (CoA baku, CRUD+guard, sync idempotent, trial balance seimbang, jurnal manual+validasi, buku besar, void, RBAC sales/warehouse 403).
- seed_reset **119/0/0** (+contract +api_contract +integrity), 20 jurnal otomatis (8 SO + 12 kas), trial balance seimbang ~Rp 223.706.250.
- health_check **21/0** · endpoint_sweep **0×5xx** (90 OK-data) · ux_audit **0 ERROR** · esbuild **0** · check_nav_map **PASS** · verify_api_contract **0/0** · compliance **0 FAIL** (GeneralLedger.jsx 430<500).
- testing_agent_v3 (iteration_49): **BE 52/52 · FE 100% · Integrasi 100% · RBAC 100%**, 0 bug.

## Next (EPIC 7 lanjutan) — ASPIRATIF (butuh keputusan owner, BUKAN kontrak)
- Kandidat terdekat: Pajak (PPN/PPH) dashboard (`cs-pajak`). Lebih jauh & belum dieksekusi (jangan dianggap berjalan): Closing (`cs-closing`), Laba-Rugi & Neraca, PO PDF email (SMTP), Budget/Commitment Control, Multi-currency/FX.

---
---

# 🧭 STATUS PURCHASING — Phase 7.2 PO Amendment ✅ SELESAI (verifikasi 21 Jun 2026)
> Phase 7.2 PO Amendment / Version History **TUNTAS & terverifikasi** (POC `test_po_amendment_poc.py` **33/33**, semua gate hijau).
> - BE: `services/po_amendment_service.py` + `POST /api/purchase-orders/{id}/amend`.
> - FE: `features/admin/po/POAmendModal.jsx` + `POVersionHistory.jsx`.
> - Backlog purchasing P2 tersisa: PO PDF email (SMTP), Multi-currency/FX, Budget/Commitment Control.
> - Roadmap EPIC0–7 (CRM-4 future-proof) = **belum dieksekusi** (analisis selesai, lihat bagian bawah).

---

# ✅ SESI VERIFIKASI (restore dari GitHub `kn11`) — EPIC 1–3 TERVERIFIKASI ULANG
> Task owner: "verifikasi harusnya EPIC 1 hingga 3 sudah diimplementasi". Environment di-restore dari repo `kn11` ke `/app` (`.env` dipertahankan), deps terpasang, services jalan.
> Metode: GATES + POC + browser (bukan baca prosa). **Hasil: EPIC 1, 2, 3 BENAR-BENAR TERIMPLEMENTASI & berfungsi.**

## Bukti GATES (DB clean-seed)
- `seed_reset.sh`: **119 PASS / 0 FAIL / 0 WARN** + contract + api_contract + integrity HIJAU.
- `health_check.py`: **20 PASS / 0 FAIL** (3 WARN = transfers/cycle-count/invoices kosong, normal tak di-seed).
- `audit_endpoint_sweep.py`: **0×5xx** (hanya 404 path-template & 200-empty disengaja).
- `ux_audit.py`: **0 ERROR** (1 WARN lama RFQCreateModal tabular-nums).

## Bukti POC (live API)
- EPIC 1 `test_epic1_poc.py`: **45/0** — /home/sales|admin|manager, KPI per peran, sales TANPA HPP, RBAC sales→/home/admin=403.
- EPIC 2 `test_epic2_categories_poc.py`: **15/0** — 7 kategori baku, SO-line snapshot (0 missing), CRUD+guard (dup 409, in-use 409), RBAC.
- EPIC 3 `test_epic3_costing_ar_poc.py`: **17/0** — WAC math cocok roll, sales 403; AR receipt apply→outstanding turun→payment_status=partial, over-alloc 400.

---

---

# ✅ F-4 — MOBILE POS + POS ADVANCED + JOIN/GROUP SALES — SELESAI & TERVERIFIKASI (22 Jun 2026)

> Keputusan owner (terkonfirmasi): kerjakan **a → b → c berurutan**. Mobile POS = **layar/route BARU khusus HP** (backend katalog sama). Rekomendasi POS dihitung dari **histori `sales_orders`** (tanpa AI). Split insentif join/group = **persentase custom per orang** (sum=100). Tidak ada aturan bisnis khusus tambahan.

## Hasil akhir (grounded — semua TERVERIFIKASI)
- **F-4a Mobile POS** (FE, reuse BE): view `mobile-pos` (nav admin/sales) — `MobilePOS` + `MobileProductCard` + `MobileCartSheet`. Katalog+search+kategori, add-to-cart, cart sheet, checkout (customer/alamat/term/backorder) → `submitOrder` (kini return bool). Testing agent iteration_61 **31/32**; happy-path & credit-block diverifikasi (KSC/SO-00012).
- **F-4b POS advanced** (BE+FE): `routers/pos.py` + `services/pos_recommendation_service.py` → `GET /api/pos/best-sellers`, `/pos/frequently-bought-together`, `/pos/substitutes` (agregasi `sales_orders`, TANPA koleksi baru; substitusi tiered kategori→grade→populer). FE: `PosBestSellers` (strip, MobilePOS+SalesPortal), `PosFBT` (di cart), `PosSubstitutesSheet` (saat OOS). POC 3 endpoint OK.
- **F-4c Join/group sales** (BE+FE): `SalesOrderCreate.sales_team` (PIC + co-sales, validasi Σ=100 & tepat 1 PIC) tersimpan di order; `sales_force_service` membagi komisi berbobot `split_pct` (tim menggantikan atribusi assigned_sales). FE `SalesTeamEditor` di `MobileCartSheet` + `CheckoutDrawer`. POC `backend/scripts/poc_f4c_group_sales.py` **PASS** (split 60/40 eksak, outsider=0, validasi 400). UI end-to-end: KSC/SO-00013 dgn tim Bima(60)+Citra(40).
- **Gate final:** `seed_reset.sh` **120 PASS / 0 FAIL / 0 WARN** · validate_compliance **78 PASS / 0 FAIL** · esbuild 0 · ux_audit 0 ERROR · verify_api_contract 0 ERROR · endpoint sweep 0×5xx. Testing agent UI iteration_62 **19/20** (1 non-bug: keterbatasan automasi Radix combobox; diverifikasi manual OK).

---


# ✅ F-3 — SPECIAL ORDER MTO + AFTERSALES (RMA) + AUTO GL POSTING — SELESAI & TERVERIFIKASI (22 Jun 2026)

## Objective (Update)
Menutup loop end-to-end untuk penjualan produk custom (MTO) dan layanan purna jual:
1) Special Order dapat di-approve → **otomatis dibuat Product SKU** (idempotent) → dapat dikonversi menjadi Sales Order standar.
2) Aftersales (retur/bs/penggantian/komplain/garansi) menghasilkan **Credit Note** dan **posting GL otomatis** (revenue reversal + PPN reversal + COGS reversal bila stok balik).
3) Semua perubahan aman terhadap gate integritas (`seed_reset.sh`).

## Hasil akhir (grounded — semua SELESAI & TERVERIFIKASI 22 Jun 2026)
### Backend
- Special Order MTO loop: `create_sku_from_special_order()` idempotent + auto-create SKU saat approve + endpoint `POST /api/special-orders/{id}/create-sku` & `POST /api/special-orders/{id}/convert-to-so` (linkage `linked_product_id`/`linked_sales_order_id`, audit log). Backend test **16/16**, GL balanced (iteration_58).
- GL auto-posting: `simulate-payment` → `post_sales_order` + `post_order_cogs`; approval `sales_returns` → Credit Note (`credit_notes`) + `post_sales_return` (revenue/PPN/COGS reversal). `return_type` valid: `retur|bs|penggantian|komplain|garansi`.

### Frontend
- `SpecialOrderDetail.jsx`: chip SKU & SO + tombol Buat SKU / Konversi ke SO (gated manager/admin, idempotent). Direfactor 527→**365** baris (`SpecialOrderShared.jsx` + `SpecialOrderInfoPanels.jsx`).
- Returns: tipe komplain/garansi (`ReturnShared`/`CreateReturnForm`) + tampil Credit Note (`ReturnDetail` chip+section, `SalesReturns` kolom CN). UI test **17/17** (iteration_60).

---


## Berkas referensi inti (Update)
- BE:
  - `backend/routers/special_orders.py` (target utama F-3)
  - `backend/services/special_order_service.py`
  - `backend/routers/sales_orders.py` (create_order, source_special_order_id)
  - `backend/routers/invoices.py` (simulate-payment → GL posting)
  - `backend/services/return_service.py` (credit note + GL posting)
  - `backend/services/gl_service.py` (post_sales_order, post_order_cogs, post_sales_return)
- FE:
  - `frontend/src/features/sales/SpecialOrders.jsx`
  - `frontend/src/features/sales/SpecialOrderDetail.jsx`
  - `frontend/src/features/sales/SalesReturns.jsx`
  - `frontend/src/features/sales/ReturnDetail.jsx`
  - `frontend/src/features/sales/ReturnShared.jsx`
  - `frontend/src/features/sales/CreateReturnForm.jsx`

---

> Guardrails:
> - Jangan ubah `.env` port/URL.
> - Jangan rename `data-testid` yang sudah ada.
> - Jika data aneh/missing setelah perubahan skema/collection: jalankan `bash scripts/seed_reset.sh`.
> - Ikuti design system existing (`tokens.css`, `components.css`, `section-card`, `primary-button`, `KNSelect`, `field`).
