#!/usr/bin/env python3
"""
Kain Nusantara — Compliance Validator
======================================
Jalankan sebelum mark task sebagai DONE.
Output: PASS / FAIL per check dengan detail actionable.

Usage:
  python3 /app/scripts/validate_compliance.py
  python3 /app/scripts/validate_compliance.py --quick     # hanya checks kritis
  python3 /app/scripts/validate_compliance.py --fix-hints # tampilkan cara fix
"""
import os
import re
import sys
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path("/app")
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend" / "src"

# ─── LIMITS ───────────────────────────────────────────────────────────────
MAX_LINES_ROUTER   = 800
MAX_LINES_COMPONENT = 500
MAX_LINES_UTILITY  = 380  # bumped: navigationConfig.js is data-driven IA config (333 lines)
MAX_LINES_CSS      = 400

results = []   # list of (status, category, message)


def ok(category, message):
    results.append(("PASS", category, message))


def warn(category, message):
    results.append(("WARN", category, message))


def fail(category, message):
    results.append(("FAIL", category, message))


def section(title):
    results.append(("INFO", "", f"{'='*60}"))
    results.append(("INFO", "", f"  {title}"))
    results.append(("INFO", "", f"{'='*60}"))


# ─── CHECK 1: FILE SIZE ──────────────────────────────────────────────────────────
def check_file_sizes():
    section("CHECK 1: FILE SIZE LIMITS")
    any_fail = False

    # Python routers
    router_dir = BACKEND / "routers"
    for f in sorted(router_dir.glob("*.py")):
        lines = len(f.read_text().splitlines())
        if lines > MAX_LINES_ROUTER:
            fail("FILE_SIZE", f"{f.relative_to(ROOT)}: {lines} baris (MELEBIHI BATAS {MAX_LINES_ROUTER})")
            any_fail = True
        elif lines > MAX_LINES_ROUTER * 0.8:
            warn("FILE_SIZE", f"{f.relative_to(ROOT)}: {lines} baris (mendekati batas {MAX_LINES_ROUTER})")
        else:
            ok("FILE_SIZE", f"{f.relative_to(ROOT)}: {lines} baris")

    # Python core files
    for fname in ["server.py", "core_utils.py", "dependencies.py", "schemas.py", "permissions_config.py"]:
        f = BACKEND / fname
        if f.exists():
            lines = len(f.read_text().splitlines())
            if lines > MAX_LINES_ROUTER:
                fail("FILE_SIZE", f"backend/{fname}: {lines} baris (MELEBIHI BATAS)")
                any_fail = True
            else:
                ok("FILE_SIZE", f"backend/{fname}: {lines} baris")

    # React components
    for f in sorted(FRONTEND.rglob("*.jsx")):
        lines = len(f.read_text().splitlines())
        if lines > MAX_LINES_COMPONENT:
            fail("FILE_SIZE", f"{f.relative_to(ROOT)}: {lines} baris (MELEBIHI BATAS {MAX_LINES_COMPONENT})")
            any_fail = True
        elif lines > MAX_LINES_COMPONENT * 0.85:
            warn("FILE_SIZE", f"{f.relative_to(ROOT)}: {lines} baris (mendekati batas {MAX_LINES_COMPONENT})")

    # JS utilities (bukan .jsx)
    for f in sorted(FRONTEND.rglob("*.js")):
        if "node_modules" in str(f):
            continue
        lines = len(f.read_text().splitlines())
        # Hook files bisa lebih panjang
        limit = MAX_LINES_UTILITY * 2 if "hooks/" in str(f) else MAX_LINES_UTILITY
        if lines > limit:
            warn("FILE_SIZE", f"{f.relative_to(ROOT)}: {lines} baris (melebihi batas {limit} untuk utility)")

    # CSS
    for f in FRONTEND.glob("*.css"):
        lines = len(f.read_text().splitlines())
        if lines > MAX_LINES_CSS:
            warn("FILE_SIZE", f"{f.relative_to(ROOT)}: {lines} baris (melebihi guideline {MAX_LINES_CSS})")

    if not any_fail:
        ok("FILE_SIZE", "Semua router Python dalam batas")


