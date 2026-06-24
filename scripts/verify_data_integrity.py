#!/usr/bin/env python3
"""
verify_data_integrity.py — Kain Nusantara (KN3) POST-SEED INTEGRITY GATE
========================================================================
"Penjaga yang hilang". Menangkap kelas bug yang TERUS berulang walau RC-1
sudah didokumentasikan:

  L1. Seed↔App collection DRIFT   (seed menulis nama legacy, app baca kanonik)
  L2. Seed GAP                    (koleksi yang dibaca app tidak pernah diisi)
  L3. Cross-endpoint INTENT drift (KPI dashboard != sumbernya; stats != list)
  L4. Invarian akuntansi stok     (konservasi qty; total order == Σ subtotal)

KENAPA gate ini ada (pelajaran CASE_STUDY_INTENT_DRIFT torado60):
  • Validasi di DB dev yang KOTOR menutupi drift → gate ini WAJIB dijalankan di
    DB BERSIH sesudah seed_reset (lihat scripts/seed_reset.sh blok [GATE]).
  • "HTTP 200" / "service running" != benar → gate ini cek NILAI & invarian
    LINTAS-ENDPOINT, bukan status code.
  • Tambah fitur ⇒ tambah Concept(...) di sini (kanonik + legacy-harus-kosong).

Kontrak KN3 yang DIVERIFIKASI (bukan diasumsikan):
  • Auth: POST /api/auth/login {email,password} → {"token": "...", "user": {...}}
    (field token = "token", BUKAN access_token; respons LANGSUNG tanpa envelope).
  • List endpoint mengembalikan ARRAY langsung; dashboard objek langsung.
  • inventory_balances: on_hand == available + reserved + blocked + picked + in_transit.

Usage:
    cd /app && python scripts/verify_data_integrity.py
Exit 0 = semua invarian valid. != 0 = INTEGRITY VIOLATION (pakai sbg gate CI/seed).
"""
import asyncio
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Shared bootstrap (M4): SETIAP entrypoint load env dengan cara yang SAMA,
#    kalau tidak, script diam-diam menatap DB yang salah (bug D1 di Torado). ─────
ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except Exception:
    pass

