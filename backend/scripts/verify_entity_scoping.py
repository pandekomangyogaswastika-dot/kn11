"""F0-C — GATE kepatuhan multi-entity (anti-regresi).

Dua lapis pemeriksaan:
  (1) DB CHECK   : 0 dokumen pada koleksi SCOPED yang tidak punya field entitas.
  (2) STATIC CHECK: setiap router yang melakukan list/aggregate atas koleksi
      SCOPED WAJIB mengimpor helper `entity_scope` (proxy: memakai scoping).
      Pengecualian terdokumentasi (per file×koleksi) untuk kasus yang sengaja
      lintas-entitas / by-id / ditunda fase lain.

Pakai:
    cd /app/backend && python -m scripts.verify_entity_scoping
Exit code 0 = LULUS, 1 = ADA FAIL (dipakai di CI/seed_reset).
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import db  # noqa: E402
from entity_scope import SCOPED_COLLECTIONS, field_for  # noqa: E402

ROUTERS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "routers")

# Alias nama koleksi nyata di kode vs registry.
ALIASES = {"input_tax_invoices": ["tax_invoices_in"]}

# Ditunda fase lain (dilewati pada STATIC CHECK, tetap diuji DB CHECK).
# F0-E SELESAI: gl_accounts kini SHARED (CoA by-code) → keluar dari SCOPED.
# journal_entries di-scope via service (gl_service), bukan db.* langsung di router.
DEFERRED_STATIC = {"journal_entries"}

# Pengecualian STATIC terdokumentasi: (router_file, collection) → alasan.
STATIC_EXEMPTIONS = {
    ("admin.py", "customers"): "statistik admin oversight (lintas-PT, by design)",
    ("incentive_rates.py", "incentive_rates"): "matriks config global+entity (fallback 'all')",
    ("landed_cost.py", "purchase_orders"): "lookup PO by-id untuk alokasi biaya (terikat PO ter-scope)",
    ("inbound_receiving.py", "purchase_orders"): "lookup PO by-id (join enrich)",
    ("pegging.py", "inventory_rolls"): "perencanaan ATP/pegging (Model 1: dalam entitas via transfer)",
    ("products.py", "inventory_balances"): "katalog SHARED; tampilan stok lintas-entitas (D1)",
    ("products.py", "inventory_rolls"): "katalog SHARED; tampilan roll lintas-entitas (D1)",
    ("products.py", "sales_orders"): "reservasi produk lintas-entitas (info, D1)",
}


def _missing_filter(field: str) -> dict:
    return {"$or": [{field: {"$exists": False}}, {field: None}, {field: ""}]}


async def db_check() -> bool:
    real = set(await db.list_collection_names())
    print(f"{'=' * 64}\n(1) DB CHECK — 0 dokumen SCOPED tanpa field entitas\n{'=' * 64}")
    ok = True
    for coll in sorted(SCOPED_COLLECTIONS):
        names = [coll] + ALIASES.get(coll, [])
        existing = [n for n in names if n in real]
        if not existing:
            continue
        field = field_for(coll) or "entity_id"
        missing = 0
        for n in existing:
            missing += await db[n].count_documents(_missing_filter(field))
        if missing:
            ok = False
        print(f"  [{'OK ' if missing == 0 else 'FAIL'}] {coll:24} field={field:16} missing={missing}")
    return ok


def static_check() -> bool:
    print(f"\n{'=' * 64}\n(2) STATIC CHECK — router list/aggregate SCOPED pakai entity_scope\n{'=' * 64}")
    patterns = {}
    for c in SCOPED_COLLECTIONS:
        if c in DEFERRED_STATIC:
            continue
        names = [c] + ALIASES.get(c, [])
        patterns[c] = re.compile(r"db\.(" + "|".join(names) + r")\.(find|aggregate)\(")
    ok = True
    for f in sorted(os.listdir(ROUTERS_DIR)):
        if not f.endswith(".py"):
            continue
        src = open(os.path.join(ROUTERS_DIR, f)).read()
        uses_helper = "from entity_scope import" in src
        for c, p in patterns.items():
            if not p.search(src):
                continue
            if uses_helper:
                print(f"  [OK    ] {f:26} {c}")
            elif (f, c) in STATIC_EXEMPTIONS:
                print(f"  [EXEMPT] {f:26} {c}  — {STATIC_EXEMPTIONS[(f, c)]}")
            else:
                ok = False
                print(f"  [FAIL  ] {f:26} {c}  — query koleksi SCOPED tanpa entity_scope")
    return ok


async def main():
    db_ok = await db_check()
    st_ok = static_check()
    print(f"\n{'=' * 64}")
    print(f"DB CHECK    : {'✅ LULUS' if db_ok else '❌ GAGAL'}")
    print(f"STATIC CHECK: {'✅ LULUS' if st_ok else '❌ GAGAL'}")
    print(f"GATE F0-C   : {'✅ LULUS (0 FAIL)' if (db_ok and st_ok) else '❌ ADA FAIL'}")
    print("=" * 64)
    sys.exit(0 if (db_ok and st_ok) else 1)


if __name__ == "__main__":
    asyncio.run(main())
