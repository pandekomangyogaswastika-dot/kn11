# PLAN — POS & Order SSOT Revamp (Sesi Lanjutan #057)

> Status: **DRAFT untuk review owner** · Dibuat: 23 Jun 2026 · Basis: review mendalam 15 poin temuan owner + performa + navigasi.
> Aturan main proyek tetap: **kode menang atas prosa**; tiap fase ditutup verifikasi gate + testing agent; perubahan data harus **additive + backfill idempotent**.

---

## 0. Ringkasan
Revamp modul POS + Sales Order berbasis 15 temuan owner. Mencakup: perbaikan performa & navigasi, penyederhanaan UI POS, **UoM SSOT (satuan dari master + roll-count)**, **redesign status SO (2-level SSOT)**, **penyatuan alur approval (special price + over-credit + nilai) anti double-logic**, **PPN/Faktur per-entitas**, **multi-entitas untuk sales + rekening per-entitas**, dan fitur baru **Catalog Model**.

---

## 1. KEPUTUSAN OWNER (LOCKED)
1. **UoM SSOT:** 1 produk = 1 `base_unit` untuk SEMUA roll-nya; tiap roll beda **panjang**, bukan beda satuan. POS **tidak** memilih satuan. Inventory & POS tampil **"X roll / Y {base_unit}"**. (kg hanya untuk catch-weight yang sudah ada).
2. **PPN & Faktur:** PPN mengikuti **entitas** (`default_tax_mode`); tambah toggle **"minta Faktur Pajak"** per order; entitas **bisa diganti di checkout**; UI memperjelas **"Anda di entitas X sebagai role Y"**.
3. **Multi-entitas sales:** sales bisa di-assign >1 entitas (`allowed_entity_ids`); **rekening per-entitas** (koleksi `bank_accounts` sudah ada) — siapkan slot untuk Finance lanjutan.
4. **Special price & over-credit = aksi SETELAH buat SO** (di **detail SO**, bukan di checkout). Wajib **alasan + lampiran bukti**. Approver = manager/admin.
5. **Over-credit:** SO **tetap tersimpan** + tombol **"Minta Approval Kredit"** (membawa data order) — **bukan** diblokir 409.
6. **RBAC:** SALES hanya **BUAT SO + unggah bukti/validasi**; **tidak** approve/confirm/proses. Admin/Manager yang approve; selanjutnya progres **otomatis oleh sistem**.
7. **Validasi admin:** setiap SO divalidasi/di-approve admin sebelum **Confirmed** (diatur `approval_rules`, configurable; default: wajib).
8. **Catalog Model:** hanya **referensi** (tidak dijual, tidak ada stok).

---

## 2. MODEL STATUS SO (SSOT) — FINAL

### 2.1 Dua level
- **STAGE (timeline induk, linear):** `Reserved → Approved → Confirmed → Picked → Shipped → Delivered` (+ `Cancelled`).
- **SUB-STATUS (anak, kontekstual, boleh >1):** alasan "kenapa berhenti di sini".

### 2.2 Definisi stage + sub-status
| Stage | Arti | Sub-status yang mungkin |
|---|---|---|
| **Reserved** | SO dibuat, stok dipegang, **belum disahkan** | `menunggu_validasi`, `menunggu_approval_harga`, `menunggu_approval_kredit`, `menunggu_approval_nilai`, `siap_disahkan` |
| **Approved** | Sudah di-ACC admin; **komersial final**. Jika **barang belum masuk gudang (backorder) → BERHENTI di sini** | `menunggu_stok` (backorder), `siap_confirm` (stok siap) |
| **Confirmed (Keep)** | Barang **siap di gudang**, di-commit, task outbound dibuat | `siap_pick`, `sedang_pick` |
| **Picked (Ready)** | Barang sudah diambil gudang | `sebagian_dipick` |
| **Shipped** | Barang dikirim | `sebagian_dikirim` |
| **Delivered (Done)** | Diterima customer; selesai | — |
| **Cancelled** | Dibatalkan; reservasi/komitmen dilepas | — |

> Perubahan kunci dari diskusi: **`menunggu_stok` ada di stage APPROVED** (bukan Confirmed). Order yang sudah di-ACC tapi barang belum datang berhenti di Approved; naik ke Confirmed hanya saat stok benar-benar siap di gudang.