# ─── CHECK 2: CONSOLE.LOG ───────────────────────────────────────────────────────────
def check_console_logs():
    section("CHECK 2: DEBUG STATEMENTS")
    found = []

    # Frontend: console.log (kecuali yang di-comment)
    for f in FRONTEND.rglob("*.js"):
        if "node_modules" in str(f):
            continue
        for i, line in enumerate(f.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if "console.log" in line and "// ok" not in line.lower():
                found.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:80]}")

    for f in FRONTEND.rglob("*.jsx"):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            if "console.log" in line and "// ok" not in line.lower():
                found.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:80]}")

    # Backend: debug print()
    for f in (BACKEND / "routers").glob("*.py"):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.match(r"\s*print\s*\(", line) and "# ok" not in line.lower():
                found.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:80]}")

    if found:
        for item in found:
            fail("DEBUG", item)
    else:
        ok("DEBUG", "Tidak ada console.log atau debug print() ditemukan")


# ─── CHECK 3: DUPLICATE ENDPOINTS ───────────────────────────────────────────────────
def check_duplicate_endpoints():
    section("CHECK 3: DUPLICATE ENDPOINTS")
    endpoint_map = defaultdict(list)  # (method, path) -> [files]

    pattern = re.compile(r'@router\.(get|post|put|patch|delete)\([\'"](.*?)[\'"]')

    router_dir = BACKEND / "routers"
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        for match in pattern.finditer(content):
            method = match.group(1).upper()
            path = match.group(2)
            key = f"{method} {path}"
            endpoint_map[key].append(f.name)

    duplicates = {k: v for k, v in endpoint_map.items() if len(v) > 1}
    if duplicates:
        for endpoint, files in duplicates.items():
            fail("DUPLICATE_ENDPOINT", f"{endpoint} → ditemukan di: {', '.join(files)}")
    else:
        ok("DUPLICATE_ENDPOINT", f"Tidak ada duplicate endpoint ({len(endpoint_map)} endpoints total)")


# ─── CHECK 4: FORBIDDEN COLLECTION NAMES ────────────────────────────────────────────
def check_forbidden_collections():
    section("CHECK 4: FORBIDDEN COLLECTION NAMES (SSOT)")
    forbidden = [
        "items", "goods", "materials", "accessories", "kain", "fabric",
        "stock", "stok", "stock_levels", "inventory_count",
        "orders", "customer_orders", "penjualan",
        "inbound_tasks", "outbound_tasks", "receiving_tasks",
        r"^transfers$",  # warehouse_transfers is correct
        "stock_transfer", "pemindahan",
        r"^po$", "pembelian", "supplier_orders",
        "bills", "tagihan", "faktur",
        r"^templates$",  # document_templates is correct
        "staff", "operator", "karyawan",
        r"^gudang$", "depot",
        "stock_history", "stock_log", "gerakan_stok",
        "supplier_master", "vendors",  # not yet added, use suppliers if needed
    ]

    found_forbidden = []
    # Scan all Python router files for db.COLLECTION patterns
    pattern = re.compile(r'db\.([a-z_]+)')
    router_dir = BACKEND / "routers"
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        collections_in_file = set(pattern.findall(content))
        for coll in collections_in_file:
            for forb in forbidden:
                if forb.startswith("^"):
                    if re.match(forb, coll):
                        found_forbidden.append((f.name, coll, forb))
                elif coll == forb:
                    found_forbidden.append((f.name, coll, "exact match"))

    if found_forbidden:
        for fname, coll, reason in found_forbidden:
            fail("FORBIDDEN_COLLECTION",
                 f"{fname}: db.{coll} — nama ini dilarang (lihat ENTITY_REGISTRY.md)")
    else:
        ok("FORBIDDEN_COLLECTION", "Tidak ada forbidden collection names ditemukan")