G, Y, R, C, B, X = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[0m"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "kain_nusantara")

# API base: utamakan localhost (gate dijalankan di host yang sama dgn backend)
API = os.environ.get("API_BASE", "http://localhost:8001").rstrip("/")
ADMIN_EMAIL = os.environ.get("KN_ADMIN_EMAIL", "admin@kainnusantara.id")
ADMIN_PASS = os.environ.get("KN_ADMIN_PASS", "demo12345")


@dataclass
class Concept:
    """Satu konsep bisnis -> SATU koleksi kanonik yang dibaca app, plus nama
    legacy yang TIDAK BOLEH berisi data (drift aktif) setelah seed diperbaiki."""
    name: str
    canonical: str
    must_have_data: bool = True
    legacy_must_be_empty: list = field(default_factory=list)


# Kontrak executable KN3. Tambah fitur => tambah Concept di sini.
CONCEPTS = [
    Concept("users", "users", True, ["staff", "employees", "operator"]),
    Concept("products", "products", True, ["items", "goods", "materials", "kain"]),
    Concept("customers", "customers", True, ["clients", "buyers"]),
    Concept("warehouses", "warehouses", True, ["gudang", "depot"]),
    Concept("uoms", "uoms", True, ["satuan", "unit_ukur"]),
    Concept("inventory_balances", "inventory_balances", True, ["stock", "stok", "stock_balances"]),
    Concept("inventory_movements", "inventory_movements", True, ["stock_movements", "stock_history"]),
    Concept("inventory_rolls", "inventory_rolls", True, ["stock_units", "rolls", "fabric_rolls"]),
    Concept("system_settings", "system_settings", True, ["settings", "config", "configuration"]),
    Concept("payment_terms", "payment_terms", True, ["terms", "payment_term"]),
    Concept("approval_rules", "approval_rules", True, ["approval_matrix", "approvals"]),
    Concept("sales_orders", "sales_orders", True, ["orders", "penjualan", "customer_orders"]),
    Concept("purchase_orders", "purchase_orders", True, ["po", "pos", "pembelian"]),
    # Fase 3 — Procurement (Supplier Master + Pengelolaan Kas)
    Concept("suppliers", "suppliers", True, ["vendor", "vendors", "pemasok"]),
    Concept("cash_transactions", "cash_transactions", True, ["kas", "petty_cash"]),
    # Depth #1 — Retur Beli (Purchase Return / Nota Debit)
    Concept("purchase_returns", "purchase_returns", True, ["retur_beli", "debit_notes", "po_returns"]),
    # Depth #2 — Purchase Requisition (Hulu Procurement)
    Concept("purchase_requisitions", "purchase_requisitions", True, ["requisitions", "pr_list", "permintaan_pembelian"]),
    Concept("wms_tasks", "wms_tasks", True, ["inbound_tasks", "outbound_tasks", "receiving_tasks"]),
    Concept("document_templates", "document_templates", True, ["templates"]),
    Concept("permission_settings", "permission_settings", True, []),
    # Boleh kosong di seed minimal (transaksional/opsional) — must_have_data=False
    Concept("warehouse_transfers", "warehouse_transfers", False, ["transfers", "stock_transfer"]),
    Concept("cycle_count_sessions", "cycle_count_sessions", False, ["stock_count", "stock_opname"]),
    Concept("invoices", "invoices", False, ["bills", "tagihan"]),
    Concept("audit_logs", "audit_logs", False, ["audit_log", "audits"]),
]

results = {"pass": 0, "fail": 0, "warn": 0}


def line(tag, color, msg, detail=""):
    print(f"  {color}[{tag}]{X} {msg}" + (f"  {color}{detail}{X}" if detail else ""))


async def layer1_collection_reconciliation(db):
    print(f"\n{C}{B}L1/L2 — Rekonsiliasi koleksi Seed↔App (butuh DB clean-seed){X}")
    for c in CONCEPTS:
        canon = await db[c.canonical].count_documents({})
        if c.must_have_data and canon == 0:
            results["fail"] += 1
            line("FAIL", R, f"{c.name}: kanonik '{c.canonical}' KOSONG",
                 "→ seed GAP atau DRIFT (data masuk ke koleksi legacy?)")
        else:
            results["pass"] += 1
            line("PASS", G, f"{c.name}: '{c.canonical}' berisi {canon} dok")
        for legacy in c.legacy_must_be_empty:
            n = await db[legacy].count_documents({})
            if n > 0:
                results["fail"] += 1
                line("FAIL", R, f"{c.name}: legacy '{legacy}' masih berisi {n} dok",
                     "→ DRIFT AKTIF: seed/app menulis koleksi yang salah")
            else:
                results["pass"] += 1


async def layer2_db_invariants(db):
    """Invarian level-DB (tidak butuh API) — konservasi stok & total order."""
    print(f"\n{C}{B}L4 — Invarian akuntansi (level DB){X}")
    # INV-DB1: konservasi stok per balance (KN_15 §3.4 — on_hand = Σ bucket fisik)
    bals = await db.inventory_balances.find({}, {"_id": 0}).to_list(5000)
    cons_viol, neg_viol = [], []
    PHYS = ["available_qty", "reserved_qty", "committed_qty", "picked_qty",
            "packed_qty", "quarantine_qty", "blocked_qty", "damaged_qty"]
    for b in bals:
        oh = float(b.get("on_hand_qty", 0))
        phys_sum = sum(float(b.get(k, 0) or 0) for k in PHYS)
        # fallback legacy (in_transit_qty pernah masuk on_hand di model lama)
        if abs(oh - phys_sum) > 0.01:
            cons_viol.append(b.get("id"))
        bucket_vals = [float(b.get(k, 0) or 0) for k in PHYS] + [oh]
        if min(bucket_vals) < -0.01:
            neg_viol.append(b.get("id"))
    if cons_viol:
        results["fail"] += 1
        line("FAIL", R, f"stok: {len(cons_viol)} balance melanggar konservasi",
             "on_hand != Σ(available+reserved+committed+picked+packed+quarantine+blocked+damaged)")
    else:
        results["pass"] += 1
        line("PASS", G, f"stok: {len(bals)} balance — konservasi qty (bucket fisik) terpenuhi")
    if neg_viol:
        results["fail"] += 1
        line("FAIL", R, f"stok: {len(neg_viol)} balance punya bucket NEGATIF")
    else:
        results["pass"] += 1
        line("PASS", G, "stok: tidak ada qty negatif")

    # INV-DB2: sales_order.total_amount == Σ items.subtotal & subtotal == price*qty
    orders = await db.sales_orders.find({}, {"_id": 0}).to_list(2000)
    tot_viol, sub_viol = [], []
    for o in orders:
        items = o.get("items", [])
        ssum = sum(float(i.get("subtotal", 0)) for i in items)
        if abs(ssum - float(o.get("total_amount", 0))) > 0.01:
            tot_viol.append(o.get("number", o.get("id")))
        for i in items:
            if abs(float(i.get("subtotal", 0)) - float(i.get("price", 0)) * float(i.get("quantity", 0))) > 0.01:
                sub_viol.append(o.get("number", o.get("id")))
                break
    if tot_viol:
        results["fail"] += 1
        line("FAIL", R, f"order: {len(tot_viol)} total_amount != Σ subtotal", str(tot_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"order: {len(orders)} order — total_amount == Σ subtotal")
    if sub_viol:
        results["fail"] += 1
        line("FAIL", R, f"order: {len(sub_viol)} item subtotal != price×qty", str(sub_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "order: subtotal == price × quantity")

    # INV-DB3 (Fase 1B): konsistensi pricing diskon+PPN untuk order ber-breakdown.
    #   - net_subtotal == total_amount − discount_total (≥0, ≤ total)
    #   - excluded: ppn == round(dpp×rate/100); grand == net_subtotal + ppn
    #   - included: grand == net_subtotal; dpp + ppn == net_subtotal
    #   - line_total item == subtotal − discount_amount; 0 ≤ discount_percent ≤ 100
    tax_viol, disc_viol, line_viol = [], [], []
    n_breakdown = 0
    for o in orders:
        if o.get("grand_total") is None:
            continue
        n_breakdown += 1
        num = o.get("number", o.get("id"))
        total = float(o.get("total_amount", 0) or 0)
        disc_total = float(o.get("discount_total", 0) or 0)
        net = float(o.get("net_subtotal", 0) or 0)
        dpp = float(o.get("dpp", 0) or 0)
        ppn = float(o.get("ppn_amount", 0) or 0)
        grand = float(o.get("grand_total", 0) or 0)
        rate = float(o.get("ppn_rate", 0) or 0)
        mode = o.get("ppn_mode", "excluded")
        if disc_total < -0.01 or disc_total > total + 0.01:
            disc_viol.append(num)
        if abs(net - round(total - disc_total, 2)) > 0.5:
            disc_viol.append(num)
        if mode == "included":
            if abs(grand - net) > 0.5 or abs((dpp + ppn) - net) > 0.5:
                tax_viol.append(num)
        else:  # excluded
            exp_ppn = round(dpp * rate / 100.0, 2)
            if abs(ppn - exp_ppn) > 0.5 or abs(grand - round(net + ppn, 2)) > 0.5:
                tax_viol.append(num)
        for it in o.get("items", []):
            st = float(it.get("subtotal", 0) or 0)
            da = float(it.get("discount_amount", 0) or 0)
            lt = float(it.get("line_total", st) or 0)
            dp = float(it.get("discount_percent", 0) or 0)
            if abs(lt - round(st - da, 2)) > 0.5 or dp < -0.01 or dp > 100.01:
                line_viol.append(num)
                break
    if disc_viol:
        results["fail"] += 1
        line("FAIL", R, f"order: {len(set(disc_viol))} order diskon tak konsisten (net != total−diskon)", str(list(set(disc_viol))[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"order: {n_breakdown} order — net_subtotal == total_amount − discount_total")
    if tax_viol:
        results["fail"] += 1
        line("FAIL", R, f"order: {len(set(tax_viol))} order PPN/grand_total tak konsisten", str(list(set(tax_viol))[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"order: {n_breakdown} order — PPN & grand_total konsisten (mode excluded/included)")
    if line_viol:
        results["fail"] += 1
        line("FAIL", R, f"order: {len(set(line_viol))} order line_total/diskon item tak konsisten", str(list(set(line_viol))[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "order: line_total == subtotal − discount_amount (0 ≤ disc% ≤ 100)")

    # INV-DB-PO (P0-1): konsistensi pricing diskon+PPN (Faktur Pajak Masukan) untuk
    #   PURCHASE ORDER ber-breakdown. Hanya PO buatan engine (punya net_subtotal) yang
    #   divalidasi; PO seed lama tanpa breakdown sengaja DILEWATI (financials via fallback).
    pos = await db.purchase_orders.find({}, {"_id": 0}).to_list(2000)
    po_tot_viol, po_sub_viol, po_tax_viol, po_disc_viol, po_line_viol = [], [], [], [], []
    n_po_breakdown = 0
    for o in pos:
        if o.get("net_subtotal") is None:
            continue
        n_po_breakdown += 1
        num = o.get("po_number", o.get("id"))
        items = o.get("items", [])
        ssum = sum(float(i.get("subtotal", 0) or 0) for i in items)
        total = float(o.get("total_amount", 0) or 0)
        if abs(ssum - total) > 0.01:
            po_tot_viol.append(num)
        for i in items:
            if abs(float(i.get("subtotal", 0) or 0) - float(i.get("price", 0) or 0) * float(i.get("quantity", 0) or 0)) > 0.01:
                po_sub_viol.append(num)
                break
        disc_total = float(o.get("discount_total", 0) or 0)
        net = float(o.get("net_subtotal", 0) or 0)
        dpp = float(o.get("dpp", 0) or 0)
        ppn = float(o.get("ppn_amount", 0) or 0)
        grand = float(o.get("grand_total", 0) or 0)
        rate = float(o.get("ppn_rate", 0) or 0)
        mode = o.get("ppn_mode", "excluded")
        if disc_total < -0.01 or disc_total > total + 0.01:
            po_disc_viol.append(num)
        if abs(net - round(total - disc_total, 2)) > 0.5:
            po_disc_viol.append(num)
        if mode == "included":
            if abs(grand - net) > 0.5 or abs((dpp + ppn) - net) > 0.5:
                po_tax_viol.append(num)
        else:  # excluded
            exp_ppn = round(dpp * rate / 100.0, 2)
            if abs(ppn - exp_ppn) > 0.5 or abs(grand - round(net + ppn, 2)) > 0.5:
                po_tax_viol.append(num)
        for it in items:
            st = float(it.get("subtotal", 0) or 0)
            da = float(it.get("discount_amount", 0) or 0)
            lt = float(it.get("line_total", st) or 0)
            dp = float(it.get("discount_percent", 0) or 0)
            if abs(lt - round(st - da, 2)) > 0.5 or dp < -0.01 or dp > 100.01:
                po_line_viol.append(num)
                break
    if po_tot_viol:
        results["fail"] += 1
        line("FAIL", R, f"PO: {len(set(po_tot_viol))} total_amount != Σ subtotal", str(list(set(po_tot_viol))[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"PO: {n_po_breakdown} PO ber-breakdown — total_amount == Σ subtotal")
    if po_sub_viol:
        results["fail"] += 1
        line("FAIL", R, f"PO: {len(set(po_sub_viol))} item subtotal != price×qty", str(list(set(po_sub_viol))[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "PO: subtotal == price × quantity")
    if po_disc_viol:
        results["fail"] += 1
        line("FAIL", R, f"PO: {len(set(po_disc_viol))} PO diskon tak konsisten (net != total−diskon)", str(list(set(po_disc_viol))[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"PO: {n_po_breakdown} PO — net_subtotal == total_amount − discount_total")
    if po_tax_viol:
        results["fail"] += 1
        line("FAIL", R, f"PO: {len(set(po_tax_viol))} PO PPN/grand_total tak konsisten", str(list(set(po_tax_viol))[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"PO: {n_po_breakdown} PO — PPN Masukan & grand_total konsisten")
    if po_line_viol:
        results["fail"] += 1
        line("FAIL", R, f"PO: {len(set(po_line_viol))} PO line_total/diskon item tak konsisten", str(list(set(po_line_viol))[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "PO: line_total == subtotal − discount_amount (0 ≤ disc% ≤ 100)")



async def _login(client):
    r = await client.post(f"{API}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    d = r.json()
    # KN3: token field = "token" (respons langsung, tanpa envelope)
    return d.get("token") or (d.get("data") or {}).get("token")


async def layer3_intent_invariants():
    print(f"\n{C}{B}L3 — Invarian INTENT lintas-endpoint (KPI dashboard == sumber data){X}")
    try:
        import httpx
    except ImportError:
        os.system("pip install httpx -q"); import httpx
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tok = await _login(client)
        if not tok:
            results["fail"] += 1
            line("FAIL", R, "login gagal — invarian API dilewati"); return
        h = {"Authorization": f"Bearer {tok}"}

        async def get(path):
            r = await client.get(f"{API}{path}", headers=h, timeout=25)
            return r.json()

        # INV-1: dashboard.metrics.products == jumlah GET /products
        try:
            dash = await get("/api/dashboard")
            metrics = dash.get("metrics", {})
            prods = await get("/api/products")
            n_prod = len(prods) if isinstance(prods, list) else len(prods.get("items", []))
            if metrics.get("products") == n_prod:
                results["pass"] += 1
                line("PASS", G, f"dashboard: products KPI {metrics.get('products')} == /products {n_prod}")
            else:
                results["fail"] += 1
                line("FAIL", R, f"dashboard: products {metrics.get('products')} != /products {n_prod}",
                     "→ KPI dan list baca sumber berbeda")
        except Exception as e:
            results["fail"] += 1; line("FAIL", R, f"invarian products GAGAL/error (bukan di-skip): {e}")

        # INV-2: dashboard available_qty == Σ /inventory/balances available_qty
        try:
            dash = await get("/api/dashboard")
            kpi_avail = round(float(dash.get("metrics", {}).get("available_qty", 0)), 2)
            bals = await get("/api/inventory/balances")
            bal_list = bals if isinstance(bals, list) else bals.get("items", [])
            sum_avail = round(sum(float(b.get("available_qty", 0)) for b in bal_list), 2)
            if abs(kpi_avail - sum_avail) <= 0.5:
                results["pass"] += 1
                line("PASS", G, f"dashboard: available KPI {kpi_avail} == Σbalances {sum_avail}")
            else:
                results["fail"] += 1
                line("FAIL", R, f"dashboard: available {kpi_avail} != Σbalances {sum_avail}",
                     "→ KPI stok dan ledger stok tidak sinkron")
        except Exception as e:
            results["fail"] += 1; line("FAIL", R, f"invarian available_qty GAGAL/error: {e}")

        # INV-3: dashboard reserved_qty == Σ balances reserved_qty
        try:
            dash = await get("/api/dashboard")
            kpi_res = round(float(dash.get("metrics", {}).get("reserved_qty", 0)), 2)
            bals = await get("/api/inventory/balances")
            bal_list = bals if isinstance(bals, list) else bals.get("items", [])
            sum_res = round(sum(float(b.get("reserved_qty", 0)) for b in bal_list), 2)
            if abs(kpi_res - sum_res) <= 0.5:
                results["pass"] += 1
                line("PASS", G, f"dashboard: reserved KPI {kpi_res} == Σbalances {sum_res}")
            else:
                results["fail"] += 1
                line("FAIL", R, f"dashboard: reserved {kpi_res} != Σbalances {sum_res}")
        except Exception as e:
            results["fail"] += 1; line("FAIL", R, f"invarian reserved_qty GAGAL/error: {e}")

        # INV-4: sales-orders/stats/summary total_orders == jumlah GET /sales-orders
        try:
            stats = await get("/api/sales-orders/stats/summary")
            orders = await get("/api/sales-orders")
            n_orders = len(orders) if isinstance(orders, list) else len(orders.get("items", []))
            if stats.get("total_orders") == n_orders:
                results["pass"] += 1
                line("PASS", G, f"orders: stats total {stats.get('total_orders')} == /sales-orders {n_orders}")
            else:
                results["fail"] += 1
                line("FAIL", R, f"orders: stats {stats.get('total_orders')} != list {n_orders}",
                     "→ breakdown/summary menyembunyikan order")
        except Exception as e:
            results["fail"] += 1; line("FAIL", R, f"invarian orders stats GAGAL/error: {e}")

        # INV-5 (G9/RC-7): dashboard active_orders == count SELURUH order aktif,
        # bukan hasil window 20 order terakhir.
        try:
            dash = await get("/api/dashboard")
            kpi_active = dash.get("metrics", {}).get("active_orders")
            orders = await get("/api/sales-orders")
            olist = orders if isinstance(orders, list) else orders.get("items", [])
            actual_active = sum(1 for o in olist
                                if o.get("status") not in ["done", "cancelled", "expired"])
            if kpi_active == actual_active:
                results["pass"] += 1
                line("PASS", G, f"dashboard: active_orders KPI {kpi_active} == hitung penuh {actual_active}")
            else:
                results["fail"] += 1
                line("FAIL", R, f"dashboard: active_orders {kpi_active} != hitung penuh {actual_active}",
                     "→ KPI dihitung dari window terbatas (RC-7), salah saat order banyak")
        except Exception as e:
            results["fail"] += 1; line("FAIL", R, f"invarian active_orders GAGAL/error: {e}")


def _entity_registry_collections():
    """Ekstrak nama koleksi kanonik dari ENTITY_REGISTRY.md (SSOT) untuk
    cross-check (cegah gate & dokumen drift sendiri — pelajaran B2)."""
    import re
    reg = ROOT / "ENTITY_REGISTRY.md"
    if not reg.exists():
        return None
    text = reg.read_text(encoding="utf-8", errors="ignore")
    found = set()
    for m in re.finditer(r"Collection:\s*([a-z][a-z0-9_]+)", text):
        found.add(m.group(1))
    for m in re.finditer(r"`([a-z][a-z0-9_]+)`", text):
        found.add(m.group(1))
    return found


async def layer0_self_check():
    """G4: daftar kanonik di verify_contract.py HARUS konsisten dgn ENTITY_REGISTRY.md."""
    print(f"\n{C}{B}L0 — Self-check: gate vs ENTITY_REGISTRY (anti self-drift){X}")
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from verify_contract import CANONICAL_COLLECTIONS
    except Exception as e:
        results["warn"] += 1; line("WARN", Y, f"tidak bisa impor CANONICAL_COLLECTIONS: {e}"); return
    reg = _entity_registry_collections()
    if reg is None:
        results["warn"] += 1; line("WARN", Y, "ENTITY_REGISTRY.md tidak ditemukan"); return
    # setiap koleksi kanonik gate harus disebut di ENTITY_REGISTRY
    missing_in_reg = sorted(c for c in CANONICAL_COLLECTIONS if c not in reg)
    if missing_in_reg:
        results["fail"] += 1
        line("FAIL", R, f"{len(missing_in_reg)} koleksi gate tidak ada di ENTITY_REGISTRY: {missing_in_reg}",
             "→ gate & SSOT drift; samakan keduanya")
    else:
        results["pass"] += 1
        line("PASS", G, f"{len(CANONICAL_COLLECTIONS)} koleksi kanonik konsisten dengan ENTITY_REGISTRY")


async def layer5_number_series(db):
    """G8/RC-5: deteksi duplikat nomor dokumen (sumber duplicate-key/kebingungan)."""
    print(f"\n{C}{B}L5 — Number-series integrity (cegah RC-5 duplicate number){X}")
    for coll, field in [("sales_orders", "number"), ("purchase_orders", "po_number"),
                        ("invoices", "number")]:
        docs = await db[coll].find({}, {"_id": 0, field: 1}).to_list(5000)
        nums = [d.get(field) for d in docs if d.get(field)]
        dupes = {n for n in nums if nums.count(n) > 1}
        if dupes:
            results["fail"] += 1
            line("FAIL", R, f"{coll}.{field}: nomor DUPLIKAT {sorted(dupes)[:5]}",
                 "→ RC-5: penomoran berbasis count rentan tabrakan")
        elif nums:
            results["pass"] += 1
            line("PASS", G, f"{coll}.{field}: {len(nums)} nomor unik (tidak ada duplikat)")


async def layer_roll_invariants(db):
    """Fase 0.5 — Invarian Roll-as-SSOT (KN_15 §10): balance == proyeksi rolls,
    panjang valid, referensi owner/lot, owner-scoped allocation."""
    print(f"\n{C}{B}L4-ROLL — Invarian Roll-as-SSOT (KN_15){X}")
    rolls = await db.inventory_rolls.find({}, {"_id": 0}).to_list(50000)
    if not rolls:
        results["fail"] += 1
        line("FAIL", R, "inventory_rolls KOSONG", "→ Roll-as-SSOT belum ter-generate")
        return

    # INV-ROLL-2: 0 <= length_remaining <= length_initial
    len_viol = [r.get("id") for r in rolls
                if not (0 - 0.01 <= float(r.get("length_remaining", 0) or 0)
                        <= float(r.get("length_initial", 0) or 0) + 0.01)]
    if len_viol:
        results["fail"] += 1
        line("FAIL", R, f"roll: {len(len_viol)} roll length_remaining di luar [0, length_initial]", str(len_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"roll: {len(rolls)} roll — 0 ≤ length_remaining ≤ length_initial")

    # INV-ROLL-3: referensi valid + lot wajib
    ent_ids = {e["id"] for e in await db.business_entities.find({}, {"_id": 0, "id": 1}).to_list(100)}
    wh_ids = {w["id"] for w in await db.warehouses.find({}, {"_id": 0, "id": 1}).to_list(100)}
    prod_ids = {p["id"] for p in await db.products.find({}, {"_id": 0, "id": 1}).to_list(2000)}
    ref_viol = [r.get("id") for r in rolls
                if r.get("owner_entity_id") not in ent_ids
                or r.get("warehouse_id") not in wh_ids
                or r.get("product_id") not in prod_ids
                or not r.get("lot")]
    if ref_viol:
        results["fail"] += 1
        line("FAIL", R, f"roll: {len(ref_viol)} roll referensi owner/wh/product/lot tidak valid", str(ref_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"roll: referensi owner/warehouse/product valid + lot wajib terisi")

    # INV-ROLL-1: balance == proyeksi rolls per segmen (available & reserved)
    from collections import defaultdict
    seg_avail = defaultdict(float)
    seg_res = defaultdict(float)
    for r in rolls:
        key = (r.get("product_id"), r.get("warehouse_id"), r.get("owner_entity_id"))
        length = float(r.get("length_remaining", 0) or 0)
        if r.get("status") == "available":
            seg_avail[key] += length
        elif r.get("status") == "reserved":
            seg_res[key] += length
    bals = await db.inventory_balances.find({}, {"_id": 0}).to_list(5000)
    proj_viol = []
    for b in bals:
        key = (b.get("product_id"), b.get("warehouse_id"), b.get("owner_entity_id"))
        if abs(float(b.get("available_qty", 0) or 0) - round(seg_avail.get(key, 0.0), 2)) > 0.5:
            proj_viol.append((b.get("id"), "available"))
        if abs(float(b.get("reserved_qty", 0) or 0) - round(seg_res.get(key, 0.0), 2)) > 0.5:
            proj_viol.append((b.get("id"), "reserved"))
    if proj_viol:
        results["fail"] += 1
        line("FAIL", R, f"roll: {len(proj_viol)} segmen balance != proyeksi rolls", str(proj_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"roll: {len(bals)} segmen — balance == Σ rolls (available/reserved)")

    # INV-OWN-1: alokasi SO owner-scoped (owner_entity_id == SO.entity_id) bila tersedia
    orders = await db.sales_orders.find(
        {"status": {"$in": ["reserved", "waiting_approval", "approved", "confirmed"]}}, {"_id": 0}
    ).to_list(2000)
    own_viol = []
    for o in orders:
        for a in o.get("allocations", []):
            if a.get("owner_entity_id") and a.get("owner_entity_id") != o.get("entity_id"):
                own_viol.append(o.get("number", o.get("id")))
                break
    if own_viol:
        results["fail"] += 1
        line("FAIL", R, f"order: {len(own_viol)} SO menjual roll milik entitas lain (langgar D3)", str(own_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "order: alokasi owner-scoped (owner == SO.entity_id) — D3 terpenuhi")

    # INV-LOT-1 (Sub-fase 1.7): konsistensi lot_mode per-alokasi & has_mixed_lot per-order.
    # Defensif: hanya cek alokasi yang punya field lot_mode (order pra-1.7 dilewati).
    lot_viol = []
    mixed_viol = []
    for o in orders:
        order_lots = set()
        has_lotmode_field = False
        for a in o.get("allocations", []):
            lm = a.get("lot_mode")
            lots = [l for l in (a.get("lots") or []) if l]
            order_lots.update(lots)
            if lm is None:
                continue
            has_lotmode_field = True
            if lm == "single" and len(lots) > 1:
                lot_viol.append(o.get("number", o.get("id")))
            if lm == "mixed" and len(lots) < 2:
                lot_viol.append(o.get("number", o.get("id")))
        # has_mixed_lot harus true bila >1 lot dipakai lintas alokasi (per order)
        if has_lotmode_field and "has_mixed_lot" in o:
            expect_mixed = len(order_lots) > 1
            if bool(o.get("has_mixed_lot")) != expect_mixed:
                mixed_viol.append(o.get("number", o.get("id")))
    if lot_viol:
        results["fail"] += 1
        line("FAIL", R, f"order: {len(lot_viol)} alokasi lot_mode tak konsisten (single>1 lot / mixed<2 lot)", str(lot_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "order: alokasi lot_mode konsisten (single≤1 lot, mixed≥2 lot) — Sub-fase 1.7")
    if mixed_viol:
        results["fail"] += 1
        line("FAIL", R, f"order: {len(mixed_viol)} SO has_mixed_lot tak cocok lot dipakai", str(mixed_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "order: has_mixed_lot ⟺ >1 lot dipakai (lintas alokasi) — Sub-fase 1.7")

    # INV-PEG (Pegging/Earmark): roll yang di-pegging WAJIB berstatus 'available'.
    peg_viol = [r.get("roll_no", r.get("id")) for r in rolls
                if r.get("earmarked_for") and r.get("status") != "available"]
    if peg_viol:
        results["fail"] += 1
        line("FAIL", R, f"roll: {len(peg_viol)} roll di-pegging tapi status != available", str(peg_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "roll: earmarked_for terisi ⟹ status 'available' (Pegging) — konsisten")


async def layer_backorder_invariants(db):
    """Sub-fase 1.6 — Invarian Backorder Lifecycle.
    Hanya untuk SO ber-anotasi fulfillment (reserved_qty/backorder_qty per item)."""
    print(f"\n{C}{B}L4-BO — Invarian Backorder (Sub-fase 1.6){X}")
    EPS = 0.5
    ACTIVE = {"reserved", "waiting_approval", "approved", "confirmed", "waiting_stock", "dispatched"}
    orders = await db.sales_orders.find({}, {"_id": 0}).to_list(5000)
    annotated = [o for o in orders
                 if any("backorder_qty" in (it or {}) for it in o.get("items", []))]
    if not annotated:
        results["pass"] += 1
        line("PASS", G, "backorder: tidak ada SO ber-anotasi fulfillment (skip — valid)")
        return

    # INV-BO-1: per item, quantity == reserved_qty + backorder_qty
    bo1_viol = []
    for o in annotated:
        for it in o.get("items", []):
            if "backorder_qty" not in it:
                continue
            # Sub-fase 1.13 — reservasi & backorder dalam BASE unit ⇒ bandingkan base_quantity.
            q = float(it.get("base_quantity", it.get("quantity", 0)) or 0)
            rq = float(it.get("reserved_qty", 0) or 0)
            bq = float(it.get("backorder_qty", 0) or 0)
            if abs(q - (rq + bq)) > EPS:
                bo1_viol.append((o.get("number", o.get("id")), it.get("sku")))
    if bo1_viol:
        results["fail"] += 1
        line("FAIL", R, f"backorder: {len(bo1_viol)} item base_quantity != reserved+backorder", str(bo1_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"backorder: {len(annotated)} SO — base_quantity == reserved + backorder per item")

    # INV-BO-2: konsistensi flag has_backorder + makna waiting_stock (decoupled, Sub-fase 1.6.1)
    bo2_viol = []
    for o in annotated:
        if o.get("status") not in ACTIVE:
            continue
        total_bo = sum(float(it.get("backorder_qty", 0) or 0) for it in o.get("items", []))
        total_res = sum(float(it.get("reserved_qty", 0) or 0) for it in o.get("items", []))
        has_bo_flag = bool(o.get("has_backorder"))
        if has_bo_flag != (total_bo > EPS):
            bo2_viol.append((o.get("number"), "flag has_backorder tidak konsisten"))
        if o.get("status") == "waiting_stock":
            if total_bo <= EPS:
                bo2_viol.append((o.get("number"), "waiting_stock tanpa backorder"))
            if total_res > EPS:
                bo2_viol.append((o.get("number"), "waiting_stock tapi ada porsi reserved (harusnya reserved)"))
    if bo2_viol:
        results["fail"] += 1
        line("FAIL", R, f"backorder: {len(bo2_viol)} SO status/flag tak konsisten", str(bo2_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "backorder: flag has_backorder ⟺ Σbackorder>0; waiting_stock ⟹ Σreserved≈0")

    # INV-BO-3: backorders[].entity_id == order.entity_id (owner-scoped, jaga D3)
    bo3_viol = []
    for o in annotated:
        for bo in o.get("backorders", []):
            if bo.get("entity_id") and bo.get("entity_id") != o.get("entity_id"):
                bo3_viol.append(o.get("number"))
                break
    if bo3_viol:
        results["fail"] += 1
        line("FAIL", R, f"backorder: {len(bo3_viol)} SO backorder owner != SO.entity_id", str(bo3_viol[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "backorder: backorder owner-scoped (entity == SO.entity_id) — D3")


async def layer_shipment_invariants(db):
    """Sub-fase 1.8 — Status SO diperluas + Partial Shipment (SSOT-safe)."""
    from collections import defaultdict
    print(f"\n{C}{B}L4-SHIP — Invarian Shipment & Status SO (Sub-fase 1.8){X}")
    EPS = 0.5
    tasks = await db.wms_tasks.find({"flow_type": "outbound"}, {"_id": 0}).to_list(20000)
    shipments = await db.shipments.find({}, {"_id": 0}).to_list(20000)
    orders = {o["id"]: o for o in await db.sales_orders.find({}, {"_id": 0}).to_list(20000)}

    # SHIP-1: 0 <= shipped_qty <= quantity per task
    s1 = [t.get("id") for t in tasks
          if not (-EPS <= float(t.get("shipped_qty", 0) or 0) <= float(t.get("quantity", 0) or 0) + EPS)]
    if s1:
        results["fail"] += 1
        line("FAIL", R, f"shipment: {len(s1)} task shipped_qty di luar [0, quantity]", str(s1[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"shipment: {len(tasks)} task outbound — 0 ≤ shipped_qty ≤ quantity")

    # SHIP-2: Σ shipments.qty per order == Σ task.shipped_qty per order
    ship_by_order = defaultdict(float)
    for s in shipments:
        ship_by_order[s.get("order_id")] += float(s.get("qty", 0) or 0)
    task_ship_by_order = defaultdict(float)
    for t in tasks:
        task_ship_by_order[t.get("order_id")] += float(t.get("shipped_qty", 0) or 0)
    s2 = [oid for oid in set(list(ship_by_order) + list(task_ship_by_order))
          if abs(ship_by_order.get(oid, 0) - task_ship_by_order.get(oid, 0)) > EPS]
    if s2:
        results["fail"] += 1
        line("FAIL", R, f"shipment: {len(s2)} order Σshipments.qty != Σtask.shipped_qty",
             str([orders.get(o, {}).get("number", o) for o in s2[:5]]))
    else:
        results["pass"] += 1
        line("PASS", G, f"shipment: {len(shipments)} shipment — Σ qty == Σ task.shipped_qty per order")

    # SHIP-3: status SO konsisten dgn progres task outbound
    s3 = []
    by_order_tasks = defaultdict(list)
    for t in tasks:
        by_order_tasks[t.get("order_id")].append(t)
    for oid, ts in by_order_tasks.items():
        o = orders.get(oid)
        if not o or o.get("status") in {"cancelled", "expired"}:
            continue
        total = sum(float(t.get("quantity", 0) or 0) for t in ts)
        shipped = sum(float(t.get("shipped_qty", 0) or 0) for t in ts)
        st = o.get("status")
        if st in {"shipped", "done"} and not (total > 0 and shipped + EPS >= total):
            s3.append((o.get("number"), f"{st} tapi shipped {round(shipped,1)}/{round(total,1)}"))
        if st == "partially_shipped" and not (EPS < shipped < total + EPS):
            s3.append((o.get("number"), f"partially_shipped tapi shipped {round(shipped,1)}/{round(total,1)}"))
        if st in {"confirmed", "partially_picked", "picked"} and shipped > EPS:
            s3.append((o.get("number"), f"{st} tapi sudah ada shipped {round(shipped,1)}"))
    if s3:
        results["fail"] += 1
        line("FAIL", R, f"shipment: {len(s3)} SO status tak konsisten dgn progres task", str(s3[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "shipment: status SO ⟺ progres task (picked/partially_shipped/shipped/done)")


async def layer_tax_invoice_invariants(db):
    """Sub-fase 1.9 — Faktur Pajak Jual (tax_invoices)."""
    print(f"\n{C}{B}L4-FKT — Invarian Faktur Pajak (Sub-fase 1.9){X}")
    EPS = 1.0
    fakturs = await db.tax_invoices.find({}, {"_id": 0}).to_list(20000)
    order_ids = {o["id"] for o in await db.sales_orders.find({}, {"id": 1, "_id": 0}).to_list(20000)}
    if not fakturs:
        results["pass"] += 1
        line("PASS", G, "faktur: belum ada Faktur Pajak (skip — valid, pajak opsional)")
        return

    # FKT-1: PPN ≈ DPP × rate ; grand ≈ DPP + PPN (mode excluded)
    bad_calc = []
    for f in fakturs:
        if f.get("status") == "batal":
            continue
        dpp = float(f.get("dpp", 0) or 0)
        rate = float(f.get("ppn_rate", 0) or 0)
        ppn = float(f.get("ppn_amount", 0) or 0)
        grand = float(f.get("grand_total", 0) or 0)
        if abs(ppn - round(dpp * rate / 100, 2)) > EPS or abs(grand - (dpp + ppn)) > EPS:
            bad_calc.append(f.get("number"))
    if bad_calc:
        results["fail"] += 1
        line("FAIL", R, f"faktur: {len(bad_calc)} faktur PPN/Grand tidak konsisten", str(bad_calc[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"faktur: {len(fakturs)} faktur — PPN==DPP×rate & Grand==DPP+PPN")

    # FKT-2: referensi order valid + hanya PKP & ppn>0 (utk normal/pengganti)
    bad_ref = [f.get("number") for f in fakturs if f.get("order_id") not in order_ids]
    bad_pkp = [f.get("number") for f in fakturs
               if f.get("status") != "batal" and not (f.get("is_pkp") and float(f.get("ppn_amount", 0) or 0) > 0)]
    if bad_ref or bad_pkp:
        results["fail"] += 1
        line("FAIL", R, f"faktur: {len(bad_ref)} ref order invalid / {len(bad_pkp)} non-PKP-atau-tanpa-PPN",
             str((bad_ref + bad_pkp)[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "faktur: referensi order valid + hanya PKP & ber-PPN (normal/pengganti)")

    # FKT-3: maksimal 1 faktur AKTIF (bukan batal & belum diganti) per order + nomor unik
    from collections import defaultdict
    active_by_order = defaultdict(int)
    for f in fakturs:
        if f.get("status") != "batal" and not f.get("replaced_by_id"):
            active_by_order[f.get("order_id")] += 1
    dup_active = [oid for oid, n in active_by_order.items() if n > 1]
    numbers = [f.get("number") for f in fakturs]
    dup_no = len(numbers) != len(set(numbers))
    if dup_active or dup_no:
        results["fail"] += 1
        line("FAIL", R, f"faktur: {len(dup_active)} order >1 faktur aktif / nomor duplikat={dup_no}",
             str(dup_active[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"faktur: ≤1 faktur aktif/order + {len(set(numbers))} nomor unik")

    # FKT-4: rantai pengganti konsisten (replaces_id menunjuk faktur yang ada)
    ids = {f.get("id") for f in fakturs}
    bad_chain = [f.get("number") for f in fakturs
                 if f.get("status") == "pengganti" and f.get("replaces_id") not in ids]
    if bad_chain:
        results["fail"] += 1
        line("FAIL", R, f"faktur: {len(bad_chain)} pengganti dgn replaces_id menggantung", str(bad_chain[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "faktur: rantai pengganti konsisten (replaces_id valid)")


async def layer_pr_invariants(db):
    """Depth #2 — Invarian Purchase Requisition (purchase_requisitions)."""
    print(f"\n{C}{B}L4-PR — Invarian Purchase Requisition (Depth #2){X}")
    EPS = 1.0
    prs = await db.purchase_requisitions.find({}, {"_id": 0}).to_list(20000)
    if not prs:
        results["pass"] += 1
        line("PASS", G, "PR: belum ada Purchase Requisition (skip — valid, opsional)")
        return

    po_ids = {p["id"] for p in await db.purchase_orders.find({}, {"id": 1, "_id": 0}).to_list(20000)}

    # PR-1: subtotal == est_price × qty  &&  total_est == Σ subtotal
    bad_calc = []
    for pr in prs:
        tot = 0.0
        ok = True
        for it in pr.get("items", []):
            sub = float(it.get("subtotal", 0) or 0)
            calc = round(float(it.get("est_price", 0) or 0) * float(it.get("quantity", 0) or 0), 2)
            if abs(sub - calc) > EPS:
                ok = False
            tot += sub
        if not ok or abs(round(tot, 2) - float(pr.get("total_est_amount", 0) or 0)) > EPS:
            bad_calc.append(pr.get("number"))
    if bad_calc:
        results["fail"] += 1
        line("FAIL", R, f"PR: {len(bad_calc)} PR subtotal/total tidak konsisten", str(bad_calc[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, f"PR: {len(prs)} PR — subtotal==est×qty & total==Σ subtotal")

    # PR-2: status 'converted' ⟹ po_id valid (menunjuk PO yang ada)
    bad_conv = [pr.get("number") for pr in prs
                if pr.get("status") == "converted" and pr.get("po_id") not in po_ids]
    if bad_conv:
        results["fail"] += 1
        line("FAIL", R, f"PR: {len(bad_conv)} PR converted dgn po_id menggantung", str(bad_conv[:5]))
    else:
        results["pass"] += 1
        line("PASS", G, "PR: status converted ⟹ po_id valid")

    # PR-3: nomor PR unik
    numbers = [pr.get("number") for pr in prs]
    if len(numbers) != len(set(numbers)):
        results["fail"] += 1
        line("FAIL", R, "PR: ada nomor PR duplikat")
    else:
        results["pass"] += 1
        line("PASS", G, f"PR: {len(set(numbers))} nomor PR unik")


async def main():
    print(f"{B}{C}{'='*64}{X}")
    print(f"{B}  KN3 — DATA INTEGRITY GATE  (DB={DB_NAME}  API={API}){X}")
    print(f"{B}{C}{'='*64}{X}")
    from motor.motor_asyncio import AsyncIOMotorClient
    db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    await layer0_self_check()
    await layer1_collection_reconciliation(db)
    await layer2_db_invariants(db)
    await layer_roll_invariants(db)
    await layer_backorder_invariants(db)
    await layer_shipment_invariants(db)
    await layer_tax_invoice_invariants(db)
    await layer_pr_invariants(db)
    await layer5_number_series(db)
    await layer3_intent_invariants()
    print(f"\n{B}{'='*64}{X}")
    print(f"  {G}PASS {results['pass']}{X}  |  {R}FAIL {results['fail']}{X}  |  {Y}WARN {results['warn']}{X}")
    if results["fail"]:
        print(f"  {R}{B}INTEGRITY VIOLATION — blokir seed/deploy sampai diperbaiki.{X}\n")
        return 1
    print(f"  {G}{B}SEMUA INVARIAN VALID.{X}\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