### 2.3 Pemetaan migrasi (status lama → baru, additive + backfill idempotent)
- `waiting_approval` → **Reserved** + `menunggu_approval_*`
- `reserved` (pra-approval) → **Reserved** + (`menunggu_validasi` atau `siap_disahkan`)
- `waiting_stock` → bila SO sudah di-approve: **Approved** + `menunggu_stok`; bila belum: **Reserved** + tanda backorder
- `approved` → **Approved** + (`siap_confirm`/`menunggu_stok`)
- `confirmed` → **Confirmed**
- `partially_picked` → **Picked** + `sebagian_dipick`
- `picked` → **Picked**
- `partially_shipped` → **Shipped** + `sebagian_dikirim`
- `shipped` → **Shipped**
- `done` → **Delivered**
- `cancelled` → **Cancelled**

### 2.4 Model approval terpadu (anti "double-logic")
Ganti 3 mekanisme paralel (approval_rules / credit_overrides / price_approvals yang saling menimpa status) dengan **1 SSOT di SO**:
```
so.pending_approvals: [
  { type: "nilai" | "kredit" | "special_price",
    required_role, status: "pending"|"approved"|"rejected",
    requested_by, decided_by, reason, evidence_url, ref_id, order_snapshot }
]
```
Aturan: **SO tidak naik ke Approved sampai SEMUA item `pending_approvals` = approved.** Koleksi `credit_overrides`/`price_approvals` tetap dipakai sebagai detail tapi **statusnya direferensikan** lewat daftar ini (1 sumber kebenaran). "Pusat Persetujuan" membaca daftar ini + menampilkan konteks order.

---

## 3. RISIKO KONFLIK DATA & MITIGASI
1. **Migrasi status SO** → skrip backfill idempotent (`scripts/migrate_so_status.py`) + gate verifikasi; jangan hapus field lama, tambahkan `stage`+`sub_status` dulu lalu deprecate.
2. **Triple-approval** → satukan ke `pending_approvals` (lihat §2.4); satu transisi `recompute_approval_gate()`.
3. **Special price pending** → simpan `unit_price_normal` + `unit_price_requested`; SO tak boleh maju sampai approved; tolak → revert. Ubah `get_effective_special_price` agar boleh state pending.
4. **Ganti entitas di checkout** → reset & re-preview ATP/harga/PPN/kredit; reservasi roll hanya saat create terhadap entitas final.
5. **UoM lock** → dukung tampilan order lama (unit non-base); `roll_count` field baru additive + backfill `rebuild_balance`.
6. **Multi-entitas sales** → insentif ikut entitas SO, payroll ikut `home_entity_id`; penomoran SO per-entitas (sudah ada).

---

## 4. RENCANA BERTAHAP (setiap fase ditutup testing agent + gate)