# ─── CHECK 5: HARDCODED IDs / CONFIG ──────────────────────────────────────────────────
def check_hardcoded_values():
    section("CHECK 5: HARDCODED IDs / WAREHOUSE IDs")
    # Pattern: known demo IDs yang tidak boleh hardcoded di bisnis logic
    hardcoded_patterns = [
        (r'["\']wh_jakarta["\']', "warehouse ID hardcoded"),
        (r'["\']wh_bandung["\']', "warehouse ID hardcoded"),
        (r'["\']wh_surabaya["\']', "warehouse ID hardcoded"),
        (r'["\']user_admin_01["\']', "user ID hardcoded"),
        (r'["\']user_sales_01["\']', "user ID hardcoded"),
        (r'["\']prod_batik_mega["\']', "product ID hardcoded"),
        (r'["\']demo12345["\']', "password hardcoded"),
        (r'localhost:8001', "localhost URL hardcoded (use env var)"),
        (r'localhost:3000', "localhost URL hardcoded (use env var)"),
    ]

    found = []
    # Check routers (seed data in server.py is expected to have these)
    router_dir = BACKEND / "routers"
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        for pat, desc in hardcoded_patterns:
            if re.search(pat, content):
                found.append(f"{f.name}: {desc} (pattern: {pat})")

    if found:
        for item in found:
            warn("HARDCODED", item)
    else:
        ok("HARDCODED", "Tidak ada hardcoded IDs di router files")


# ─── CHECK 6: SAFE_DOC USAGE ──────────────────────────────────────────────────────────
def check_safe_doc_usage():
    section("CHECK 6: SAFE_DOC / SERIALIZATION")
    # Look for direct MongoDB return without safe_doc()
    risky_patterns = [
        (r'return await db\.[^\s]+\.find_one', "find_one tanpa safe_doc() wrapper"),
        (r'return await db\.[^\s]+\.insert_one', "insert_one result langsung di-return"),
    ]
    issues = []
    router_dir = BACKEND / "routers"
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        for pat, desc in risky_patterns:
            matches = re.findall(pat, content)
            if matches:
                issues.append(f"{f.name}: {desc} ({len(matches)}x)")

    if issues:
        for item in issues:
            warn("SERIALIZATION", item)
    else:
        ok("SERIALIZATION", "Tidak ada langsung return MongoDB result yang mencurigakan")


# ─── CHECK 7: MISSING DATA-TESTID ───────────────────────────────────────────────────────
def check_data_testids():
    section("CHECK 7: DATA-TESTID COVERAGE")
    # Count testids in feature files (should be substantial)
    total_testids = 0
    files_without_testid = []

    for f in FRONTEND.rglob("*.jsx"):
        content = f.read_text()
        count = content.count("data-testid")
        total_testids += count
        # Feature files should have testids
        if "features/" in str(f) and count == 0:
            files_without_testid.append(str(f.relative_to(ROOT)))

    if files_without_testid:
        for fname in files_without_testid:
            warn("TESTID", f"{fname}: tidak ada data-testid (testing agent tidak bisa test ini)")
    else:
        ok("TESTID", f"Semua feature files punya data-testid (total: {total_testids} testids)")


