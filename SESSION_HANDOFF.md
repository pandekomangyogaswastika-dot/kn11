# SESSION HANDOFF — Kain Nusantara (WMS/ERP)

> Diperbarui akhir sesi. Bahasa: Indonesia. Ikuti `MASTER_ROADMAP.md` (urutan EPIC).

---

## 1. RINGKAS STATUS PROGRAM
| EPIC | Judul | Status |
|---|---|---|
| EPIC 0 | IA Hygiene + Scaffold F4/F5 | ✅ CODE-COMPLETE (browser-E2E tertunda) |
| EPIC 1 | Role Experience & Sales Home | ✅ CODE-COMPLETE (browser-E2E tertunda) |
| EPIC 2 | Master Kategori + Snapshot SO | ⬜ BERIKUTNYA |
| EPIC 3–7 | Costing/AR, Incentive v2, POS, Timeline, Finance | ⬜ Belum |

---

## 2. YANG DIKERJAKAN DI SESI INI (EPIC 1 Frontend Integration)
**Backend (sudah ada sebelumnya, terverifikasi):** `GET /api/home/sales|admin|manager`
(`routers/home.py` + `services/home_service.py`); matrix izin `permissions_config.py`
mencabut HPP/vendor-bill/input-tax/PO dari role `sales` (stok tetap read). POC `test_epic1_poc.py` = 45/0.

**Frontend (sesi ini):**
- `frontend/src/App.js`:
  - Import `SalesHome` & `AdminHome`.
  - Render branch baru: view `sales-home` (Performa Saya) & `admin-home` (Control Tower).
  - `activeView` awal kini **sadar-role** (konsisten saat refresh halaman).
- `frontend/src/config/navigationConfig.js`:
  - `ROLE_HOME_REGISTRY`: Beranda **sales→sales-home**, **admin→admin-home** (navId `home`).
    POS & Master Data tetap diakses lewat menu masing-masing.
  - `PAGE_META`: tambah entri `sales-home` & `admin-home`.
  - **Pengetatan nav sales**: grup **Pembelian** + item `vendor-bills`, `landed-cost`,
    `input-tax`, `purchase-requisitions` dicabut dari `sales`. Sales kini 11 item (read stok tetap).

---

## 3. HASIL VERIFIKASI (gate hijau)
- **esbuild**: 0 error (hanya 1 warning lama tak terkait di `CreateSpecialOrderForm.jsx`).
- **check_nav_map.py**: PASS — reach admin:55 / sales:11 / manager:46 / warehouse:20.
- **validate_compliance.py**: 68 PASS / 0 FAIL / 24 WARN (warning semuanya pre-existing).
- **navigationConfig.js**: 377/380 baris (di bawah batas guardrail).
- **Backend curl (localhost:8001)**:
  - `/api/home/admin` (admin) 200 — key: period, sales, ar, approvals_pending, low_stock, incentive_payout, leaderboard_top, top_overdue.
  - `/api/home/sales` (sales) 200 — key: commission, target, kpi, history, customers, collections, recent_orders.
  - `/api/home/manager` (manager) 200.
  - Batas izin: sales→`/api/home/admin` = **403**, sales→`/api/vendor-bills` = **403**.

---

## 4. ISU TERBUKA (P0 — INFRA, BUKAN KODE)
**Preview URL ter-shadow deployment lain ("SKYBDAY").**
- Dampak: `testing_agent_v3` (browser E2E) & validasi visual UI **DIBLOKIR**.
- Aksi: user kirim email ke `support@emergent.sh` untuk fix edge-routing.
- Sementara: gunakan `curl`/`python -c` (backend) + `esbuild` (frontend) untuk verifikasi.

---

## 5. LANGKAH BERIKUTNYA
1. **Setelah Preview URL pulih**: jalankan `testing_agent_v3` untuk EPIC 0 & EPIC 1
   (login: admin/sales/manager@kainnusantara.id, password `demo12345`) — validasi visual
   Sales Home, Admin Control Tower, sidebar sales tanpa back-office.
2. **EPIC 2** — Master Kategori Produk (`product_categories`) CRUD admin + snapshot `category`
   pada SO line + backfill idempotent (lihat MASTER_ROADMAP §3 EPIC 2 & F1).

---

## 6. CATATAN PENTING UNTUK AGEN BERIKUTNYA
- **navigationConfig.js mepet batas (377/380)** — sangat hemat saat menambah baris.
- **server.py** rawan IndentationError di blok `app.include_router`/`lifespan` saat edit — cek ekor file.
- Setelah perubahan skema/koleksi: jalankan `bash scripts/seed_reset.sh` lalu guardrail
  (`scripts/check_nav_map.py`, `scripts/validate_compliance.py`, `scripts/health_check.py`).
- Jangan ubah `.env` (`REACT_APP_BACKEND_URL`, `MONGO_URL`). Pakai UUID, datetime `timezone.utc`.

---

## 7. KREDENSIAL UJI
- admin@kainnusantara.id · sales@kainnusantara.id · manager@kainnusantara.id
- Password: `demo12345`