### FASE 1 — Performa + Quick Wins UI + Navigasi (risiko rendah, dampak cepat)
> ✅ **SELESAI & TERVERIFIKASI (23 Jun 2026, Sesi #058)** — compile HIJAU (FE webpack compiled, BE `/api/` 200 "Kain Nusantara API aktif"); `seed_reset.sh` SEMUA GATE LULUS (contract ✅ · api_contract ✅ · data_integrity ✅ · entity_scoping F0-C ✅). Verifikasi UI end-to-end (main agent, viewport 1920×800; testing agent kena infra-timeout `networkidle` krn HMR websocket — bukan bug app):
> - Login 1-klik admin OK, dashboard Control Tower render data nyata, **0 console error**.
> - **Navigasi semua menu: 60/60 view dikunjungi, 0 crash, 0 red-overlay, 0 console error.**
> - **Poin 11** sidebar highlight sinkron dgn `activeView` (`nav-sales`/`nav-home` class `active`). 
> - **Perf loadAll**: pilih customer TIDAK full-reload (product-grid tetap mounted di belakang drawer).
> - **Poin 1** kartu 1 tombol "Pilih Varian & Detail"/"Lihat Detail & Tambah" (buka `product-quickview`). **Poin 5** label harga ikut `base_unit` (kartu "/meter", popup "HARGA/METER"). **Poin 6** filter "Rentang Harga (Rp)" tanpa "/meter". **Poin 7** checkout step-1 "Item Pesanan (N)" ringkasan. **Poin 15** ATP "Tersedia sekarang + Akan datang = Bisa dijanjikan". Gambar `loading=lazy/decoding=async`.
- **Perf:** perbaiki `useAppActions.loadAll` — hapus `selectedCustomer` dari deps & dari trigger reload penuh (pisahkan auto-select customer); kurangi reload penuh pasca-aksi yang tidak perlu.
- **Gambar:** tambah parameter ukuran pada URL gambar (kurangi lag render).
- **Poin 1:** gabung tombol "Tambah" + "ⓘ" → 1 tombol buka detail penuh (`PosProductCard.jsx`).
- **Poin 5:** label harga ikut `base_unit` (`ProductQuickView`, kartu).
- **Poin 6:** ubah label filter "Rentang Harga (Rp/meter)" → "Rentang Harga" (`FacetRail.jsx`).
- **Poin 11-nav:** jadikan highlight sidebar **turunan dari `activeView`** (satu SSOT) → sidebar selalu sinkron (`App.js`, Sidebar).
- **Poin 7:** tampilkan ringkasan item keranjang di checkout **step 1** (`CheckoutDrawer.jsx`).
- **Poin 15:** perjelas label ATP → "Tersedia sekarang 755 + Akan datang 800 = Bisa dijanjikan 1.555".
- **Test:** navigasi semua menu, POS pilih customer (cek tidak lag), checkout step 1.

### FASE 2 — UoM SSOT (satuan dari master + roll-count) — poin 4a/4b/5
> ✅ **SELESAI & TERVERIFIKASI (23 Jun 2026, Sesi #058)** — gate `seed_reset.sh` LULUS (data-integrity 119/0/0, F0-C ✅, `[F2-UoM] roll_count backfilled ke 16 balance`). Testing agent iter_73: backend API PASS (roll_count di /products, /inventory/balances +base_unit, stock-breakdown ownership_matrix); FE diverifikasi via screenshot + `ui_smoke.py` 9/9.
> - **Backend:** `roll_service.rebuild_balance` hitung `roll_count`(roll tersedia)/`on_hand_roll_count`/`roll_counts` per-bucket; `inventory_service.product_summary` agregasi roll_count; `roll_service.backfill_roll_counts()` (additive+idempotent, TANPA sentuh qty) + dipanggil di akhir seed; `scripts/migrate_roll_count.py` (migrasi terpisah). `/api/inventory/balances` tambah `base_unit`.
> - **POS hapus pemilih satuan:** `ProductQuickView` (selector `quickview-unit-select` DIHAPUS → field FIXED `quickview-unit-fixed`=base_unit + stat `quickview-roll-count`); `CheckoutDrawer` step-2 (selector `cart-item-unit-select` DIHAPUS → Qty(base_unit) + `cart-item-rolls-<id>`). Order create unit=base_unit OK (KSC/SO-00010).
> - **Tampil "X roll / Y base_unit":** kartu (`product-rolls-<id>`), mobile (`mobile-product-rolls-<id>`), inventory `BalancesTable` (`balance-onhand-rolls`/`balance-avail-rolls`).
> - **Master data:** field "Satuan Dasar" (`admin-product-base_unit-input`) kini DROPDOWN (meter/yard/cm/inch/kg/pcs/lembar) + nota penjelasan.
> - Catatan: catch-weight (kg) tetap di alur inbound `GRCatchWeightModal` yang sudah ada (tak tersentuh).
- **Backend:** `rebuild_balance` simpan `roll_count` per bucket; pastikan satuan tunggal = `base_unit`; endpoint stok kembalikan `roll_count`+`length`.
- **Master data:** perjelas pilih **Satuan Dasar** di master produk; alirkan ke purchasing (terima roll dgn panjang masing-masing) & inventory.
- **POS:** hapus pemilih satuan (popup + checkout) → pakai `base_unit`; tampil **"X roll / Y {base_unit}"** di kartu, detail, inventory.
- **Migrasi:** backfill `roll_count`.
- **Test:** master set satuan → purchasing terima 2 roll beda panjang → inventory "2 roll / 300 yard" → POS tampil benar.

### FASE 3 — Master Data: Deskripsi + Gambar per-varian — poin 3 & 2
> ✅ **SELESAI & TERVERIFIKASI (24 Jun 2026, Sesi #058)** — testing agent iter_74: **100% PASS** (backend 4/4, POS 100%, admin 100%, 0 bug). Gate `seed_reset.sh` LULUS (119/0/0).
> - **Backend:** `ProductPayload.description` (create) + `description` di whitelist PATCH (`routers/products.py`). Round-trip POST/PATCH/GET diverifikasi. (image per-varian sudah ada di model).
> - **POS popup:** `ProductQuickView` tampil blok `quickview-description` (ikut varian terpilih, fallback `group.description`); ganti varian → **SKU + gambar (`quickview-image`) + deskripsi** berubah (Biru-Coklat→Hijau-Emas terverifikasi). `variants.js` expose `group.description`.
> - **Master form (`AdminView`):** input URL gambar `admin-product-image-input` + preview `admin-product-image-preview` + textarea `admin-product-description-input` + dropdown `admin-product-base_unit-input`; tombol **Edit kini membuka form** (`setShowCreateForm(true)`) & load nilai; Update simpan via PATCH OK.
> - **Seed:** batik `tpl_batik_mega` 3 varian = 3 gambar BERBEDA (+ endek 3 varian); deskripsi per-produk auto-generate (ikut warna/grade → beda per varian).
- **Backend:** tambah `description` ke produk; tambah `image` per-varian (schema + generate varian tidak paksa samakan).
- **Frontend:** form master varian (set gambar + deskripsi per varian); popup detail tampilkan deskripsi; gambar berubah saat ganti varian.
- **Seed:** beri gambar berbeda per varian batik.
- **Test:** ganti varian → gambar & deskripsi berubah.

### FASE 4 — Redesign Status SO (SSOT 2-level) — poin 3 (fondasi) + bug poin 14
- **Backend:** tambah field `stage` + `sub_status` (+ keep status lama selama transisi); refactor transisi create/submit/approve/confirm; `recompute_so_status` & banner; **backorder→Approved(menunggu_stok)**.
- **Bug poin 14:** transisi aman (tidak ada 409 mentah; tombol di-guard sesuai stage; pesan memandu).
- **Frontend:** timeline tampil **stage + chip sub-status**; OrdersView/Dashboard pakai mapping baru.
- **Migrasi:** `migrate_so_status.py` (idempotent) + gate.
- **Test:** semua skenario (normal, nilai besar, backorder) berada di stage/sub yang benar; auto-approve tidak error.

> ⏸️ **HANDOFF — DEVELOPMENT BERHENTI DI SINI (24 Jun 2026, Sesi #058)**
> Status FASE 4: **POC SELESAI & LULUS — wiring app BELUM dimulai.** App tetap berfungsi penuh (FASE 1/2/3 live); semua yang dibuat di FASE 4 sejauh ini **ADDITIVE & belum dipakai runtime** (belum di-import di mana pun), jadi **aman / tidak ada risiko regresi**.
>
> **✅ SUDAH DIKERJAKAN (terverifikasi):**
> 1. `backend/services/so_status.py` (BARU) — SSOT derivasi 2-level: `derive_stage_substatus(order)→(stage,[sub])`, `stage_fields()`, `backfill_so_status(db)` (idempotent), `STAGE_FLOW`, `VALID_STAGES`, `SUBSTATUS_LABELS`, `stage_index()`. Keputusan kunci ter-implement: **approved+backorder → Approved/menunggu_stok** (bukan Confirmed).
> 2. `backend/scripts/poc_so_status.py` (BARU) — POC isolasi. **HASIL: POC LULUS** — 13 skenario unit PASS + 9 SO di DB semua stage valid (distribusi: Delivered 1, Shipped 2, Confirmed 1, Approved 1, Reserved 4) + backfill idempotent 2× (invalid=0). Jalankan ulang: `cd /app/backend && python scripts/poc_so_status.py`.
>
> **⬜ BELUM DIKERJAKAN (lanjutan FASE 4 — urut prioritas):**
> 1. **Wiring backend** (import `so_status.stage_fields`): di `routers/sales_orders.py` → `create_order` (set stage di dok sebelum insert), `_transition` (tambah `stage_fields({**order,**update_data})` ke `update_data`), `release_reservation`; di `services/fulfillment_status.py` → `recompute_so_status` (tambah ke `set_doc`). Fallback: di `_norm_backorder` tambahkan stage bila belum ada.
> 2. **Migrasi formal** `backend/scripts/migrate_so_status.py` (standalone, panggil `backfill_so_status`, self-verify exit≠0 bila invalid) + **panggil `backfill_so_status` di akhir `seed_realistic.seed_all`** (pola sama spt `backfill_roll_counts`).
> 3. **Bug poin 14:** ubah pesan 409 di `_transition` jadi memandu (sebut stage + aksi yang boleh); FE: guard tombol per-stage.
> 4. **Frontend:** `utils/soStatus.js` (mirror derivasi sbg fallback: `getStage`, `getSubStatus`, `STAGE_FLOW`, `stageMeta`, `subStatusLabel`); `OrderDetailPanel.jsx` timeline jadi **stage-based + chip sub-status** (ganti `TIMELINE_STEPS/STATUS_ORDER` berbasis status); `OrdersView.jsx` badge stage + chip; `OrderDashboard.jsx`/Dashboard pakai mapping stage.
> 5. **Tutup fase:** `seed_reset.sh` gate + testing agent end-to-end (skenario normal / nilai besar→waiting_approval / backorder→Approved-menunggu_stok / auto-approve) + update doc ini ke SELESAI.
>
> **Referensi model:** §2.2 (definisi stage+sub) & §2.3 (pemetaan migrasi) di dokumen ini = sumber kebenaran. Resep test UI: `scripts/ui_smoke.py` (domcontentloaded + data-testid, JANGAN networkidle/type=email).


### FASE 5 — Alur Approval Terpadu (special price + over-credit + nilai) + RBAC — poin 8/9/10/12/13
- **Backend:** model `pending_approvals` (§2.4); aksi **di detail SO**: "Ajukan Special Price" (harga+alasan+bukti) & "Minta Approval Kredit" (bawa data order); RBAC: sales **tak bisa** approve/auto-approve/confirm.
- **Poin 8/9:** hapus input diskon manual oleh sales; diskon hanya via special-price (admin/manager). Hilangkan 2-diskon yang membingungkan dari sisi sales.
- **Frontend:** "Pusat Persetujuan" terpadu (1 inbox, konteks order); detail SO punya aksi unggah bukti; sales hanya lihat status.
- **Test:** sales buat SO → ajukan special price + bukti → manager ACC → Confirmed; over-credit → SO tersimpan + minta approval → ACC; sales tak bisa auto-approve.

### FASE 6 — PPN/Faktur per-entitas + UX Entitas/Role + Multi-entitas + Rekening — poin 10/11 + 2c
- **Backend:** verifikasi/lengkapi edit entitas (`default_tax_mode`); `tax_override` + flag `needs_tax_invoice` di SO; user CRUD dukung `home_entity_id`+`allowed_entity_ids`; bank account per-entitas + slot "rekening tujuan".
- **Frontend:** checkout toggle "pakai Faktur Pajak" + ganti entitas (reset preview); banner "Anda di [entitas] sebagai [role]"; switcher entitas untuk sales multi-entitas; form master user assign entitas; master rekening per-entitas.
- **Test:** jual di entitas non-PPN → tanpa PPN; entitas PPN → PPN 11% + opsi faktur; sales 2-entitas bisa switch; rekening tampil per-entitas.

### FASE 7 — Catalog Model (fitur baru) — poin 6
- **Backend:** koleksi `catalog_models` (nama, gambar, deskripsi, `linked_skus[]`); CRUD; link dua arah.
- **Frontend:** menu "Catalog Model"; detail model → daftar SKU kain; detail kain → contoh model.
- **Test:** buat model → link ke SKU → muncul dua arah.

---

## 5. OUT OF SCOPE (slot disiapkan, implementasi nanti)
- Finance lanjutan: posting GL rekening, faktur pajak resmi (e-Faktur), F0-G/H eliminasi intercompany.
- Pajak dashboard (`cs-pajak`), tutup buku (`cs-closing`).

---

## 6. URUTAN EKSEKUSI & CHECKPOINT
F1 (perf+quickwin) → F2 (UoM) → F3 (master) → F4 (status SSOT) → F5 (approval+RBAC) → F6 (pajak+entitas) → F7 (catalog).
Tiap fase: implement → testing agent → fix → update doc ini → lanjut.