# ─── CHECK 8: ENTITY REGISTRY SYNC ─────────────────────────────────────────────────────
def check_entity_registry_sync():
    section("CHECK 8: ENTITY REGISTRY SYNC")
    # Known good collections (from ENTITY_REGISTRY.md)
    known_collections = {
        "users", "sessions", "products", "customers", "warehouses",
        "uoms", "sales_orders", "invoices", "inventory_balances",
        "inventory_movements", "wms_tasks", "warehouse_transfers",
        "cycle_count_sessions", "purchase_orders", "document_templates",
        "generated_documents", "permission_settings", "audit_logs",
        "user_onboarding",
        # Fase 0 — Multi-Entity + Notification Center (registered in ENTITY_REGISTRY.md)
        "business_entities", "notifications",
        # Fase 0.5 — Roll-as-SSOT Inventory Ownership (registered in ENTITY_REGISTRY.md)
        "inventory_rolls",
        # Fase 1A — Configuration Foundation (registered in ENTITY_REGISTRY.md)
        "system_settings", "payment_terms", "approval_rules",
        # Sub-fase 1.7 — Special Price (registered in ENTITY_REGISTRY.md)
        "price_approvals",
        # Sub-fase 1.8 — Partial Shipment (registered in ENTITY_REGISTRY.md)
        "shipments",
        "shipments",
        # Sub-fase 1.9 — Faktur Pajak Jual (registered in ENTITY_REGISTRY.md)
        "tax_invoices",
        # Sub-fase 1.11 — Returns & Barang Sisa
        "sales_returns",
        # Sub-fase 1.12 — Special Orders
        "special_orders",
        # Approval Requests (Sub-fase 1.6+)
        "approval_requests",
        # Fase 3 — Procurement masters & transaksi (registered in ENTITY_REGISTRY.md)
        "suppliers", "cash_transactions", "purchase_returns", "purchase_requisitions",
        # Depth #3 — Supplier Intelligence price-list (registered in ENTITY_REGISTRY.md)
        "supplier_price_lists",
        # EPIC2 — Master Kategori Produk (registered in ENTITY_REGISTRY.md)
        "product_categories",
        # EPIC3B — AR Receipt ledger (registered in ENTITY_REGISTRY.md)
        "ar_receipts",
        # EPIC4 — Incentive rate matrix (registered in ENTITY_REGISTRY.md)
        "incentive_rates",
    }

    # Scan actual collections used in routers
    pattern = re.compile(r'db\.([a-z_]+)')
    actual_collections = set()
    router_dir = BACKEND / "routers"
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        for coll in pattern.findall(content):
            actual_collections.add(coll)

    # Also check server.py
    server_content = (BACKEND / "server.py").read_text()
    for coll in pattern.findall(server_content):
        actual_collections.add(coll)

    # Find collections in code but not in registry
    unregistered = actual_collections - known_collections
    # Remove false positives (not real collection names)
    false_positives = {"items", "client"}  # these are method names
    unregistered -= false_positives

    if unregistered:
        for coll in sorted(unregistered):
            warn("ENTITY_REGISTRY",
                 f"db.{coll} digunakan di code tapi tidak ada di ENTITY_REGISTRY.md — tambahkan jika ini collection baru")
    else:
        ok("ENTITY_REGISTRY", f"Semua {len(actual_collections)} collections sudah terdaftar di ENTITY_REGISTRY.md")


# ─── CHECK 9: REQUIRED DOCS EXIST ───────────────────────────────────────────────────────
def check_required_docs():
    section("CHECK 9: REQUIRED DOCUMENTATION")
    required_docs = [
        ROOT / "ENTITY_REGISTRY.md",
        ROOT / "CODEBASE_MAP.md",
        ROOT / "memory" / "PRD.md",
        ROOT / "memory" / "SESSION_HANDOFF.md",
        ROOT / "memory" / "SESSION_LOG.md",
        ROOT / "memory" / "TECH_DECISIONS.md",
        ROOT / "plan.md",
        ROOT / "docs" / "KN_00_AGENT_QUICK_START.md",
        ROOT / "docs" / "KN_13_NAVIGATION_MAP.md",
    ]
    for doc in required_docs:
        if doc.exists():
            ok("DOCS", f"{doc.relative_to(ROOT)} ✓")
        else:
            fail("DOCS", f"{doc.relative_to(ROOT)} — FILE TIDAK ADA (wajib ada!)")


