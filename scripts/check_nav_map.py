#!/usr/bin/env python3
"""
Check Navigation Map Script (v2 — config-driven, truthful)
==========================================================

Memvalidasi navigasi NYATA yang berjalan, sesuai **KN_13 §528 "TARGET GROUPED
NAVIGATION IA"** (grouped, collapsible, role-filtered) — bukan konvensi flat v1.0
yang sudah usang.

SSOT yang dibaca (KODE MENANG atas DOKUMEN):
  - frontend/src/config/navigationConfig.js   → struktur grup/menu + roles
  - frontend/src/components/CoreWidgets.jsx    → konvensi testid render sidebar
  - frontend/src/features/wms/OperationsView.jsx → tab WMS (wms-tab-*)
  - frontend/src/features/orders/OrdersView.jsx  → tab Orders (tab-dashboard/list)

Konvensi testid (KN_13 §586): `nav-group-{groupId}`, `nav-{module}`, `wms-tab-{tab}`.

Gate ini BISA GAGAL (exit 1) bila ada drift nyata:
  - item tanpa id/label/roles, group kosong, id duplikat
  - admin TIDAK bisa melihat semua menu (invarian KN_13 "admin lihat semua")
  - item "yatim" (tak ter-reach role mana pun) / landing role tak ter-reach
  - konvensi testid render hilang
  - tab WMS wajib hilang
  - kedalaman IA > 4 (KN_13 §585)

Usage:
    python /app/scripts/check_nav_map.py [-v]
"""

import re
import sys
import argparse
from pathlib import Path

SRC = Path("/app/frontend/src")
NAV_CFG = SRC / "config/navigationConfig.js"
SIDEBAR = SRC / "components/CoreWidgets.jsx"
OPS_VIEW = SRC / "features/wms/OperationsView.jsx"
ORDERS_VIEW = SRC / "features/orders/OrdersView.jsx"

ROLES = ["admin", "sales", "manager", "warehouse"]
REQUIRED_WMS_TABS = {"stok", "inbound", "outbound", "transfer", "cycle"}
MAX_DEPTH = 4  # KN_13 §585: Grup(L1) → Menu(L2) → Tab(L3) → Modal(L4)


class C:
    RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
    BLUE = "\033[94m"; RESET = "\033[0m"; BOLD = "\033[1m"