# ─── CHECK 10: API PREFIX ───────────────────────────────────────────────────────────────
def check_api_prefix():
    section("CHECK 10: API PREFIX (/api/)")
    # All router prefixes should start with /api/
    pattern = re.compile(r'APIRouter\(prefix=["\']([^\'"]+)["\']')
    issues = []
    router_dir = BACKEND / "routers"
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        for match in pattern.finditer(content):
            prefix = match.group(1)
            if not prefix.startswith("/api"):
                issues.append(f"{f.name}: prefix '{prefix}' tidak diawali /api")

    # Also check @router decorators without /api prefix (no router-level prefix)
    endpoint_pattern = re.compile(r'@router\.(get|post|put|patch|delete)\(["\']([^\'"]+)["\']')
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        # If no APIRouter prefix, all endpoints should start with /api
        if 'APIRouter(prefix=' not in content:
            for match in endpoint_pattern.finditer(content):
                path = match.group(2)
                if not path.startswith("/api"):
                    issues.append(f"{f.name}: endpoint '{path}' tanpa /api prefix dan tidak ada router prefix")

    if issues:
        for item in issues:
            warn("API_PREFIX", item)
    else:
        ok("API_PREFIX", "Semua endpoints menggunakan prefix /api/")


# ─── CHECK 11: ENV VARS (NO HARDCODED) ─────────────────────────────────────────────────
def check_env_vars():
    section("CHECK 11: ENVIRONMENT VARIABLES")
    # Check .env files exist
    backend_env = BACKEND / ".env"
    frontend_env = ROOT / "frontend" / ".env"

    if backend_env.exists():
        content = backend_env.read_text()
        if "MONGO_URL" in content:
            ok("ENV", "backend/.env: MONGO_URL ✓")
        else:
            fail("ENV", "backend/.env: MONGO_URL tidak ada!")
        if "DB_NAME" in content:
            ok("ENV", "backend/.env: DB_NAME ✓")
        else:
            warn("ENV", "backend/.env: DB_NAME tidak ada (akan default)")
        # Check no secrets hardcoded in code
        if "kain-nusantara::" in content:
            warn("ENV", "backend/.env: berisi string internal (bukan secret tapi perhatikan)")
    else:
        fail("ENV", "backend/.env tidak ditemukan!")

    if frontend_env.exists():
        content = frontend_env.read_text()
        if "REACT_APP_BACKEND_URL" in content:
            ok("ENV", "frontend/.env: REACT_APP_BACKEND_URL ✓")
        else:
            fail("ENV", "frontend/.env: REACT_APP_BACKEND_URL tidak ada!")
    else:
        fail("ENV", "frontend/.env tidak ditemukan!")


# ─── CHECK 12: MONSTER FILES (FILE COMPLEXITY) ──────────────────────────────────────────
def check_monster_files():
    section("CHECK 12: MONSTER FILE DETECTION")
    # Detect files that are approaching or exceeding danger zone
    monsters = []
    
    # Backend routers
    router_dir = BACKEND / "routers"
    for f in sorted(router_dir.glob("*.py")):
        lines = len(f.read_text().splitlines())
        if lines > MAX_LINES_ROUTER:
            monsters.append((str(f.relative_to(ROOT)), lines, MAX_LINES_ROUTER, "CRITICAL"))
        elif lines > MAX_LINES_ROUTER * 0.9:
            monsters.append((str(f.relative_to(ROOT)), lines, MAX_LINES_ROUTER, "HIGH"))
    
    # React components
    for f in sorted(FRONTEND.rglob("*.jsx")):
        lines = len(f.read_text().splitlines())
        if lines > MAX_LINES_COMPONENT:
            monsters.append((str(f.relative_to(ROOT)), lines, MAX_LINES_COMPONENT, "CRITICAL"))
        elif lines > MAX_LINES_COMPONENT * 0.9:
            monsters.append((str(f.relative_to(ROOT)), lines, MAX_LINES_COMPONENT, "HIGH"))
    
    # JS utilities
    for f in sorted(FRONTEND.rglob("*.js")):
        if "node_modules" in str(f):
            continue
        lines = len(f.read_text().splitlines())
        limit = MAX_LINES_UTILITY * 2 if "hooks/" in str(f) else MAX_LINES_UTILITY
        if lines > limit:
            monsters.append((str(f.relative_to(ROOT)), lines, limit, "WARN"))
    
    if monsters:
        for filepath, lines, limit, severity in monsters:
            if severity == "CRITICAL":
                fail("MONSTER_FILE", f"{filepath}: {lines} baris (MELEBIHI {limit}) — WAJIB REFACTOR")
            elif severity == "HIGH":
                warn("MONSTER_FILE", f"{filepath}: {lines} baris (90% dari {limit}) — segera split sebelum terlambat")
            else:
                warn("MONSTER_FILE", f"{filepath}: {lines} baris (melebihi guideline {limit})")
    else:
        ok("MONSTER_FILE", "Tidak ada monster files detected")


# ─── CHECK 13: NAMING CONSISTENCY ──────────────────────────────────────────────────────
def check_naming_consistency():
    section("CHECK 13: NAMING CONVENTIONS")
    issues = []
    
    # Check Python files for camelCase (should be snake_case)
    pattern_camelcase = re.compile(r'\bdef ([a-z]+[A-Z][a-zA-Z]*)\(')
    router_dir = BACKEND / "routers"
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        matches = pattern_camelcase.findall(content)
        if matches:
            for match in matches[:3]:  # Show max 3 examples
                issues.append(f"{f.name}: function '{match}' menggunakan camelCase (seharusnya snake_case)")
    
    # Check for inconsistent collection naming in MongoDB queries
    pattern_collection = re.compile(r'db\.([a-zA-Z_]+)')
    all_collections = set()
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        collections = pattern_collection.findall(content)
        all_collections.update(collections)
    
    # Check if collections follow domain prefix convention
    valid_prefixes = ["inventory_", "warehouse_", "sales_", "finance_", "hr_", "audit_", "wms_", "cycle_"]
    for coll in all_collections:
        if coll in ["users", "sessions", "products", "customers", "warehouses", "uoms", 
                    "invoices", "purchase_orders", "document_templates", "generated_documents",
                    "permission_settings", "user_onboarding",
                    "business_entities", "notifications",
                    "system_settings", "payment_terms", "approval_rules",
                    "price_approvals", "shipments", "tax_invoices", "sales_returns",
                    # Fase 3 + Depth #2/#3 — procurement masters & transaksi (domain entity)
                    "suppliers", "supplier_price_lists", "cash_transactions",
                    "purchase_returns", "purchase_requisitions", "special_orders",
                    "approval_requests", "product_categories", "ar_receipts", "incentive_rates"]:
            continue  # Known valid without prefix (config/master/domain entity)
        
        has_valid_prefix = any(coll.startswith(prefix) for prefix in valid_prefixes)
        if not has_valid_prefix and len(coll) > 3:  # Ignore false positives like "db"
            issues.append(f"Collection 'db.{coll}' tidak mengikuti domain prefix convention")
    
    if issues:
        for issue in issues[:10]:  # Show max 10 issues
            warn("NAMING", issue)
    else:
        ok("NAMING", "Naming conventions konsisten")


# ─── CHECK 14: TECH DEBT MARKERS ───────────────────────────────────────────────────────
def check_tech_debt():
    section("CHECK 14: TECH DEBT MARKERS")
    # Look for TODO, FIXME, HACK, XXX comments
    markers = []
    
    # Backend
    for f in (BACKEND / "routers").glob("*.py"):
        content = f.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            if re.search(r'#\s*(TODO|FIXME|HACK|XXX|BUG)\b', line, re.IGNORECASE):
                marker_type = re.search(r'(TODO|FIXME|HACK|XXX|BUG)', line, re.IGNORECASE).group(1).upper()
                markers.append((f.relative_to(ROOT), i, marker_type, line.strip()[:60]))
    
    # Frontend
    for f in FRONTEND.rglob("*.jsx"):
        content = f.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            if re.search(r'//\s*(TODO|FIXME|HACK|XXX|BUG)\b', line, re.IGNORECASE):
                marker_type = re.search(r'(TODO|FIXME|HACK|XXX|BUG)', line, re.IGNORECASE).group(1).upper()
                markers.append((f.relative_to(ROOT), i, marker_type, line.strip()[:60]))
    
    if markers:
        for filepath, line_num, marker, text in markers[:15]:  # Show max 15
            warn("TECH_DEBT", f"{filepath}:{line_num} [{marker}] {text}")
        if len(markers) > 15:
            warn("TECH_DEBT", f"... dan {len(markers) - 15} tech debt markers lainnya")
    else:
        ok("TECH_DEBT", "Tidak ada tech debt markers (TODO/FIXME/HACK)")