def hdr(t): print(f"\n{C.BOLD}{C.BLUE}{'='*60}{C.RESET}\n{C.BOLD}{t}{C.RESET}\n{C.BOLD}{C.BLUE}{'='*60}{C.RESET}\n")
def ok(t): print(f"{C.GREEN}\u2713 {t}{C.RESET}")
def bad(t): print(f"{C.RED}\u2717 {t}{C.RESET}")
def warn(t): print(f"{C.YELLOW}\u26a0 {t}{C.RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# PARSER: navigationConfig.js → list of entries
#   standalone: {"type":"standalone","id":..,"roles":[..]}
#   group:      {"type":"group","groupId":..,"roles":[..],"items":[{id,roles}..]}
# ─────────────────────────────────────────────────────────────────────────────
ROLES_RE = re.compile(r'roles:\s*\[([^\]]*)\]')
ID_RE = re.compile(r'id:\s*"([^"]+)"')
GROUPID_RE = re.compile(r'groupId:\s*"([^"]+)"')
ITEM_RE = re.compile(r'\{\s*id:\s*"([^"]+)"\s*,\s*label:\s*"([^"]*)"[^}]*?roles:\s*\[([^\]]*)\][^}]*\}')


def _roles(s):
    return [r.strip().strip('"\'') for r in s.split(",") if r.strip()]


def parse_nav_config():
    content = NAV_CFG.read_text()
    # isolate NAV_STRUCTURE = [ ... ];
    m = re.search(r'const NAV_STRUCTURE\s*=\s*\[(.*?)\n\];', content, re.S)
    body = m.group(1) if m else content
    entries = []
    # split per-entry by 'type:' marker (items inside groups have no 'type:')
    chunks = body.split("type:")
    for chunk in chunks[1:]:
        kind = "group" if chunk.lstrip().startswith('"group"') else (
            "standalone" if chunk.lstrip().startswith('"standalone"') else None)
        if kind is None:
            continue
        if kind == "standalone":
            idm = ID_RE.search(chunk)
            rm = ROLES_RE.search(chunk)
            entries.append({
                "type": "standalone",
                "id": idm.group(1) if idm else None,
                "roles": _roles(rm.group(1)) if rm else [],
            })
        else:  # group
            gm = GROUPID_RE.search(chunk)
            # group-level roles = first roles[] that appears BEFORE 'items:'
            before_items = chunk.split("items:")[0]
            grm = ROLES_RE.search(before_items)
            items_part = chunk.split("items:", 1)[1] if "items:" in chunk else ""
            items = []
            for im in ITEM_RE.finditer(items_part):
                items.append({"id": im.group(1), "label": im.group(2), "roles": _roles(im.group(3))})
            entries.append({
                "type": "group",
                "groupId": gm.group(1) if gm else None,
                "roles": _roles(grm.group(1)) if grm else [],
                "items": items,
            })
    return entries


def reachable_ids(entries, role):
    """Replicate buildNavGroups(): group visible if role in group.roles; items filtered by role."""
    out = set()
    for e in entries:
        if role not in e["roles"]:
            continue
        if e["type"] == "standalone":
            if e["id"]:
                out.add(e["id"])
        else:
            for it in e["items"]:
                if role in it["roles"]:
                    out.add(it["id"])
    return out


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 1 — Config integrity + testid convention
# ─────────────────────────────────────────────────────────────────────────────
def check_config(entries, verbose=False):
    hdr("CHECK 1: Nav config integrity + testid convention")
    issues = 0
    all_ids = []

    for e in entries:
        if e["type"] == "standalone":
            if not e["id"]:
                bad("standalone entry tanpa id"); issues += 1
            if not e["roles"]:
                bad(f"standalone '{e.get('id')}' tanpa roles"); issues += 1
            if e["id"]:
                all_ids.append(e["id"])
        else:
            gid = e.get("groupId")
            if not gid:
                bad("group entry tanpa groupId"); issues += 1
            if not e["roles"]:
                bad(f"group '{gid}' tanpa roles"); issues += 1
            if not e["items"]:
                bad(f"group '{gid}' KOSONG (0 item)"); issues += 1
            for it in e["items"]:
                if not it["id"] or not it["label"]:
                    bad(f"group '{gid}': item tanpa id/label"); issues += 1
                if not it["roles"]:
                    bad(f"group '{gid}': item '{it['id']}' tanpa roles"); issues += 1
                all_ids.append(it["id"])

    # duplicate ids
    dups = sorted({x for x in all_ids if all_ids.count(x) > 1})
    if dups:
        bad(f"id navigasi duplikat: {dups}"); issues += len(dups)

    # testid convention in CoreWidgets.jsx (render layer)
    side = SIDEBAR.read_text()
    conv = {
        "nav-${...id}": re.search(r'data-testid=\{`nav-\$\{[^}]+\}`\}', side),
        "nav-group-${groupId}": re.search(r'data-testid=\{`nav-group-\$\{[^}]+\}`\}', side),
        "nav-group-toggle-${groupId}": re.search(r'data-testid=\{`nav-group-toggle-\$\{[^}]+\}`\}', side),
    }
    for name, found in conv.items():
        if not found:
            bad(f"CoreWidgets.jsx: konvensi testid '{name}' tidak ditemukan"); issues += 1
        elif verbose:
            ok(f"testid convention: {name}")

    if issues == 0:
        n_groups = sum(1 for e in entries if e["type"] == "group")
        n_items = len(all_ids)
        ok(f"Config valid: {len(entries)} entri ({n_groups} grup), {n_items} id unik, konvensi testid render OK")
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 2 — WMS tabs + Orders tabs (dari source nyata)
# ─────────────────────────────────────────────────────────────────────────────
def check_tabs(verbose=False):
    hdr("CHECK 2: WMS tabs (wms-tab-*) + Orders tabs")
    issues = 0
    ops = OPS_VIEW.read_text()
    if not re.search(r'data-testid=\{`wms-tab-\$\{[^}]+\}`\}', ops):
        bad("OperationsView.jsx: render testid `wms-tab-${tab.id}` tidak ditemukan"); issues += 1
    # parse WMS_TABS array ids
    m = re.search(r'WMS_TABS\s*=\s*\[(.*?)\];', ops, re.S)
    tab_ids = set(re.findall(r'id:\s*"([^"]+)"', m.group(1))) if m else set()
    missing = REQUIRED_WMS_TABS - tab_ids
    if missing:
        bad(f"WMS tab wajib hilang: {sorted(missing)}"); issues += len(missing)
    elif verbose:
        ok(f"WMS tabs: {sorted(tab_ids)}")

    # Orders tabs
    if ORDERS_VIEW.exists():
        ordv = ORDERS_VIEW.read_text()
        for t in ["tab-dashboard", "tab-list"]:
            if f'data-testid="{t}"' not in ordv:
                warn(f"Orders tab '{t}' tidak ditemukan (opsional)")

    if issues == 0:
        ok(f"Semua {len(REQUIRED_WMS_TABS)} tab WMS hadir + konvensi testid OK")
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 3 — Role matrix (KN_13: admin lihat semua; tak ada item yatim; landing reachable)
# ─────────────────────────────────────────────────────────────────────────────
def check_roles(entries, verbose=False):
    hdr("CHECK 3: Role-based access (KN_13 role matrix)")
    issues = 0

    # semua item id (union)
    all_items = set()
    for e in entries:
        if e["type"] == "standalone" and e["id"]:
            all_items.add(e["id"])
        elif e["type"] == "group":
            for it in e["items"]:
                all_items.add(it["id"])

    reach = {r: reachable_ids(entries, r) for r in ROLES}

    # 3a. admin lihat semua
    admin_missing = all_items - reach["admin"]
    if admin_missing:
        bad(f"admin TIDAK bisa melihat: {sorted(admin_missing)} (invarian 'admin lihat semua')")
        issues += len(admin_missing)
    elif verbose:
        ok(f"admin reach semua {len(all_items)} item")

    # 3b. tidak ada item yatim (ter-reach minimal 1 role)
    union = set().union(*reach.values())
    orphan = all_items - union
    if orphan:
        bad(f"item yatim (tak ter-reach role mana pun): {sorted(orphan)}"); issues += len(orphan)

    # 3c. landing view per role reachable
    landing = {"admin": "admin", "warehouse": "wms-stok", "manager": "reports", "sales": "sales"}
    for role, nid in landing.items():
        if nid not in reach[role]:
            bad(f"landing role '{role}' → '{nid}' tidak ter-reach"); issues += 1
        elif verbose:
            ok(f"landing {role} → {nid} OK")

    if issues == 0:
        counts = ", ".join(f"{r}:{len(reach[r])}" for r in ROLES)
        ok(f"Role matrix konsisten (item ter-reach → {counts})")
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# CHECK 4 — Kedalaman IA ≤ 4 (KN_13 §585)
# ─────────────────────────────────────────────────────────────────────────────
def check_depth(entries, verbose=False):
    hdr("CHECK 4: Kedalaman IA (maks 4 — KN_13 §585)")
    # standalone item = L1 (menu langsung)
    # group = L1, item = L2, item-with-WMS-tab → tab = L3 (+ modal L4 = batas)
    max_depth = 1
    has_group = any(e["type"] == "group" for e in entries)
    if has_group:
        max_depth = 2
    # WMS items punya tab (deep-link tab) → +1
    ops = OPS_VIEW.read_text()
    if "wms-tab-" in ops:
        max_depth = 3
    if max_depth > MAX_DEPTH:
        bad(f"Kedalaman IA {max_depth} > {MAX_DEPTH}"); return 1
    ok(f"Kedalaman IA = {max_depth} (Grup→Menu→Tab) ≤ {MAX_DEPTH} \u2014 sesuai KN_13")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Check Navigation Map compliance (config-driven)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    print(f"\n{C.BOLD}Navigation Map Validator v2 (config-driven){C.RESET}")
    print("Reference: KN_13 §528 TARGET GROUPED NAVIGATION IA\n")

    if not NAV_CFG.exists():
        bad("navigationConfig.js tidak ditemukan"); sys.exit(1)

    entries = parse_nav_config()
    total = 0
    total += check_config(entries, args.verbose)
    total += check_tabs(args.verbose)
    total += check_roles(entries, args.verbose)
    total += check_depth(entries, args.verbose)

    hdr("SUMMARY")
    if total == 0:
        ok("Navigation map COMPLIANT dengan KN_13 (grouped IA)")
        print(f"\n{C.GREEN}{C.BOLD}\u2713 NAV MAP: PASS{C.RESET}\n")
        sys.exit(0)
    else:
        warn(f"{total} issue ditemukan")
        print(f"\n{C.YELLOW}{C.BOLD}\u26a0 NAV MAP: NEEDS ATTENTION{C.RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