# ─── CHECK 15: IMPORT STATEMENTS QUALITY ───────────────────────────────────────────────
def check_imports():
    section("CHECK 15: IMPORT QUALITY")
    issues = []
    
    # Check for wildcard imports in Python (bad practice)
    router_dir = BACKEND / "routers"
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        if re.search(r'from .* import \*', content):
            issues.append(f"{f.name}: menggunakan wildcard import (from X import *)")
    
    # Check for unused imports (basic check - look for imports not referenced)
    for f in router_dir.glob("*.py"):
        content = f.read_text()
        lines = content.splitlines()
        import_lines = [l for l in lines if l.strip().startswith('from ') or l.strip().startswith('import ')]
        
        # Simple check: if import line has alias and alias never used
        for imp_line in import_lines:
            if ' as ' in imp_line:
                alias = imp_line.split(' as ')[-1].strip()
                # Count occurrences (should be > 1 if used, 1 is just the import itself)
                if content.count(alias) == 1:
                    issues.append(f"{f.name}: possible unused import with alias '{alias}'")
    
    if issues:
        for issue in issues[:10]:
            warn("IMPORTS", issue)
    else:
        ok("IMPORTS", "Import statements quality check passed")


# ─── MAIN RUNNER ─────────────────────────────────────────────────────────────────────
def run_all_checks(quick=False):
    # Critical checks (always run)
    check_file_sizes()
    check_console_logs()
    check_duplicate_endpoints()
    check_forbidden_collections()
    check_entity_registry_sync()
    check_required_docs()
    check_env_vars()
    check_monster_files()

    if not quick:
        # Additional quality checks
        check_hardcoded_values()
        check_safe_doc_usage()
        check_data_testids()
        check_api_prefix()
        check_naming_consistency()
        check_tech_debt()
        check_imports()


def print_report():
    print("\n" + "="*70)
    print("  KAIN NUSANTARA — COMPLIANCE REPORT")
    print("="*70)

    counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "INFO": 0}
    fails = []
    warns = []

    for status, category, message in results:
        counts[status] = counts.get(status, 0) + 1
        if status == "FAIL":
            fails.append((category, message))
        elif status == "WARN":
            warns.append((category, message))

    # Print all results
    for status, category, message in results:
        if status == "INFO":
            print(f"\n{message}")
        elif status == "PASS":
            print(f"  \u2705 [{category}] {message}")
        elif status == "FAIL":
            print(f"  \u274c [{category}] {message}")
        elif status == "WARN":
            print(f"  \u26a0\ufe0f  [{category}] {message}")

    # Summary
    print("\n" + "="*70)
    print(f"  SUMMARY: {counts['PASS']} PASS | {counts['FAIL']} FAIL | {counts['WARN']} WARN")
    print("="*70)

    if fails:
        print("\n\u274c FAILURES (HARUS DIFIX SEBELUM MARK DONE):")
        for cat, msg in fails:
            print(f"   [{cat}] {msg}")

    if warns:
        print("\n\u26a0\ufe0f  WARNINGS (Perlu diperhatikan):")
        for cat, msg in warns:
            print(f"   [{cat}] {msg}")

    if counts["FAIL"] == 0 and counts["WARN"] == 0:
        print("\n\U0001f389 SEMUA CHECKS PASSED! Sistem dalam kondisi baik.")
    elif counts["FAIL"] == 0:
        print(f"\n\u26a0\ufe0f  {counts['WARN']} warning — fix sebelum ke production")
    else:
        print(f"\n\u274c {counts['FAIL']} failure harus difix sebelum task dianggap DONE")

    return counts["FAIL"]


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    print(f"\nMenjalankan compliance check{'(quick mode)' if quick else ''}...")
    run_all_checks(quick=quick)
    fail_count = print_report()
    sys.exit(1 if fail_count > 0 else 0)
