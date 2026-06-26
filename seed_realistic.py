"""
Kain Nusantara — Realistic Seed Data Script
Populates database with realistic historical data including:
- Purchase orders with completed receiving history
- Sales orders in various stages
- Inbound & outbound tasks (completed + in-progress)
- Inventory movements

Dapat dipakai sebagai:
1) Standalone CLI:   `python seed_realistic.py`
2) Imported module:  `from seed_realistic import seed_all; await seed_all(db_instance)`
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent / "backend"
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from core_utils import hash_password, new_id, now_iso, next_doc_number
from permissions_config import DEFAULT_PERMISSIONS
from datetime import datetime, timedelta, timezone
import random

# `db` is a module-level placeholder; it will be set by `init_with_db()`
# or by `main()` when running as a standalone script. Seed functions reference
# `db` by name at call-time, so replacing this value works correctly.
db = None


def init_with_db(db_instance):
    """Inject an external Motor DB instance (for use from FastAPI endpoint)."""
    global db
    db = db_instance


def ago(days=0, hours=0, minutes=0) -> str:
    """Return ISO string for a datetime in the past."""
    dt = datetime.now(timezone.utc) - timedelta(days=days, hours=hours, minutes=minutes)
    return dt.isoformat()


async def clear_collections():
    """Drop operational data — keep nothing (fresh realistic seed)."""
    cols = [
        "users", "uoms", "warehouses", "products", "customers",
        "inventory_balances", "inventory_movements", "inventory_rolls", "sales_orders",
        "wms_tasks", "purchase_orders", "document_templates",
        "permission_settings", "audit_logs", "onboarding_checklists",
        "cycle_counts", "transfers", "escalations",
        "business_entities", "notifications",
        "system_settings", "payment_terms", "approval_rules",
        "price_approvals", "shipments", "tax_invoices",
        "suppliers", "cash_transactions", "purchase_returns", "bank_accounts",
        "purchase_requisitions", "supplier_price_lists",
        "vendor_bills",
        "landed_cost_vouchers",
        "sales_targets", "sales_incentives", "collection_followups", "credit_overrides",
        "product_categories", "ar_receipts", "incentive_rates",
        "gl_accounts", "journal_entries",
    ]
    for col in cols:
        await db[col].delete_many({})
    print("✅ Cleared all collections")


async def seed_users():
    ALL = ["ent_ksc", "ent_kanda"]
    await db.users.insert_many([
        {
            "id": "user_admin_01", "name": "Budi Santoso", "email": "admin@kainnusantara.id",
            "role": "admin", "password_hash": hash_password("demo12345"), "status": "active",
            "home_entity_id": "ent_ksc", "allowed_entity_ids": ALL,
            "created_at": ago(days=180)
        },
        {
            "id": "user_sales_01", "name": "Ayu Permatasari", "email": "sales@kainnusantara.id",
            "role": "sales", "password_hash": hash_password("demo12345"), "status": "active",
            "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
            "created_at": ago(days=180)
        },
        {
            "id": "user_manager_01", "name": "Dewi Rahayu", "email": "manager@kainnusantara.id",
            "role": "manager", "password_hash": hash_password("demo12345"), "status": "active",
            "home_entity_id": "ent_ksc", "allowed_entity_ids": ALL,
            "created_at": ago(days=180)
        },
        {
            "id": "user_wh_01", "name": "Eko Prasetyo", "email": "warehouse@kainnusantara.id",
            "role": "warehouse", "password_hash": hash_password("demo12345"), "status": "active",
            "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
            "created_at": ago(days=180)
        },
        {
            "id": "user_wh_02", "name": "Fitri Handayani", "email": "warehouse2@kainnusantara.id",
            "role": "warehouse", "password_hash": hash_password("demo12345"), "status": "active",
            "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
            "created_at": ago(days=90)
        },
        {
            "id": "user_sales_02", "name": "Bima Saputra", "email": "sales2@kainnusantara.id",
            "role": "sales", "password_hash": hash_password("demo12345"), "status": "active",
            "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
            "created_at": ago(days=150)
        },
        {
            "id": "user_sales_03", "name": "Citra Lestari", "email": "sales3@kainnusantara.id",
            "role": "sales", "password_hash": hash_password("demo12345"), "status": "active",
            "home_entity_id": "ent_kanda", "allowed_entity_ids": ["ent_kanda"],
            "created_at": ago(days=120)
        },
    ])
    print("✅ Users seeded (with entity assignment)")


async def seed_uoms():
    await db.uoms.insert_many([
        {"id": "uom_meter", "code": "MTR", "name": "Meter", "base_type": "length", "precision": 2, "status": "active", "created_at": ago(days=180)},
        {"id": "uom_yard", "code": "YRD", "name": "Yard", "base_type": "length", "precision": 2, "status": "active", "created_at": ago(days=180)},
        {"id": "uom_roll", "code": "RLL", "name": "Roll", "base_type": "volume", "precision": 0, "status": "active", "created_at": ago(days=180)},
        {"id": "uom_pcs", "code": "PCS", "name": "Pcs", "base_type": "count", "precision": 0, "status": "active", "created_at": ago(days=180)},
    ])
    print("✅ UOMs seeded")


async def seed_warehouses():
    await db.warehouses.insert_many([
        {
            "id": "wh_jakarta", "code": "WH-JKT", "name": "Gudang Jakarta Utara", "city": "Jakarta",
            "lat": -6.1751, "lng": 106.8650, "active": True, "created_at": ago(days=180),
            "zones": [{"id": "zone_jkt_a", "name": "Zone A", "racks": [
                {"id": "rack_jkt_a1", "name": "Rack A1", "bins": [
                    {"id": "bin_jkt_a1_01", "code": "A1-01", "capacity": 500},
                    {"id": "bin_jkt_a1_02", "code": "A1-02", "capacity": 500},
                    {"id": "bin_jkt_a1_03", "code": "A1-03", "capacity": 500},
                ]},
                {"id": "rack_jkt_a2", "name": "Rack A2", "bins": [
                    {"id": "bin_jkt_a2_01", "code": "A2-01", "capacity": 400},
                    {"id": "bin_jkt_a2_02", "code": "A2-02", "capacity": 400},
                ]},
            ]},
            {"id": "zone_jkt_b", "name": "Zone B", "racks": [
                {"id": "rack_jkt_b1", "name": "Rack B1", "bins": [
                    {"id": "bin_jkt_b1_01", "code": "B1-01", "capacity": 600},
                    {"id": "bin_jkt_b1_02", "code": "B1-02", "capacity": 600},
                ]}
            ]}]
        },
        {
            "id": "wh_bandung", "code": "WH-BDG", "name": "Gudang Bandung Kopo", "city": "Bandung",
            "lat": -6.9175, "lng": 107.6191, "active": True, "created_at": ago(days=180),
            "zones": [{"id": "zone_bdg_a", "name": "Zone A", "racks": [
                {"id": "rack_bdg_a1", "name": "Rack A1", "bins": [
                    {"id": "bin_bdg_a1_01", "code": "A1-01", "capacity": 600},
                    {"id": "bin_bdg_a1_02", "code": "A1-02", "capacity": 600},
                ]}
            ]}]
        },
        {
            "id": "wh_surabaya", "code": "WH-SBY", "name": "Gudang Surabaya Rungkut", "city": "Surabaya",
            "lat": -7.2504, "lng": 112.7688, "active": True, "created_at": ago(days=180),
            "zones": [{"id": "zone_sby_a", "name": "Zone A", "racks": [
                {"id": "rack_sby_a1", "name": "Rack A1", "bins": [
                    {"id": "bin_sby_a1_01", "code": "A1-01", "capacity": 400},
                    {"id": "bin_sby_a1_02", "code": "A1-02", "capacity": 400},
                ]}
            ]}]
        },
    ])
    print("✅ Warehouses seeded")


async def seed_products():
    products = [
        {
            "id": "prod_batik_mega", "sku": "BTK-MEGA-001",
            "name": "Batik Mega Mendung Premium", "category": "Batik", "variant": "Premium",
            "color": "Biru-Coklat", "motif": "Mega Mendung", "grade": "A",
            "supplier": "Cirebon Craft", "base_unit": "meter", "price": 185000,
            "gramasi": 120, "lebar": 1.15,
            "image": "https://images.unsplash.com/photo-1761516659766-c092d4b1209d?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2MzR8MHwxfHNlYXJjaHw0fHxiYXRpayUyMGluZG9uZXNpYSUyMGZhYnJpYyUyMHRyYWRpdGlvbmFsJTIwdGV4dGlsZSUyMHBhdHRlcm58ZW58MHx8fHwxNzc4NjkyMDU3fDA&ixlib=rb-4.1.0&q=85",
            "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
            "template_id": "tpl_batik_mega", "variant_label": "Biru-Coklat · Grade A",
            "created_at": ago(days=180), "updated_at": ago(days=2)
        },
        {
            "id": "prod_tenun_ikat", "sku": "TNI-GRGD-001",
            "name": "Tenun Ikat Garuda Premium", "category": "Tenun", "variant": "Premium",
            "color": "Merah-Emas", "motif": "Garuda", "grade": "A",
            "supplier": "NTT Weaving Co", "base_unit": "meter", "price": 225000,
            "gramasi": 210, "lebar": 1.20,
            "image": "https://images.unsplash.com/photo-1748141951488-9c9fb9603daf?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwyfHx0ZW51biUyMGlrYXQlMjBpbmRvbmVzaWFuJTIwd292ZW4lMjB0ZXh0aWxlJTIwdHJhZGl0aW9uYWwlMjBmYWJyaWN8ZW58MHx8fHwxNzc4NjkyMDY1fDA&ixlib=rb-4.1.0&q=85",
            "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
            "created_at": ago(days=175), "updated_at": ago(days=5)
        },
        {
            "id": "prod_lurik_classic", "sku": "LRK-CLSC-001",
            "name": "Lurik Klasik Solo", "category": "Lurik", "variant": "Klasik",
            "color": "Coklat-Putih", "motif": "Garis Vertikal", "grade": "A",
            "supplier": "Solo Weave", "base_unit": "meter", "price": 95000,
            "gramasi": 170, "lebar": 1.10,
            "image": "https://images.unsplash.com/photo-1761516659491-bf9a672d64c1?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2MzR8MHwxfHNlYXJjaHwzfHxiYXRpayUyMGluZG9uZXNpYSUyMGZhYnJpYyUyMHRyYWRpdGlvbmFsJTIwdGV4dGlsZSUyMHBhdHRlcm58ZW58MHx8fHwxNzc4NjkyMDU3fDA&ixlib=rb-4.1.0&q=85",
            "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
            "created_at": ago(days=170), "updated_at": ago(days=1)
        },
        {
            "id": "prod_songket_palembang", "sku": "SGK-PLB-001",
            "name": "Songket Palembang Benang Emas", "category": "Songket", "variant": "Premium",
            "color": "Emas-Hitam", "motif": "Bunga Cengkeh", "grade": "A+",
            "supplier": "Palembang Silk House", "base_unit": "meter", "price": 450000,
            "gramasi": 280, "lebar": 1.05,
            "image": "https://images.unsplash.com/photo-1594100618558-978ea7266c0a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NDh8MHwxfHNlYXJjaHwzfHxzb25na2V0JTIwZmFicmljJTIwZ29sZCUyMHRocmVhZCUyMGluZG9uZXNpYW4lMjBzaWxrJTIwdGV4dGlsZXxlbnwwfHx8fDE3Nzg2OTIwNjV8MA&ixlib=rb-4.1.0&q=85",
            "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
            "created_at": ago(days=160), "updated_at": ago(days=3)
        },
        {
            "id": "prod_ulos_batak", "sku": "ULS-BTK-001",
            "name": "Ulos Batak Ragidup", "category": "Ulos", "variant": "Tradisional",
            "color": "Biru-Oranye", "motif": "Ragidup", "grade": "A",
            "supplier": "Toba Craft", "base_unit": "meter", "price": 320000,
            "gramasi": 230, "lebar": 0.90,
            "image": "https://images.unsplash.com/photo-1749367288395-f874bb54bc8a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHw0fHx0ZW51biUyMGlrYXQlMjBpbmRvbmVzaWFuJTIwd292ZW4lMjB0ZXh0aWxlJTIwdHJhZGl0aW9uYWwlMjBmYWJyaWN8ZW58MHx8fHwxNzc4NjkyMDY1fDA&ixlib=rb-4.1.0&q=85",
            "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
            "created_at": ago(days=155), "updated_at": ago(days=7)
        },
        {
            "id": "prod_jumputan_palembang", "sku": "JMP-PLB-001",
            "name": "Jumputan Palembang Pelangi", "category": "Jumputan", "variant": "Standard",
            "color": "Multicolor", "motif": "Pelangi Jumputan", "grade": "B",
            "supplier": "Palembang Silk House", "base_unit": "meter", "price": 145000,
            "gramasi": 150, "lebar": 1.15,
            "image": "https://images.unsplash.com/photo-1761515315375-1315503bb3ce?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2MzR8MHwxfHNlYXJjaHwyfHxiYXRpayUyMGluZG9uZXNpYSUyMGZhYnJpYyUyMHRyYWRpdGlvbmFsJTIwdGV4dGlsZSUyMHBhdHRlcm58ZW58MHx8fHwxNzc4NjkyMDU3fDA&ixlib=rb-4.1.0&q=85",
            "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
            "created_at": ago(days=120), "updated_at": ago(days=10)
        },
        {
            "id": "prod_endek_bali", "sku": "ENK-BALI-001",
            "name": "Endek Bali Rangrang", "category": "Endek", "variant": "Premium",
            "color": "Merah-Coklat", "motif": "Rangrang", "grade": "A",
            "supplier": "Bali Weave Studio", "base_unit": "meter", "price": 280000,
            "gramasi": 195, "lebar": 1.15,
            "image": "https://images.unsplash.com/photo-1749367288413-994ae375d2f6?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwzfHx0ZW51biUyMGlrYXQlMjBpbmRvbmVzaWFuJTIwd292ZW4lMjB0ZXh0aWxlJTIwdHJhZGl0aW9uYWwlMjBmYWJyaWN8ZW58MHx8fHwxNzc4NjkyMDY1fDA&ixlib=rb-4.1.0&q=85",
            "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
            "template_id": "tpl_endek_bali", "variant_label": "Merah-Coklat · Grade A",
            "created_at": ago(days=100), "updated_at": ago(days=4)
        },
    ]
    # ── EPIC-VAR — varian SKU (warna/grade) yang berbagi template_id ──────────
    # Prinsip: 1 varian = 1 SKU. Grouping HANYA di tampilan katalog POS.
    # WMS/inventory/receiving tetap per-SKU (tidak berubah).
    _batik_img = products[0]["image"]
    _endek_img = products[6]["image"]
    # F3 — gambar BERBEDA per varian dalam 1 template (popup ganti gambar saat ganti varian)
    _batik_img_merah = "https://images.unsplash.com/photo-1761516659491-bf9a672d64c1?crop=entropy&cs=srgb&fm=jpg&q=85"
    _batik_img_hijau = "https://images.unsplash.com/photo-1761515315375-1315503bb3ce?crop=entropy&cs=srgb&fm=jpg&q=85"
    _endek_img_biru = "https://images.unsplash.com/photo-1748141951488-9c9fb9603daf?crop=entropy&cs=srgb&fm=jpg&q=85"
    _endek_img_ungu = "https://images.unsplash.com/photo-1749367288395-f874bb54bc8a?crop=entropy&cs=srgb&fm=jpg&q=85"
    products += [
        {"id": "prod_batik_mega_merah", "sku": "BTK-MEGA-002",
         "name": "Batik Mega Mendung Premium", "category": "Batik", "variant": "Premium",
         "color": "Merah-Marun", "motif": "Mega Mendung", "grade": "A",
         "supplier": "Cirebon Craft", "base_unit": "meter", "price": 185000,
         "gramasi": 120, "lebar": 1.15, "image": _batik_img_merah,
         "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
         "template_id": "tpl_batik_mega", "variant_label": "Merah-Marun · Grade A",
         "created_at": ago(days=120), "updated_at": ago(days=2)},
        {"id": "prod_batik_mega_hijau", "sku": "BTK-MEGA-003",
         "name": "Batik Mega Mendung Premium", "category": "Batik", "variant": "Eksklusif",
         "color": "Hijau-Emas", "motif": "Mega Mendung", "grade": "A+",
         "supplier": "Cirebon Craft", "base_unit": "meter", "price": 215000,
         "gramasi": 125, "lebar": 1.15, "image": _batik_img_hijau,
         "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
         "template_id": "tpl_batik_mega", "variant_label": "Hijau-Emas · Grade A+",
         "created_at": ago(days=110), "updated_at": ago(days=2)},
        {"id": "prod_endek_bali_biru", "sku": "ENK-BALI-002",
         "name": "Endek Bali Rangrang", "category": "Endek", "variant": "Premium",
         "color": "Biru-Putih", "motif": "Rangrang", "grade": "A",
         "supplier": "Bali Weave Studio", "base_unit": "meter", "price": 280000,
         "gramasi": 195, "lebar": 1.15, "image": _endek_img_biru,
         "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
         "template_id": "tpl_endek_bali", "variant_label": "Biru-Putih · Grade A",
         "created_at": ago(days=95), "updated_at": ago(days=4)},
        {"id": "prod_endek_bali_ungu", "sku": "ENK-BALI-003",
         "name": "Endek Bali Rangrang", "category": "Endek", "variant": "Eksklusif",
         "color": "Ungu-Emas", "motif": "Rangrang", "grade": "A+",
         "supplier": "Bali Weave Studio", "base_unit": "meter", "price": 320000,
         "gramasi": 200, "lebar": 1.15, "image": _endek_img_ungu,
         "status": "active", "uom_conversions": [], "batch_lot_rolls": [],
         "template_id": "tpl_endek_bali", "variant_label": "Ungu-Emas · Grade A+",
         "created_at": ago(days=90), "updated_at": ago(days=4)},
    ]
    # F3 — deskripsi produk per-varian (additive). Tampil di popup detail POS;
    # berbeda per varian (warna/grade) → ganti varian = deskripsi & gambar berubah.
    for p in products:
        if not p.get("description"):
            p["description"] = (
                f"{p['name']} — motif {p['motif']}, warna {p['color']}, grade {p['grade']}. "
                f"Kain {p['category']} {str(p.get('variant', '')).lower()} dari {p['supplier']}; "
                f"gramasi {int(p.get('gramasi', 0))} gsm, lebar {p.get('lebar', 0)} m. "
                f"Dijual per {p.get('base_unit', 'meter')} — panjang tiap roll bervariasi."
            )
    await db.products.insert_many(products)
    # Depth #2b — reorder point/qty (replenishment). Beberapa produk sengaja
    # diberi reorder_point tinggi agar muncul saran replenishment untuk demo.
    reorder_map = {
        "prod_songket_palembang": (400.0, 600.0),
        "prod_ulos_batak":        (350.0, 500.0),
        "prod_endek_bali":        (300.0, 500.0),
    }
    await db.products.update_many({}, {"$set": {"reorder_point": 250.0, "reorder_qty": 500.0}})
    for pid, (rop, roq) in reorder_map.items():
        await db.products.update_one({"id": pid}, {"$set": {"reorder_point": rop, "reorder_qty": roq}})
    print("✅ Products seeded (11 products incl. variants) + reorder points")


async def seed_customers():
    await db.customers.insert_many([
        {
            "id": "cust_toko_kain", "code": "CUST-0001", "name": "Toko Kain Sejahtera",
            "pic_name": "Pak Hendra", "phone": "081234567890", "email": "hendra@tokokain.id",
            "type": "Retailer", "city": "Jakarta", "status": "active",
            "created_by": "user_admin_01", "created_at": ago(days=170),
            "addresses": [{"id": "addr_001", "label": "Toko Utama", "recipient_name": "Pak Hendra",
                           "phone": "081234567890", "city": "Jakarta",
                           "address": "Jl. Mangga Besar Raya No. 45", "is_primary": True}]
        },
        {
            "id": "cust_butik_bali", "code": "CUST-0002", "name": "Butik Bali Indah",
            "pic_name": "Ibu Komang", "phone": "082345678901", "email": "komang@butikbali.id",
            "type": "Boutique", "city": "Denpasar", "status": "active",
            "created_by": "user_admin_01", "created_at": ago(days=165),
            "addresses": [{"id": "addr_002", "label": "Butik Seminyak", "recipient_name": "Ibu Komang",
                           "phone": "082345678901", "city": "Denpasar",
                           "address": "Jl. Seminyak No. 88", "is_primary": True}]
        },
        {
            "id": "cust_moda_surabaya", "code": "CUST-0003", "name": "Moda Surabaya Fashion",
            "pic_name": "Bapak Andi", "phone": "083456789012", "email": "andi@modasby.id",
            "type": "Wholesaler", "city": "Surabaya", "status": "active",
            "created_by": "user_admin_01", "created_at": ago(days=160),
            "addresses": [{"id": "addr_003", "label": "Gudang Pusat", "recipient_name": "Bapak Andi",
                           "phone": "083456789012", "city": "Surabaya",
                           "address": "Jl. Rungkut Industri No. 22", "is_primary": True}]
        },
        {
            "id": "cust_fashion_bandung", "code": "CUST-0004", "name": "Fashion Bandung Kencana",
            "pic_name": "Ibu Sari", "phone": "085678901234", "email": "sari@fashionbdg.id",
            "type": "Boutique", "city": "Bandung", "status": "active",
            "created_by": "user_admin_01", "created_at": ago(days=120),
            "addresses": [{"id": "addr_004", "label": "Toko Dago", "recipient_name": "Ibu Sari",
                           "phone": "085678901234", "city": "Bandung",
                           "address": "Jl. Dago No. 112, Bandung", "is_primary": True}]
        },
        {
            "id": "cust_textile_medan", "code": "CUST-0005", "name": "Tekstil Medan Jaya",
            "pic_name": "Pak Robert", "phone": "081345678905", "email": "robert@tekstilmedan.id",
            "type": "Wholesaler", "city": "Medan", "status": "active",
            "created_by": "user_admin_01", "created_at": ago(days=90),
            "addresses": [{"id": "addr_005", "label": "Gudang Utama", "recipient_name": "Pak Robert",
                           "phone": "081345678905", "city": "Medan",
                           "address": "Jl. Asia No. 78, Medan", "is_primary": True}]
        },
    ])
    # CRM-lite enrichment (KN_17): assigned_sales, segment, payment_profile, credit_limit, contacts
    crm_map = {
        "cust_toko_kain":      ("user_sales_01", "Ayu Permatasari", "Retail",      50_000_000, ["langganan"]),
        "cust_butik_bali":     ("user_sales_02", "Bima Saputra",     "VIP",         30_000_000, ["premium", "bali"]),
        "cust_moda_surabaya":  ("user_sales_01", "Ayu Permatasari", "Wholesale",  200_000_000, ["grosir"]),
        "cust_fashion_bandung":("user_sales_03", "Citra Lestari",    "Retail",      40_000_000, ["butik"]),
        "cust_textile_medan":  ("user_sales_02", "Bima Saputra",     "Distributor",150_000_000, ["distributor"]),
    }
    for cid, (sid, sname, seg, limit, tags) in crm_map.items():
        cust = await db.customers.find_one({"id": cid}, {"_id": 0, "pic_name": 1, "phone": 1, "email": 1})
        await db.customers.update_one({"id": cid}, {"$set": {
            "entity_id": "ent_ksc",
            "assigned_sales_id": sid,
            "assigned_sales_name": sname,
            "sales_pic": sname,
            "segment": seg,
            "tags": tags,
            "credit_limit": limit,
            "customer_group_id": "",
            "contacts": [{"name": (cust or {}).get("pic_name", ""), "role": "PIC",
                          "phone": (cust or {}).get("phone", ""), "email": (cust or {}).get("email", ""),
                          "is_primary": True}],
            "payment_profile": {"allowed_methods": ["tunai", "tempo", "dp"], "default_method": "tempo",
                                "term_days": 30, "dp_percent": 30, "installment_count": 0,
                                "installment_interval_days": 30},
        }})
    print("✅ Customers seeded (5 customers, CRM-lite enriched)")


async def seed_crm():
    """Sales targets + incentive schemes (KN_17 §6) for current period — demo."""
    from datetime import datetime, timezone
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    default_tiers = [
        {"min_achievement": 0, "rate": 1.0},
        {"min_achievement": 80, "rate": 1.5},
        {"min_achievement": 100, "rate": 2.5},
        {"min_achievement": 120, "rate": 3.5},
    ]
    targets = [
        ("user_sales_01", "Ayu Permatasari", 250_000_000, 200_000_000, 2),
        ("user_sales_02", "Bima Saputra",    300_000_000, 240_000_000, 3),
        ("user_sales_03", "Citra Lestari",   150_000_000, 120_000_000, 1),
    ]
    for sid, sname, tsales, tcoll, tnew in targets:
        await db.sales_targets.insert_one({
            "id": f"starg_{sid}_{period}", "sales_id": sid, "sales_name": sname,
            "entity_id": "ent_ksc", "period_type": "month", "period": period,
            "target_sales_amount": tsales, "target_collection_amount": tcoll,
            "target_new_customers": tnew, "target_focus_products": [], "notes": "Target demo",
            "created_by": "Dewi Rahayu", "created_at": ago(days=5),
        })
        await db.sales_incentives.insert_one({
            "id": f"sinc_{sid}_{period}", "sales_id": sid, "sales_name": sname,
            "entity_id": "ent_ksc", "period": period, "basis": "collection",
            "tiers": default_tiers, "bonus_new_customer": 250_000, "bonus_focus_product": 0,
            "notes": "Skema komisi: pencairan + tiered (S36)", "status": "draft",
            "created_by": "Dewi Rahayu", "created_at": ago(days=5),
        })
    print(f"✅ CRM seeded (sales_targets + incentives for {period})")


async def seed_inventory_initial():
    """Seed initial inventory balances before receiving history."""
    balances = [
        # Jakarta
        {"id": new_id("bal"), "product_id": "prod_batik_mega", "warehouse_id": "wh_jakarta",
         "on_hand_qty": 485, "reserved_qty": 50, "available_qty": 435, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(hours=2)},
        {"id": new_id("bal"), "product_id": "prod_tenun_ikat", "warehouse_id": "wh_jakarta",
         "on_hand_qty": 320, "reserved_qty": 30, "available_qty": 290, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(hours=3)},
        {"id": new_id("bal"), "product_id": "prod_songket_palembang", "warehouse_id": "wh_jakarta",
         "on_hand_qty": 155, "reserved_qty": 20, "available_qty": 135, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(hours=1)},
        {"id": new_id("bal"), "product_id": "prod_ulos_batak", "warehouse_id": "wh_jakarta",
         "on_hand_qty": 95, "reserved_qty": 0, "available_qty": 95, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(days=1)},
        {"id": new_id("bal"), "product_id": "prod_endek_bali", "warehouse_id": "wh_jakarta",
         "on_hand_qty": 180, "reserved_qty": 0, "available_qty": 180, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(days=2)},
        # Bandung
        {"id": new_id("bal"), "product_id": "prod_batik_mega", "warehouse_id": "wh_bandung",
         "on_hand_qty": 340, "reserved_qty": 20, "available_qty": 320, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(hours=5)},
        {"id": new_id("bal"), "product_id": "prod_lurik_classic", "warehouse_id": "wh_bandung",
         "on_hand_qty": 620, "reserved_qty": 40, "available_qty": 580, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(hours=6)},
        {"id": new_id("bal"), "product_id": "prod_jumputan_palembang", "warehouse_id": "wh_bandung",
         "on_hand_qty": 210, "reserved_qty": 0, "available_qty": 210, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(days=3)},
        # Surabaya
        {"id": new_id("bal"), "product_id": "prod_tenun_ikat", "warehouse_id": "wh_surabaya",
         "on_hand_qty": 245, "reserved_qty": 35, "available_qty": 210, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(hours=4)},
        {"id": new_id("bal"), "product_id": "prod_lurik_classic", "warehouse_id": "wh_surabaya",
         "on_hand_qty": 410, "reserved_qty": 25, "available_qty": 385, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(hours=8)},
        {"id": new_id("bal"), "product_id": "prod_ulos_batak", "warehouse_id": "wh_surabaya",
         "on_hand_qty": 140, "reserved_qty": 0, "available_qty": 140, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(days=2)},
        {"id": new_id("bal"), "product_id": "prod_endek_bali", "warehouse_id": "wh_surabaya",
         "on_hand_qty": 75, "reserved_qty": 0, "available_qty": 75, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(days=4)},
        # ── EPIC-VAR — stok awal SKU varian (Jakarta, available-only) ──
        {"id": new_id("bal"), "product_id": "prod_batik_mega_merah", "warehouse_id": "wh_jakarta",
         "on_hand_qty": 240, "reserved_qty": 0, "available_qty": 240, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(days=2)},
        {"id": new_id("bal"), "product_id": "prod_batik_mega_hijau", "warehouse_id": "wh_jakarta",
         "on_hand_qty": 160, "reserved_qty": 0, "available_qty": 160, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(days=2)},
        {"id": new_id("bal"), "product_id": "prod_endek_bali_biru", "warehouse_id": "wh_jakarta",
         "on_hand_qty": 150, "reserved_qty": 0, "available_qty": 150, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(days=3)},
        {"id": new_id("bal"), "product_id": "prod_endek_bali_ungu", "warehouse_id": "wh_jakarta",
         "on_hand_qty": 110, "reserved_qty": 0, "available_qty": 110, "blocked_qty": 0,
         "picked_qty": 0, "in_transit_qty": 0, "updated_at": ago(days=3)},
    ]
    await db.inventory_balances.insert_many(balances)
    print(f"✅ Inventory balances seeded ({len(balances)} records)")


async def seed_inventory_movements_initial():
    """Initial stock movements."""
    movements = [
        # Jakarta initial stocks (3 months ago)
        {"id": new_id("mov"), "product_id": "prod_batik_mega", "warehouse_id": "wh_jakarta",
         "movement_type": "initial_stock", "quantity": 300, "unit": "meter",
         "batch": "BTK-2025-001", "lot": "LOT-001", "roll_id": "ROLL-001",
         "source_document": "INIT-001", "notes": "Initial stock", "created_by": "user_admin_01",
         "timestamp": ago(days=180)},
        {"id": new_id("mov"), "product_id": "prod_tenun_ikat", "warehouse_id": "wh_jakarta",
         "movement_type": "initial_stock", "quantity": 200, "unit": "meter",
         "batch": "TNI-2025-001", "lot": "LOT-001", "roll_id": "ROLL-002",
         "source_document": "INIT-001", "notes": "Initial stock", "created_by": "user_admin_01",
         "timestamp": ago(days=180)},
        {"id": new_id("mov"), "product_id": "prod_songket_palembang", "warehouse_id": "wh_jakarta",
         "movement_type": "initial_stock", "quantity": 80, "unit": "meter",
         "batch": "SGK-2025-001", "lot": "LOT-001", "roll_id": "ROLL-003",
         "source_document": "INIT-001", "notes": "Initial stock", "created_by": "user_admin_01",
         "timestamp": ago(days=180)},
        # Bandung initial stocks
        {"id": new_id("mov"), "product_id": "prod_batik_mega", "warehouse_id": "wh_bandung",
         "movement_type": "initial_stock", "quantity": 250, "unit": "meter",
         "batch": "BTK-2025-001", "lot": "LOT-002", "roll_id": "ROLL-010",
         "source_document": "INIT-001", "notes": "Initial stock", "created_by": "user_admin_01",
         "timestamp": ago(days=180)},
        {"id": new_id("mov"), "product_id": "prod_lurik_classic", "warehouse_id": "wh_bandung",
         "movement_type": "initial_stock", "quantity": 400, "unit": "meter",
         "batch": "LRK-2025-001", "lot": "LOT-001", "roll_id": "ROLL-011",
         "source_document": "INIT-001", "notes": "Initial stock", "created_by": "user_admin_01",
         "timestamp": ago(days=180)},
        # Surabaya initial stocks
        {"id": new_id("mov"), "product_id": "prod_tenun_ikat", "warehouse_id": "wh_surabaya",
         "movement_type": "initial_stock", "quantity": 150, "unit": "meter",
         "batch": "TNI-2025-001", "lot": "LOT-002", "roll_id": "ROLL-020",
         "source_document": "INIT-001", "notes": "Initial stock", "created_by": "user_admin_01",
         "timestamp": ago(days=180)},
        {"id": new_id("mov"), "product_id": "prod_lurik_classic", "warehouse_id": "wh_surabaya",
         "movement_type": "initial_stock", "quantity": 300, "unit": "meter",
         "batch": "LRK-2025-001", "lot": "LOT-002", "roll_id": "ROLL-021",
         "source_document": "INIT-001", "notes": "Initial stock", "created_by": "user_admin_01",
         "timestamp": ago(days=180)},
        # ── EPIC-VAR — initial_stock SKU varian (memberi lot bermakna utk rolls) ──
        {"id": new_id("mov"), "product_id": "prod_batik_mega_merah", "warehouse_id": "wh_jakarta",
         "movement_type": "initial_stock", "quantity": 240, "unit": "meter",
         "batch": "BTK-V-001", "lot": "LOT-V01", "roll_id": "ROLL-V01",
         "source_document": "INIT-V", "notes": "Initial stock varian", "created_by": "user_admin_01",
         "timestamp": ago(days=120)},
        {"id": new_id("mov"), "product_id": "prod_batik_mega_hijau", "warehouse_id": "wh_jakarta",
         "movement_type": "initial_stock", "quantity": 160, "unit": "meter",
         "batch": "BTK-V-002", "lot": "LOT-V02", "roll_id": "ROLL-V02",
         "source_document": "INIT-V", "notes": "Initial stock varian", "created_by": "user_admin_01",
         "timestamp": ago(days=110)},
        {"id": new_id("mov"), "product_id": "prod_endek_bali_biru", "warehouse_id": "wh_jakarta",
         "movement_type": "initial_stock", "quantity": 150, "unit": "meter",
         "batch": "ENK-V-001", "lot": "LOT-V03", "roll_id": "ROLL-V03",
         "source_document": "INIT-V", "notes": "Initial stock varian", "created_by": "user_admin_01",
         "timestamp": ago(days=95)},
        {"id": new_id("mov"), "product_id": "prod_endek_bali_ungu", "warehouse_id": "wh_jakarta",
         "movement_type": "initial_stock", "quantity": 110, "unit": "meter",
         "batch": "ENK-V-002", "lot": "LOT-V04", "roll_id": "ROLL-V04",
         "source_document": "INIT-V", "notes": "Initial stock varian", "created_by": "user_admin_01",
         "timestamp": ago(days=95)},
    ]
    await db.inventory_movements.insert_many(movements)
    print(f"✅ Initial inventory movements seeded ({len(movements)})")


async def seed_purchase_orders():
    """Seed realistic POs with completed inbound receiving history."""

    # PO-00001 — Completed 45 days ago (Batik Mega Mendung from Cirebon Craft → Jakarta)
    po1_id = "po_001"
    task1a_id = new_id("wms")
    task1b_id = new_id("wms")
    await db.purchase_orders.insert_one({
        "id": po1_id, "po_number": "PO-00001",
        "supplier_name": "Cirebon Craft", "supplier_contact": "Pak Wahyu | 081234500001",
        "warehouse_id": "wh_jakarta",
        "status": "completed",
        "items": [
            {"product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
             "product_name": "Batik Mega Mendung Premium",
             "quantity": 150.0, "received_qty": 150.0, "unit": "meter", "price": 165000,
             "status": "completed", "inbound_task_id": task1a_id},
            {"product_id": "prod_songket_palembang", "sku": "SGK-PLB-001",
             "product_name": "Songket Palembang Benang Emas",
             "quantity": 60.0, "received_qty": 60.0, "unit": "meter", "price": 420000,
             "status": "completed", "inbound_task_id": task1b_id},
        ],
        "expected_delivery_date": ago(days=46),
        "notes": "Pengiriman pertama batch 2025 Q1",
        "created_by": "Budi Santoso", "created_at": ago(days=50),
        "completed_at": ago(days=44),
    })
    # WMS tasks for PO-00001
    await db.wms_tasks.insert_many([
        {
            "id": task1a_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
            "po_id": po1_id, "po_number": "PO-00001",
            "product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
            "product_name": "Batik Mega Mendung Premium",
            "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
            "expected_qty": 150.0, "received_qty": 150.0, "quantity": 150.0,
            "unit": "meter", "status": "completed",
            "supplier_name": "Cirebon Craft",
            "bin_id": "A1-01", "batch": "BTK-2025-003", "lot": "LOT-003",
            "scan_log": [
                {"scan_time": ago(days=45, hours=2), "scanned_by": "Eko Prasetyo",
                 "actual_qty": 75.0, "batch": "BTK-2025-003", "lot": "LOT-003",
                 "roll_id": "ROLL-031", "bin_id": "A1-01"},
                {"scan_time": ago(days=45, hours=1), "scanned_by": "Eko Prasetyo",
                 "actual_qty": 75.0, "batch": "BTK-2025-003", "lot": "LOT-003",
                 "roll_id": "ROLL-032", "bin_id": "A1-01"},
            ],
            "escalation": None,
            "created_at": ago(days=50), "updated_at": ago(days=44),
            "completed_at": ago(days=44),
        },
        {
            "id": task1b_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
            "po_id": po1_id, "po_number": "PO-00001",
            "product_id": "prod_songket_palembang", "sku": "SGK-PLB-001",
            "product_name": "Songket Palembang Benang Emas",
            "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
            "expected_qty": 60.0, "received_qty": 60.0, "quantity": 60.0,
            "unit": "meter", "status": "completed",
            "supplier_name": "Cirebon Craft",
            "bin_id": "A2-01", "batch": "SGK-2025-002", "lot": "LOT-002",
            "scan_log": [
                {"scan_time": ago(days=45, hours=1, minutes=30), "scanned_by": "Eko Prasetyo",
                 "actual_qty": 60.0, "batch": "SGK-2025-002", "lot": "LOT-002",
                 "roll_id": "ROLL-033", "bin_id": "A2-01"},
            ],
            "escalation": None,
            "created_at": ago(days=50), "updated_at": ago(days=44),
            "completed_at": ago(days=44),
        },
    ])
    # Inventory movements from PO-00001 receiving
    await db.inventory_movements.insert_many([
        {"id": new_id("mov"), "product_id": "prod_batik_mega", "warehouse_id": "wh_jakarta",
         "movement_type": "inbound_receiving", "quantity": 150.0, "unit": "meter",
         "batch": "BTK-2025-003", "lot": "LOT-003", "roll_id": "ROLL-031/032",
         "source_document": "PO-00001", "notes": "Receiving completed by Eko Prasetyo",
         "created_by": "user_wh_01", "timestamp": ago(days=44)},
        {"id": new_id("mov"), "product_id": "prod_songket_palembang", "warehouse_id": "wh_jakarta",
         "movement_type": "inbound_receiving", "quantity": 60.0, "unit": "meter",
         "batch": "SGK-2025-002", "lot": "LOT-002", "roll_id": "ROLL-033",
         "source_document": "PO-00001", "notes": "Receiving completed by Eko Prasetyo",
         "created_by": "user_wh_01", "timestamp": ago(days=44)},
    ])

    # PO-00002 — Completed 30 days ago (Tenun Ikat & Lurik from NTT/Solo → Bandung + Surabaya)
    po2_id = "po_002"
    task2a_id = new_id("wms")
    task2b_id = new_id("wms")
    await db.purchase_orders.insert_one({
        "id": po2_id, "po_number": "PO-00002",
        "supplier_name": "NTT Weaving Co", "supplier_contact": "Ibu Agnes | 082345600002",
        "warehouse_id": "wh_surabaya",
        "status": "completed",
        "items": [
            {"product_id": "prod_tenun_ikat", "sku": "TNI-GRGD-001",
             "product_name": "Tenun Ikat Garuda Premium",
             "quantity": 100.0, "received_qty": 100.0, "unit": "meter", "price": 200000,
             "status": "completed", "inbound_task_id": task2a_id},
            {"product_id": "prod_ulos_batak", "sku": "ULS-BTK-001",
             "product_name": "Ulos Batak Ragidup",
             "quantity": 80.0, "received_qty": 80.0, "unit": "meter", "price": 295000,
             "status": "completed", "inbound_task_id": task2b_id},
        ],
        "expected_delivery_date": ago(days=31),
        "notes": "Pengiriman batch 2025 Q1 - NTT Collection",
        "created_by": "Budi Santoso", "created_at": ago(days=35),
        "completed_at": ago(days=29),
    })
    await db.wms_tasks.insert_many([
        {
            "id": task2a_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
            "po_id": po2_id, "po_number": "PO-00002",
            "product_id": "prod_tenun_ikat", "sku": "TNI-GRGD-001",
            "product_name": "Tenun Ikat Garuda Premium",
            "warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut",
            "expected_qty": 100.0, "received_qty": 100.0, "quantity": 100.0,
            "unit": "meter", "status": "completed",
            "supplier_name": "NTT Weaving Co",
            "bin_id": "A1-01", "batch": "TNI-2025-002", "lot": "LOT-002",
            "scan_log": [
                {"scan_time": ago(days=30, hours=3), "scanned_by": "Eko Prasetyo",
                 "actual_qty": 50.0, "batch": "TNI-2025-002", "lot": "LOT-002",
                 "roll_id": "ROLL-041", "bin_id": "A1-01"},
                {"scan_time": ago(days=30, hours=2), "scanned_by": "Eko Prasetyo",
                 "actual_qty": 50.0, "batch": "TNI-2025-002", "lot": "LOT-002",
                 "roll_id": "ROLL-042", "bin_id": "A1-01"},
            ],
            "escalation": None,
            "created_at": ago(days=35), "updated_at": ago(days=29),
            "completed_at": ago(days=29),
        },
        {
            "id": task2b_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
            "po_id": po2_id, "po_number": "PO-00002",
            "product_id": "prod_ulos_batak", "sku": "ULS-BTK-001",
            "product_name": "Ulos Batak Ragidup",
            "warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut",
            "expected_qty": 80.0, "received_qty": 80.0, "quantity": 80.0,
            "unit": "meter", "status": "completed",
            "supplier_name": "NTT Weaving Co",
            "bin_id": "A1-02", "batch": "ULS-2025-001", "lot": "LOT-001",
            "scan_log": [
                {"scan_time": ago(days=30, hours=1, minutes=30), "scanned_by": "Fitri Handayani",
                 "actual_qty": 80.0, "batch": "ULS-2025-001", "lot": "LOT-001",
                 "roll_id": "ROLL-043", "bin_id": "A1-02"},
            ],
            "escalation": None,
            "created_at": ago(days=35), "updated_at": ago(days=29),
            "completed_at": ago(days=29),
        },
    ])
    await db.inventory_movements.insert_many([
        {"id": new_id("mov"), "product_id": "prod_tenun_ikat", "warehouse_id": "wh_surabaya",
         "movement_type": "inbound_receiving", "quantity": 100.0, "unit": "meter",
         "batch": "TNI-2025-002", "lot": "LOT-002", "roll_id": "ROLL-041/042",
         "source_document": "PO-00002", "notes": "Receiving completed by Eko Prasetyo",
         "created_by": "user_wh_01", "timestamp": ago(days=29)},
        {"id": new_id("mov"), "product_id": "prod_ulos_batak", "warehouse_id": "wh_surabaya",
         "movement_type": "inbound_receiving", "quantity": 80.0, "unit": "meter",
         "batch": "ULS-2025-001", "lot": "LOT-001", "roll_id": "ROLL-043",
         "source_document": "PO-00002", "notes": "Receiving completed by Fitri Handayani",
         "created_by": "user_wh_02", "timestamp": ago(days=29)},
    ])

    # PO-00003 — Completed 15 days ago (Lurik & Endek → Bandung, with escalation history)
    po3_id = "po_003"
    task3a_id = new_id("wms")
    task3b_id = new_id("wms")
    await db.purchase_orders.insert_one({
        "id": po3_id, "po_number": "PO-00003",
        "supplier_name": "Solo Weave", "supplier_contact": "Pak Joko | 085012300003",
        "warehouse_id": "wh_bandung",
        "status": "completed",
        "items": [
            {"product_id": "prod_lurik_classic", "sku": "LRK-CLSC-001",
             "product_name": "Lurik Klasik Solo",
             "quantity": 200.0, "received_qty": 180.0, "unit": "meter", "price": 88000,
             "status": "completed", "inbound_task_id": task3a_id,
             "escalation_note": "Supplier kirim 180m, bukan 200m. Manager adjust qty."},
            {"product_id": "prod_endek_bali", "sku": "ENK-BALI-001",
             "product_name": "Endek Bali Rangrang",
             "quantity": 100.0, "received_qty": 100.0, "unit": "meter", "price": 255000,
             "status": "completed", "inbound_task_id": task3b_id},
        ],
        "expected_delivery_date": ago(days=16),
        "notes": "Batch 2025 Q1 - Lurik & Endek Bali",
        "created_by": "Budi Santoso", "created_at": ago(days=20),
        "completed_at": ago(days=14),
    })
    await db.wms_tasks.insert_many([
        {
            "id": task3a_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
            "po_id": po3_id, "po_number": "PO-00003",
            "product_id": "prod_lurik_classic", "sku": "LRK-CLSC-001",
            "product_name": "Lurik Klasik Solo",
            "warehouse_id": "wh_bandung", "warehouse_name": "Gudang Bandung Kopo",
            "expected_qty": 180.0, "received_qty": 180.0, "quantity": 180.0,
            "unit": "meter", "status": "completed",
            "supplier_name": "Solo Weave",
            "bin_id": "A1-01", "batch": "LRK-2025-002", "lot": "LOT-002",
            "scan_log": [
                {"scan_time": ago(days=15, hours=4), "scanned_by": "Fitri Handayani",
                 "actual_qty": 90.0, "batch": "LRK-2025-002", "lot": "LOT-002",
                 "roll_id": "ROLL-051", "bin_id": "A1-01"},
                {"scan_time": ago(days=15, hours=3, minutes=30), "scanned_by": "Fitri Handayani",
                 "actual_qty": 90.0, "batch": "LRK-2025-002", "lot": "LOT-002",
                 "roll_id": "ROLL-052", "bin_id": "A1-01"},
            ],
            "escalation": {
                "escalated_at": ago(days=15, hours=5),
                "escalated_by": "Fitri Handayani",
                "reason": "Supplier hanya mengirim 180m dari 200m yang dipesan. Fisik sudah dihitung ulang.",
                "status": "resolved",
                "resolved_at": ago(days=15, hours=2),
                "resolved_by": "Dewi Rahayu",
                "resolution_notes": "Dikonfirmasi supplier kekurangan material. Adjust expected qty ke 180m dan proceed complete.",
                "adjusted_qty": 180.0,
            },
            "created_at": ago(days=20), "updated_at": ago(days=14),
            "completed_at": ago(days=14),
        },
        {
            "id": task3b_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
            "po_id": po3_id, "po_number": "PO-00003",
            "product_id": "prod_endek_bali", "sku": "ENK-BALI-001",
            "product_name": "Endek Bali Rangrang",
            "warehouse_id": "wh_bandung", "warehouse_name": "Gudang Bandung Kopo",
            "expected_qty": 100.0, "received_qty": 100.0, "quantity": 100.0,
            "unit": "meter", "status": "completed",
            "supplier_name": "Solo Weave",
            "bin_id": "A1-02", "batch": "ENK-2025-001", "lot": "LOT-001",
            "scan_log": [
                {"scan_time": ago(days=15, hours=2, minutes=45), "scanned_by": "Fitri Handayani",
                 "actual_qty": 100.0, "batch": "ENK-2025-001", "lot": "LOT-001",
                 "roll_id": "ROLL-053", "bin_id": "A1-02"},
            ],
            "escalation": None,
            "created_at": ago(days=20), "updated_at": ago(days=14),
            "completed_at": ago(days=14),
        },
    ])
    await db.inventory_movements.insert_many([
        {"id": new_id("mov"), "product_id": "prod_lurik_classic", "warehouse_id": "wh_bandung",
         "movement_type": "inbound_receiving", "quantity": 180.0, "unit": "meter",
         "batch": "LRK-2025-002", "lot": "LOT-002", "roll_id": "ROLL-051/052",
         "source_document": "PO-00003", "notes": "Receiving completed (escalated & resolved) by Fitri Handayani",
         "created_by": "user_wh_02", "timestamp": ago(days=14)},
        {"id": new_id("mov"), "product_id": "prod_endek_bali", "warehouse_id": "wh_bandung",
         "movement_type": "inbound_receiving", "quantity": 100.0, "unit": "meter",
         "batch": "ENK-2025-001", "lot": "LOT-001", "roll_id": "ROLL-053",
         "source_document": "PO-00003", "notes": "Receiving completed by Fitri Handayani",
         "created_by": "user_wh_02", "timestamp": ago(days=14)},
    ])

    # PO-00004 — Currently in receiving (started 3 days ago, partially scanned)
    po4_id = "po_004"
    task4a_id = new_id("wms")
    task4b_id = new_id("wms")
    await db.purchase_orders.insert_one({
        "id": po4_id, "po_number": "PO-00004",
        "supplier_name": "Palembang Silk House", "supplier_contact": "Ibu Ratna | 081278900004",
        "warehouse_id": "wh_jakarta",
        "status": "receiving",
        "items": [
            {"product_id": "prod_songket_palembang", "sku": "SGK-PLB-001",
             "product_name": "Songket Palembang Benang Emas",
             "quantity": 75.0, "received_qty": 40.0, "unit": "meter", "price": 430000,
             "status": "receiving", "inbound_task_id": task4a_id},
            {"product_id": "prod_jumputan_palembang", "sku": "JMP-PLB-001",
             "product_name": "Jumputan Palembang Pelangi",
             "quantity": 120.0, "received_qty": 0.0, "unit": "meter", "price": 130000,
             "status": "waiting_goods", "inbound_task_id": task4b_id},
        ],
        "expected_delivery_date": ago(days=2),
        "notes": "Batch 2025 Q2 - Palembang Collection. Pengiriman dalam 2 tahap.",
        "created_by": "Budi Santoso", "created_at": ago(days=7),
    })
    await db.wms_tasks.insert_many([
        {
            "id": task4a_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
            "po_id": po4_id, "po_number": "PO-00004",
            "product_id": "prod_songket_palembang", "sku": "SGK-PLB-001",
            "product_name": "Songket Palembang Benang Emas",
            "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
            "expected_qty": 75.0, "received_qty": 40.0, "quantity": 0.0,
            "unit": "meter", "status": "receiving",
            "supplier_name": "Palembang Silk House",
            "bin_id": "B1-01", "batch": "SGK-2025-003", "lot": "LOT-003",
            "scan_log": [
                {"scan_time": ago(days=3, hours=2), "scanned_by": "Eko Prasetyo",
                 "actual_qty": 40.0, "batch": "SGK-2025-003", "lot": "LOT-003",
                 "roll_id": "ROLL-061", "bin_id": "B1-01"},
            ],
            "escalation": None,
            "created_at": ago(days=7), "updated_at": ago(days=3),
        },
        {
            "id": task4b_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
            "po_id": po4_id, "po_number": "PO-00004",
            "product_id": "prod_jumputan_palembang", "sku": "JMP-PLB-001",
            "product_name": "Jumputan Palembang Pelangi",
            "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
            "expected_qty": 120.0, "received_qty": 0.0, "quantity": 0.0,
            "unit": "meter", "status": "waiting_goods",
            "supplier_name": "Palembang Silk House",
            "scan_log": [],
            "escalation": None,
            "created_at": ago(days=7), "updated_at": ago(days=7),
        },
    ])

    # PO-00005 — Pending (just created today, awaiting delivery — task siap untuk demo)
    po5_id = "po_005"
    task5a_id = new_id("wms")
    await db.purchase_orders.insert_one({
        "id": po5_id, "po_number": "PO-00005",
        "supplier_name": "Toba Craft", "supplier_contact": "Pak Maruli | 081156700005",
        "warehouse_id": "wh_surabaya",
        "status": "receiving",
        "items": [
            {"product_id": "prod_ulos_batak", "sku": "ULS-BTK-001",
             "product_name": "Ulos Batak Ragidup",
             "quantity": 100.0, "received_qty": 0.0, "unit": "meter", "price": 305000,
             "status": "receiving", "inbound_task_id": task5a_id},
        ],
        "expected_delivery_date": ago(hours=-12),
        "notes": "Restock Ulos untuk permintaan pernikahan adat Batak. Barang sudah sampai.",
        "created_by": "Budi Santoso", "created_at": ago(hours=18),
    })
    await db.wms_tasks.insert_one({
        "id": task5a_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
        "po_id": po5_id, "po_number": "PO-00005",
        "product_id": "prod_ulos_batak", "sku": "ULS-BTK-001",
        "product_name": "Ulos Batak Ragidup",
        "warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut",
        "expected_qty": 100.0, "received_qty": 0.0, "quantity": 0.0,
        "unit": "meter", "status": "created",
        "supplier_name": "Toba Craft",
        "scan_log": [],
        "escalation": None,
        "created_at": ago(hours=18), "updated_at": ago(hours=2),
    })

    # PO-00006 — Newly created with fresh receiving task (status: created, ready for demo)
    po6_id = "po_006"
    task6a_id = new_id("wms")
    await db.purchase_orders.insert_one({
        "id": po6_id, "po_number": "PO-00006",
        "supplier_name": "Bali Weave Studio", "supplier_contact": "Pak Gede | 081256700006",
        "warehouse_id": "wh_jakarta",
        "status": "receiving",
        "items": [
            {"product_id": "prod_endek_bali", "sku": "ENK-BALI-001",
             "product_name": "Endek Bali Rangrang",
             "quantity": 80.0, "received_qty": 0.0, "unit": "meter", "price": 270000,
             "status": "receiving", "inbound_task_id": task6a_id},
        ],
        "expected_delivery_date": ago(hours=-2),
        "notes": "Restock Endek Bali untuk koleksi musim semi. Barang baru tiba di gudang.",
        "created_by": "Budi Santoso", "created_at": ago(hours=8),
    })
    await db.wms_tasks.insert_one({
        "id": task6a_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
        "po_id": po6_id, "po_number": "PO-00006",
        "product_id": "prod_endek_bali", "sku": "ENK-BALI-001",
        "product_name": "Endek Bali Rangrang",
        "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
        "expected_qty": 80.0, "received_qty": 0.0, "quantity": 0.0,
        "unit": "meter", "status": "created",
        "supplier_name": "Bali Weave Studio",
        "scan_log": [],
        "escalation": None,
        "created_at": ago(hours=8), "updated_at": ago(hours=1),
    })

    print("✅ Purchase Orders seeded (PO-00001 to PO-00006 with inbound tasks)")


async def seed_sales_orders():
    """Seed realistic Sales Orders in various stages."""

    # SO-0001 — Dispatched 40 days ago (completed flow)
    so1_id = "so_001"
    ob1a_id = new_id("wms")
    await db.sales_orders.insert_one({
        "id": so1_id, "number": "SO-0001",
        "customer_id": "cust_toko_kain", "customer_name": "Toko Kain Sejahtera",
        "customer_city": "Jakarta",
        "shipping_address": {"city": "Jakarta", "address": "Jl. Mangga Besar Raya No. 45",
                              "recipient_name": "Pak Hendra", "phone": "081234567890"},
        "items": [
            {"product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
             "product_name": "Batik Mega Mendung Premium", "quantity": 30.0, "unit": "meter",
             "price": 185000, "subtotal": 5550000,
             "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara"},
            {"product_id": "prod_tenun_ikat", "sku": "TNI-GRGD-001",
             "product_name": "Tenun Ikat Garuda Premium", "quantity": 20.0, "unit": "meter",
             "price": 225000, "subtotal": 4500000,
             "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara"},
        ],
        "total_amount": 10050000, "tax": 0, "grand_total": 10050000,
        "status": "dispatched",
        "payment_status": "paid",
        "allocations": [
            {"warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
             "product_id": "prod_batik_mega", "quantity": 30.0},
            {"warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
             "product_id": "prod_tenun_ikat", "quantity": 20.0},
        ],
        "created_by": "user_sales_01", "created_at": ago(days=45),
        "approved_at": ago(days=44), "approved_by": "user_manager_01",
        "confirmed_at": ago(days=43), "confirmed_by": "user_manager_01",
        "dispatched_at": ago(days=40),
        "notes": "Order reguler bulanan - Toko Kain Sejahtera",
    })
    await db.wms_tasks.insert_one({
        "id": ob1a_id, "flow_type": "outbound", "source_type": "sales_order", "task_subtype": "picking",
        "order_id": so1_id, "order_number": "SO-0001",
        "customer_name": "Toko Kain Sejahtera",
        "product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
        "product_name": "Batik Mega Mendung Premium",
        "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
        "quantity": 30.0, "picked_qty": 30.0, "unit": "meter",
        "status": "dispatched",
        "batch": "BTK-2025-001", "lot": "LOT-001",
        "scan_log": [
            {"scan_time": ago(days=41, hours=3), "scanned_by": "Eko Prasetyo",
             "actual_qty": 30.0, "batch": "BTK-2025-001", "lot": "LOT-001",
             "roll_id": "ROLL-001", "bin_id": "A1-01"},
        ],
        "escalation": None,
        "created_at": ago(days=43), "updated_at": ago(days=40),
        "dispatched_at": ago(days=40),
    })
    await db.inventory_movements.insert_many([
        {"id": new_id("mov"), "product_id": "prod_batik_mega", "warehouse_id": "wh_jakarta",
         "movement_type": "outbound_dispatch", "quantity": -30.0, "unit": "meter",
         "batch": "BTK-2025-001", "lot": "LOT-001", "roll_id": "ROLL-001",
         "source_document": "SO-0001", "notes": "Dispatch ke Toko Kain Sejahtera",
         "created_by": "user_wh_01", "timestamp": ago(days=40)},
        {"id": new_id("mov"), "product_id": "prod_tenun_ikat", "warehouse_id": "wh_jakarta",
         "movement_type": "outbound_dispatch", "quantity": -20.0, "unit": "meter",
         "batch": "TNI-2025-001", "lot": "LOT-001", "roll_id": "ROLL-003",
         "source_document": "SO-0001", "notes": "Dispatch ke Toko Kain Sejahtera",
         "created_by": "user_wh_01", "timestamp": ago(days=40)},
    ])

    # SO-0002 — Dispatched 25 days ago, multi-warehouse split
    so2_id = "so_002"
    ob2a_id = new_id("wms")
    ob2b_id = new_id("wms")
    await db.sales_orders.insert_one({
        "id": so2_id, "number": "SO-0002",
        "customer_id": "cust_moda_surabaya", "customer_name": "Moda Surabaya Fashion",
        "customer_city": "Surabaya",
        "shipping_address": {"city": "Surabaya", "address": "Jl. Rungkut Industri No. 22",
                              "recipient_name": "Bapak Andi", "phone": "083456789012"},
        "items": [
            {"product_id": "prod_lurik_classic", "sku": "LRK-CLSC-001",
             "product_name": "Lurik Klasik Solo", "quantity": 100.0, "unit": "meter",
             "price": 95000, "subtotal": 9500000},
        ],
        "total_amount": 9500000, "tax": 0, "grand_total": 9500000,
        "status": "dispatched",
        "payment_status": "paid",
        "allocations": [
            {"warehouse_id": "wh_bandung", "warehouse_name": "Gudang Bandung Kopo",
             "product_id": "prod_lurik_classic", "quantity": 60.0},
            {"warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut",
             "product_id": "prod_lurik_classic", "quantity": 40.0},
        ],
        "created_by": "user_sales_01", "created_at": ago(days=30),
        "approved_at": ago(days=29), "approved_by": "user_manager_01",
        "confirmed_at": ago(days=28), "confirmed_by": "user_manager_01",
        "dispatched_at": ago(days=25),
        "notes": "Order grosir - Lurik split dari 2 gudang",
    })
    await db.wms_tasks.insert_many([
        {
            "id": ob2a_id, "flow_type": "outbound", "source_type": "sales_order", "task_subtype": "picking",
            "order_id": so2_id, "order_number": "SO-0002",
            "customer_name": "Moda Surabaya Fashion",
            "product_id": "prod_lurik_classic", "sku": "LRK-CLSC-001",
            "product_name": "Lurik Klasik Solo",
            "warehouse_id": "wh_bandung", "warehouse_name": "Gudang Bandung Kopo",
            "quantity": 60.0, "picked_qty": 60.0, "unit": "meter",
            "status": "dispatched",
            "batch": "LRK-2025-001", "lot": "LOT-001",
            "scan_log": [
                {"scan_time": ago(days=26, hours=4), "scanned_by": "Fitri Handayani",
                 "actual_qty": 60.0, "batch": "LRK-2025-001", "lot": "LOT-001",
                 "roll_id": "ROLL-011", "bin_id": "A1-01"},
            ],
            "escalation": None,
            "created_at": ago(days=28), "updated_at": ago(days=25),
            "dispatched_at": ago(days=25),
        },
        {
            "id": ob2b_id, "flow_type": "outbound", "source_type": "sales_order", "task_subtype": "picking",
            "order_id": so2_id, "order_number": "SO-0002",
            "customer_name": "Moda Surabaya Fashion",
            "product_id": "prod_lurik_classic", "sku": "LRK-CLSC-001",
            "product_name": "Lurik Klasik Solo",
            "warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut",
            "quantity": 40.0, "picked_qty": 40.0, "unit": "meter",
            "status": "dispatched",
            "batch": "LRK-2025-001", "lot": "LOT-002",
            "scan_log": [
                {"scan_time": ago(days=26, hours=2), "scanned_by": "Eko Prasetyo",
                 "actual_qty": 40.0, "batch": "LRK-2025-001", "lot": "LOT-002",
                 "roll_id": "ROLL-021", "bin_id": "A1-01"},
            ],
            "escalation": None,
            "created_at": ago(days=28), "updated_at": ago(days=25),
            "dispatched_at": ago(days=25),
        },
    ])
    await db.inventory_movements.insert_many([
        {"id": new_id("mov"), "product_id": "prod_lurik_classic", "warehouse_id": "wh_bandung",
         "movement_type": "outbound_dispatch", "quantity": -60.0, "unit": "meter",
         "batch": "LRK-2025-001", "lot": "LOT-001", "roll_id": "ROLL-011",
         "source_document": "SO-0002", "notes": "Dispatch (split) ke Moda Surabaya Fashion",
         "created_by": "user_wh_02", "timestamp": ago(days=25)},
        {"id": new_id("mov"), "product_id": "prod_lurik_classic", "warehouse_id": "wh_surabaya",
         "movement_type": "outbound_dispatch", "quantity": -40.0, "unit": "meter",
         "batch": "LRK-2025-001", "lot": "LOT-002", "roll_id": "ROLL-021",
         "source_document": "SO-0002", "notes": "Dispatch (split) ke Moda Surabaya Fashion",
         "created_by": "user_wh_01", "timestamp": ago(days=25)},
    ])

    # SO-0003 — Dispatched 12 days ago (Songket + Ulos, with escalation resolved)
    so3_id = "so_003"
    ob3a_id = new_id("wms")
    ob3b_id = new_id("wms")
    await db.sales_orders.insert_one({
        "id": so3_id, "number": "SO-0003",
        "customer_id": "cust_butik_bali", "customer_name": "Butik Bali Indah",
        "customer_city": "Denpasar",
        "shipping_address": {"city": "Denpasar", "address": "Jl. Seminyak No. 88",
                              "recipient_name": "Ibu Komang", "phone": "082345678901"},
        "items": [
            {"product_id": "prod_songket_palembang", "sku": "SGK-PLB-001",
             "product_name": "Songket Palembang Benang Emas", "quantity": 25.0, "unit": "meter",
             "price": 450000, "subtotal": 11250000,
             "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara"},
            {"product_id": "prod_endek_bali", "sku": "ENK-BALI-001",
             "product_name": "Endek Bali Rangrang", "quantity": 40.0, "unit": "meter",
             "price": 280000, "subtotal": 11200000,
             "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara"},
        ],
        "total_amount": 22450000, "tax": 0, "grand_total": 22450000,
        "status": "dispatched",
        "payment_status": "pending",
        "allocations": [
            {"warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
             "product_id": "prod_songket_palembang", "quantity": 25.0},
            {"warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
             "product_id": "prod_endek_bali", "quantity": 40.0},
        ],
        "created_by": "user_sales_01", "created_at": ago(days=18),
        "approved_at": ago(days=17), "approved_by": "user_manager_01",
        "confirmed_at": ago(days=16), "confirmed_by": "user_manager_01",
        "dispatched_at": ago(days=12),
        "notes": "Premium order untuk koleksi butik Bali",
    })
    await db.wms_tasks.insert_many([
        {
            "id": ob3a_id, "flow_type": "outbound", "source_type": "sales_order", "task_subtype": "picking",
            "order_id": so3_id, "order_number": "SO-0003",
            "customer_name": "Butik Bali Indah",
            "product_id": "prod_songket_palembang", "sku": "SGK-PLB-001",
            "product_name": "Songket Palembang Benang Emas",
            "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
            "quantity": 25.0, "picked_qty": 22.0, "unit": "meter",
            "status": "dispatched",
            "batch": "SGK-2025-001", "lot": "LOT-001",
            "scan_log": [
                {"scan_time": ago(days=13, hours=3), "scanned_by": "Eko Prasetyo",
                 "actual_qty": 22.0, "batch": "SGK-2025-001", "lot": "LOT-001",
                 "roll_id": "ROLL-003", "bin_id": "A2-01"},
            ],
            "escalation": {
                "escalated_at": ago(days=13, hours=4),
                "escalated_by": "Eko Prasetyo",
                "reason": "Fisik di rak hanya 22m, sistem menunjukkan 25m. Kemungkinan selisih dari pemakaian sebelumnya.",
                "status": "resolved",
                "resolved_at": ago(days=13, hours=1),
                "resolved_by": "Dewi Rahayu",
                "resolution_notes": "Disetujui kirim 22m, balance 3m dikoreksi. Customer konfirmasi OK.",
                "adjusted_qty": 22.0,
            },
            "created_at": ago(days=16), "updated_at": ago(days=12),
            "dispatched_at": ago(days=12),
        },
        {
            "id": ob3b_id, "flow_type": "outbound", "source_type": "sales_order", "task_subtype": "picking",
            "order_id": so3_id, "order_number": "SO-0003",
            "customer_name": "Butik Bali Indah",
            "product_id": "prod_endek_bali", "sku": "ENK-BALI-001",
            "product_name": "Endek Bali Rangrang",
            "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
            "quantity": 40.0, "picked_qty": 40.0, "unit": "meter",
            "status": "dispatched",
            "batch": "ENK-2025-001", "lot": "LOT-001",
            "scan_log": [
                {"scan_time": ago(days=13, hours=2), "scanned_by": "Eko Prasetyo",
                 "actual_qty": 40.0, "batch": "ENK-2025-001", "lot": "LOT-001",
                 "roll_id": "ROLL-053", "bin_id": "A2-01"},
            ],
            "escalation": None,
            "created_at": ago(days=16), "updated_at": ago(days=12),
            "dispatched_at": ago(days=12),
        },
    ])
    await db.inventory_movements.insert_many([
        {"id": new_id("mov"), "product_id": "prod_songket_palembang", "warehouse_id": "wh_jakarta",
         "movement_type": "outbound_dispatch", "quantity": -22.0, "unit": "meter",
         "batch": "SGK-2025-001", "lot": "LOT-001",
         "source_document": "SO-0003", "notes": "Dispatch ke Butik Bali Indah (adjusted after escalation)",
         "created_by": "user_wh_01", "timestamp": ago(days=12)},
        {"id": new_id("mov"), "product_id": "prod_endek_bali", "warehouse_id": "wh_jakarta",
         "movement_type": "outbound_dispatch", "quantity": -40.0, "unit": "meter",
         "batch": "ENK-2025-001", "lot": "LOT-001",
         "source_document": "SO-0003", "notes": "Dispatch ke Butik Bali Indah",
         "created_by": "user_wh_01", "timestamp": ago(days=12)},
    ])

    # SO-0004 — Currently in picking (outbound tasks in progress)
    so4_id = "so_004"
    ob4a_id = new_id("wms")
    ob4b_id = new_id("wms")
    await db.sales_orders.insert_one({
        "id": so4_id, "number": "SO-0004",
        "customer_id": "cust_fashion_bandung", "customer_name": "Fashion Bandung Kencana",
        "customer_city": "Bandung",
        "shipping_address": {"city": "Bandung", "address": "Jl. Dago No. 112, Bandung",
                              "recipient_name": "Ibu Sari", "phone": "085678901234"},
        "items": [
            {"product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
             "product_name": "Batik Mega Mendung Premium", "quantity": 50.0, "unit": "meter",
             "price": 185000, "subtotal": 9250000},
        ],
        "total_amount": 9250000, "tax": 0, "grand_total": 9250000,
        "status": "confirmed",
        "payment_status": "pending",
        "allocations": [
            {"warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
             "product_id": "prod_batik_mega", "quantity": 50.0},
        ],
        "created_by": "user_sales_01", "created_at": ago(days=5),
        "approved_at": ago(days=4), "approved_by": "user_manager_01",
        "confirmed_at": ago(days=3), "confirmed_by": "user_manager_01",
        "notes": "Urgent order - fashion show upcoming",
    })
    await db.wms_tasks.insert_many([
        {
            "id": ob4a_id, "flow_type": "outbound", "source_type": "sales_order", "task_subtype": "picking",
            "order_id": so4_id, "order_number": "SO-0004",
            "customer_name": "Fashion Bandung Kencana",
            "product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
            "product_name": "Batik Mega Mendung Premium",
            "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
            "quantity": 50.0, "picked_qty": 30.0, "unit": "meter",
            "status": "picking",
            "scan_log": [
                {"scan_time": ago(days=2, hours=5), "scanned_by": "Eko Prasetyo",
                 "actual_qty": 30.0, "batch": "BTK-2025-003", "lot": "LOT-003",
                 "roll_id": "ROLL-032", "bin_id": "A1-01"},
            ],
            "escalation": None,
            "created_at": ago(days=3), "updated_at": ago(days=2),
        },
    ])

    # SO-0005 — Approved, awaiting confirmation
    so5_id = "so_005"
    await db.sales_orders.insert_one({
        "id": so5_id, "number": "SO-0005",
        "customer_id": "cust_textile_medan", "customer_name": "Tekstil Medan Jaya",
        "customer_city": "Medan",
        "shipping_address": {"city": "Medan", "address": "Jl. Asia No. 78, Medan",
                              "recipient_name": "Pak Robert", "phone": "081345678905"},
        "items": [
            {"product_id": "prod_tenun_ikat", "sku": "TNI-GRGD-001",
             "product_name": "Tenun Ikat Garuda Premium", "quantity": 50.0, "unit": "meter",
             "price": 225000, "subtotal": 11250000,
             "warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut"},
            {"product_id": "prod_ulos_batak", "sku": "ULS-BTK-001",
             "product_name": "Ulos Batak Ragidup", "quantity": 30.0, "unit": "meter",
             "price": 320000, "subtotal": 9600000,
             "warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut"},
        ],
        "total_amount": 20850000, "tax": 0, "grand_total": 20850000,
        "status": "approved",
        "payment_status": "pending",
        "allocations": [
            {"warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut",
             "product_id": "prod_tenun_ikat", "quantity": 50.0},
            {"warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut",
             "product_id": "prod_ulos_batak", "quantity": 30.0},
        ],
        "created_by": "user_sales_01", "created_at": ago(days=2),
        "approved_at": ago(hours=10), "approved_by": "user_manager_01",
        "notes": "Order besar - Tekstil Medan, perlu konfirmasi segera",
    })

    # SO-0006 — Reserved (just submitted, masih bisa di-cancel/release reservation)
    so6_id = "so_006"
    await db.sales_orders.insert_one({
        "id": so6_id, "number": "SO-0006",
        "customer_id": "cust_toko_kain", "customer_name": "Toko Kain Sejahtera",
        "customer_city": "Jakarta",
        "shipping_address": {"city": "Jakarta", "address": "Jl. Mangga Besar Raya No. 45",
                              "recipient_name": "Pak Hendra", "phone": "081234567890"},
        "items": [
            {"product_id": "prod_lurik_classic", "sku": "LRK-CLSC-001",
             "product_name": "Lurik Klasik Solo", "quantity": 40.0, "unit": "meter",
             "price": 95000, "subtotal": 3800000,
             "warehouse_id": "wh_bandung", "warehouse_name": "Gudang Bandung Kopo"},
            {"product_id": "prod_songket_palembang", "sku": "SGK-PLB-001",
             "product_name": "Songket Palembang Benang Emas", "quantity": 10.0, "unit": "meter",
             "price": 450000, "subtotal": 4500000,
             "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara"},
        ],
        "total_amount": 8300000, "tax": 0, "grand_total": 8300000,
        "status": "reserved",
        "payment_status": "pending",
        "reservation_expires_at": (datetime.now(timezone.utc) + timedelta(days=2, hours=18)).isoformat(),
        "allocations": [
            {"warehouse_id": "wh_bandung", "warehouse_name": "Gudang Bandung Kopo",
             "product_id": "prod_lurik_classic", "quantity": 40.0},
            {"warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
             "product_id": "prod_songket_palembang", "quantity": 10.0},
        ],
        "created_by": "user_sales_01", "created_at": ago(hours=2),
        "notes": "Repeat order dari Pak Hendra - Toko Kain Sejahtera (reserved otomatis, demo release reservation)",
    })

    # SO-0007 — Waiting Approval (target tour 'Approve Order')
    so7_id = "so_007"
    await db.sales_orders.insert_one({
        "id": so7_id, "number": "SO-0007",
        "customer_id": "cust_fashion_bandung", "customer_name": "Fashion Bandung Kencana",
        "customer_city": "Bandung",
        "shipping_address": {"city": "Bandung", "address": "Jl. Dago No. 112, Bandung",
                              "recipient_name": "Ibu Sari", "phone": "085678901234"},
        "items": [
            {"product_id": "prod_endek_bali", "sku": "ENK-BALI-001",
             "product_name": "Endek Bali Rangrang", "quantity": 25.0, "unit": "meter",
             "price": 280000, "subtotal": 7000000,
             "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara"},
            {"product_id": "prod_jumputan_palembang", "sku": "JMP-PLB-001",
             "product_name": "Jumputan Palembang Pelangi", "quantity": 60.0, "unit": "meter",
             "price": 145000, "subtotal": 8700000,
             "warehouse_id": "wh_bandung", "warehouse_name": "Gudang Bandung Kopo"},
        ],
        "total_amount": 15700000, "tax": 0, "grand_total": 15700000,
        "status": "waiting_approval",
        "payment_status": "pending",
        "reservation_expires_at": (datetime.now(timezone.utc) + timedelta(days=2, hours=22)).isoformat(),
        "allocations": [
            {"warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
             "product_id": "prod_endek_bali", "quantity": 25.0},
            {"warehouse_id": "wh_bandung", "warehouse_name": "Gudang Bandung Kopo",
             "product_id": "prod_jumputan_palembang", "quantity": 60.0},
        ],
        "created_by": "user_sales_01", "created_at": ago(hours=1),
        "notes": "Order baru untuk koleksi musim semi - butuh approval manager",
    })

    # SO-0008 — Reserved + multi-product (target untuk demo release reservation)
    so8_id = "so_008"
    await db.sales_orders.insert_one({
        "id": so8_id, "number": "SO-0008",
        "customer_id": "cust_butik_bali", "customer_name": "Butik Bali Indah",
        "customer_city": "Denpasar",
        "shipping_address": {"city": "Denpasar", "address": "Jl. Seminyak No. 88",
                              "recipient_name": "Ibu Komang", "phone": "082345678901"},
        "items": [
            {"product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
             "product_name": "Batik Mega Mendung Premium", "quantity": 15.0, "unit": "meter",
             "price": 185000, "subtotal": 2775000,
             "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara"},
        ],
        "total_amount": 2775000, "tax": 0, "grand_total": 2775000,
        "status": "reserved",
        "payment_status": "pending",
        "reservation_expires_at": (datetime.now(timezone.utc) + timedelta(days=1, hours=12)).isoformat(),
        "allocations": [
            {"warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
             "product_id": "prod_batik_mega", "quantity": 15.0},
        ],
        "created_by": "user_sales_01", "created_at": ago(hours=8),
        "notes": "Reservasi sample untuk koleksi butik - akan dikonfirmasi",
    })

    # ===== SO-0009 — Pending SO (F2b): backorder menunggu incoming PO-00009 =====
    # Stok batik tak cukup saat order → 200m masuk backorder, dijanjikan dari PO
    # incoming (PO-00009, 800m, ETA ~5 hari). Tampil di papan Stok Multi-Bucket →
    # tab "Pending SO" dengan coverage "Terjamin" + promise date = ETA PO.
    so9_id = new_id("so")
    await db.sales_orders.insert_one({
        "id": so9_id, "number": "SO-0009",
        "customer_id": "cust_textile_medan", "customer_name": "Tekstil Medan Jaya",
        "customer_city": "Medan", "entity_id": "ent_ksc",
        "shipping_address": {"city": "Medan", "address": "Jl. Sisingamangaraja No. 21",
                              "recipient_name": "Bapak Sitorus", "phone": "081234567000"},
        "items": [], "allocations": [], "total_amount": 0.0, "tax": 0, "grand_total": 0.0,
        "status": "waiting_stock", "payment_status": "pending", "has_backorder": True,
        "backorders": [{
            "id": new_id("bo"), "product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
            "product_name": "Batik Mega Mendung Premium", "entity_id": "ent_ksc",
            "customer_city": "Medan", "requested_qty": 300.0, "reserved_qty": 100.0,
            "backorder_qty": 200.0, "status": "waiting_stock",
            "created_at": ago(hours=6), "updated_at": ago(hours=6),
        }],
        "created_by": "user_sales_01", "created_at": ago(hours=6),
        "notes": "Pending SO — 200m backorder, menunggu incoming PO-00009",
    })
    # Task 1 — SO-0005 outbound (status created, fresh ready to pick)
    ob5a_id = new_id("wms")
    ob5b_id = new_id("wms")
    await db.wms_tasks.insert_many([
        {
            "id": ob5a_id, "flow_type": "outbound", "source_type": "sales_order", "task_subtype": "picking",
            "order_id": so5_id, "order_number": "SO-0005",
            "customer_name": "Tekstil Medan Jaya",
            "product_id": "prod_tenun_ikat", "sku": "TNI-GRGD-001",
            "product_name": "Tenun Ikat Garuda Premium",
            "warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut",
            "quantity": 50.0, "picked_qty": 0.0, "unit": "meter",
            "status": "created",
            "scan_log": [], "escalation": None,
            "created_at": ago(hours=10), "updated_at": ago(hours=10),
        },
        {
            "id": ob5b_id, "flow_type": "outbound", "source_type": "sales_order", "task_subtype": "picking",
            "order_id": so5_id, "order_number": "SO-0005",
            "customer_name": "Tekstil Medan Jaya",
            "product_id": "prod_ulos_batak", "sku": "ULS-BTK-001",
            "product_name": "Ulos Batak Ragidup",
            "warehouse_id": "wh_surabaya", "warehouse_name": "Gudang Surabaya Rungkut",
            "quantity": 30.0, "picked_qty": 0.0, "unit": "meter",
            "status": "created",
            "scan_log": [], "escalation": None,
            "created_at": ago(hours=10), "updated_at": ago(hours=10),
        },
    ])

    print("✅ Sales Orders seeded (SO-0001 to SO-0008 with outbound tasks)")


async def seed_document_templates():
    await db.document_templates.insert_many([
        {
            "id": "tmpl_sj_default", "document_type": "surat_jalan", "name": "Template SJ Standard",
            "header": "KAIN NUSANTARA — Enterprise Textile Warehouse",
            "footer": "Barang diterima dalam kondisi baik. Tanda tangan sebagai bukti penerimaan.",
            "columns": ["sku", "name", "qty", "unit", "batch", "lot"],
            "logo_url": "", "paper_size": "A4", "orientation": "portrait", "margin_mm": 12,
            "signature_left": "Disiapkan Oleh", "signature_right": "Diterima Oleh",
            "section_order": ["header", "customer", "items", "allocation", "signature", "footer"],
            "status": "active", "created_by": "seed", "created_at": ago(days=180)
        },
        {
            "id": "tmpl_inv_default", "document_type": "invoice", "name": "Template Invoice Standard",
            "header": "KAIN NUSANTARA — Invoice",
            "footer": "Pembayaran dalam 30 hari. Terima kasih atas kepercayaan Anda.",
            "columns": ["sku", "name", "qty", "unit", "price", "subtotal"],
            "logo_url": "", "paper_size": "A4", "orientation": "portrait", "margin_mm": 12,
            "signature_left": "Dibuat Oleh", "signature_right": "Disetujui Oleh",
            "section_order": ["header", "customer", "items", "signature", "footer"],
            "status": "active", "created_by": "seed", "created_at": ago(days=180)
        },
    ])
    print("✅ Document templates seeded")


async def seed_permissions():
    if await db.permission_settings.count_documents({}) == 0:
        await db.permission_settings.insert_one(
            {"id": "default", "matrix": DEFAULT_PERMISSIONS, "updated_at": ago(days=30)}
        )
    print("✅ Permissions seeded")


async def seed_audit_logs():
    """Seed some realistic audit log entries."""
    logs = [
        {"id": new_id("audit"), "user_id": "user_admin_01", "user_name": "Budi Santoso",
         "action": "CREATE", "resource": "purchase_order", "resource_id": "po_001",
         "details": {"po_number": "PO-00001", "supplier": "Cirebon Craft"},
         "timestamp": ago(days=50)},
        {"id": new_id("audit"), "user_id": "user_wh_01", "user_name": "Eko Prasetyo",
         "action": "COMPLETE", "resource": "inbound_task", "resource_id": "completed",
         "details": {"po_number": "PO-00001", "product": "Batik Mega Mendung Premium", "quantity": 150},
         "timestamp": ago(days=44)},
        {"id": new_id("audit"), "user_id": "user_sales_01", "user_name": "Ayu Permatasari",
         "action": "CREATE", "resource": "sales_order", "resource_id": "so_001",
         "details": {"order_number": "SO-0001", "customer": "Toko Kain Sejahtera", "total": 10050000},
         "timestamp": ago(days=45)},
        {"id": new_id("audit"), "user_id": "user_manager_01", "user_name": "Dewi Rahayu",
         "action": "APPROVE", "resource": "sales_order", "resource_id": "so_001",
         "details": {"order_number": "SO-0001"},
         "timestamp": ago(days=44)},
        {"id": new_id("audit"), "user_id": "user_wh_02", "user_name": "Fitri Handayani",
         "action": "ESCALATE", "resource": "inbound_task", "resource_id": "escalated",
         "details": {"po_number": "PO-00003", "reason": "Qty kurang dari supplier"},
         "timestamp": ago(days=15, hours=5)},
        {"id": new_id("audit"), "user_id": "user_manager_01", "user_name": "Dewi Rahayu",
         "action": "RESOLVE_ESCALATION", "resource": "inbound_task", "resource_id": "resolved",
         "details": {"po_number": "PO-00003", "adjusted_qty": 180},
         "timestamp": ago(days=15, hours=2)},
    ]
    await db.audit_logs.insert_many(logs)
    print(f"✅ Audit logs seeded ({len(logs)} entries)")


async def backfill_order_snapshots():
    """Snapshot-completeness (kontrak FE↔BE): pastikan setiap sales_order punya
    `sales_name` (dari user pembuat) & `shipping_city` (dari customer/alamat).
    create_order menghasilkan field ini; seed harus mengikuti kontrak yang sama
    agar OrdersView tidak menampilkan label kosong (cegah RC-2/G1 drift)."""
    users_map = {u["id"]: u["name"]
                 for u in await db.users.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)}
    patched = 0
    for o in await db.sales_orders.find({}, {"_id": 0}).to_list(500):
        upd = {}
        if not o.get("sales_name"):
            upd["sales_name"] = users_map.get(o.get("created_by"), "Sales")
        if not o.get("shipping_city"):
            upd["shipping_city"] = (
                o.get("customer_city")
                or (o.get("shipping_address") or {}).get("city")
                or "-"
            )
        if upd:
            await db.sales_orders.update_one({"id": o["id"]}, {"$set": upd})
            patched += 1
    print(f"✅ Order snapshots backfilled (sales_name/shipping_city) → {patched} order")


async def finalize_epic2_categories():
    """EPIC2 — dijalankan di AKHIR pipeline (setelah backfill_order_pricing yang
    menulis ulang items). 1) seed master `product_categories`; 2) snapshot
    `category` (+base_unit/base_quantity) ke setiap SO line. Idempotent."""
    products_map = {p["id"]: p for p in await db.products.find(
        {}, {"_id": 0, "id": 1, "category": 1, "base_unit": 1}).to_list(2000)}

    # 1) Master kategori produk
    if await db.product_categories.count_documents({}) == 0:
        base_units = {"Batik": "meter", "Tenun": "meter", "Lurik": "meter", "Songket": "meter",
                      "Ulos": "meter", "Jumputan": "meter", "Endek": "meter"}
        names = sorted({c for c in await db.products.distinct("category") if c} | set(base_units))
        cat_docs = []
        for idx, name in enumerate(names):
            rep = next((p for p in products_map.values() if p.get("category") == name), {})
            cat_docs.append({
                "id": new_id("cat"), "code": name.upper()[:24], "name": name,
                "base_unit": rep.get("base_unit") or base_units.get(name, "meter"),
                "description": f"Kategori kain {name}", "sort_order": idx, "status": "active",
                "created_at": now_iso(), "updated_at": now_iso(),
            })
        if cat_docs:
            await db.product_categories.insert_many(cat_docs)
            print(f"✅ Product categories seeded → {len(cat_docs)} kategori")

    # 2) Snapshot kategori per SO line
    patched = 0
    for o in await db.sales_orders.find({}, {"_id": 0, "id": 1, "items": 1}).to_list(500):
        items = o.get("items") or []
        changed = False
        for it in items:
            if "category" not in it:
                prod = products_map.get(it.get("product_id"), {})
                it["category"] = prod.get("category", "")
                it.setdefault("base_unit", prod.get("base_unit", "meter"))
                it.setdefault("base_quantity", float(it.get("quantity", 0) or 0))
                changed = True
        if changed:
            await db.sales_orders.update_one({"id": o["id"]}, {"$set": {"items": items}})
            patched += 1
    print(f"✅ SO line category snapshot → {patched} order")


# EPIC3 — rasio HPP per kategori (proxy biaya bila harga_pokok belum diisi).
_HPP_RATIO_SEED = {"Batik": 0.66, "Tenun": 0.70, "Lurik": 0.62, "Songket": 0.72,
                   "Ulos": 0.68, "Jumputan": 0.60, "Endek": 0.69}


async def finalize_epic3_costing_and_ar():
    """EPIC3 — dijalankan di AKHIR pipeline. Idempotent.

    A) Costing: isi products.harga_pokok (proxy rasio kategori) bila kosong, lalu
       backfill inventory_rolls.base_unit_cost/unit_cost dari harga_pokok → WAC valid.
    B) AR Receipt: contoh penerimaan pembayaran (parsial) ke 2 order AR agar
       Collection Worklist & credit gate menampilkan paid/partial yang realistis.
    """
    # ── A) Costing data ──
    prods = await db.products.find({}, {"_id": 0}).to_list(2000)
    hpp_map = {}
    for p in prods:
        hpp = float(p.get("harga_pokok") or 0)
        if hpp <= 0:
            ratio = _HPP_RATIO_SEED.get(p.get("category"), 0.66)
            hpp = round(float(p.get("price", 0) or 0) * ratio, -2)
            if hpp > 0:
                await db.products.update_one({"id": p["id"]}, {"$set": {"harga_pokok": hpp}})
        hpp_map[p["id"]] = hpp
    roll_n = 0
    for r in await db.inventory_rolls.find({}, {"_id": 0, "id": 1, "product_id": 1,
                                               "base_unit_cost": 1, "landed_cost_total": 1}).to_list(10000):
        if r.get("base_unit_cost") not in (None, 0, 0.0):
            continue
        base = round(hpp_map.get(r.get("product_id"), 0.0), 4)
        if base <= 0:
            continue
        landed = float(r.get("landed_cost_total") or 0)
        await db.inventory_rolls.update_one(
            {"id": r["id"]}, {"$set": {"base_unit_cost": base, "unit_cost": round(base + landed, 4)}})
        roll_n += 1
    print(f"✅ EPIC3 costing → harga_pokok set, {roll_n} roll cost backfilled")

    # ── A.2) Snapshot unit_cost (cost-at-sale) ke SO line (P2-3) ──
    # Dilakukan di seed agar data konsisten tanpa perlu restart (backfill startup
    # tetap ada sbg jaring pengaman). Cost = harga_pokok produk (proxy WAC saat jual).
    so_fixed = 0
    async for o in db.sales_orders.find({}, {"_id": 0, "id": 1, "items": 1}):
        items = o.get("items") or []
        changed = False
        for it in items:
            if "unit_cost" in it:
                continue
            it["unit_cost"] = round(float(hpp_map.get(it.get("product_id"), 0.0)), 2)
            changed = True
        if changed:
            await db.sales_orders.update_one({"id": o["id"]}, {"$set": {"items": items}})
            so_fixed += 1
    print(f"✅ EPIC3 costing → unit_cost snapshot ke {so_fixed} SO (P2-3)")

    # ── B) AR Receipt examples (idempotent: skip bila sudah ada) ──
    if await db.ar_receipts.count_documents({}) > 0:
        return
    cash_methods = {"kontan", "tunai", "cash"}
    dead = {"cancelled", "draft", "expired", "rejected"}
    # P1-2 — distribusi AR LINTAS sales (bukan menumpuk di 1 sales).
    cust_sales = {c["id"]: c.get("assigned_sales_id", "") for c in
                  await db.customers.find({}, {"_id": 0, "id": 1, "assigned_sales_id": 1}).to_list(3000)}
    by_sales = {}
    for o in await db.sales_orders.find({}, {"_id": 0}).to_list(500):
        if o.get("status") in dead:
            continue
        method = str((o.get("payment_profile_method") or o.get("payment_term_code") or "")).lower()
        if method in cash_methods:
            continue
        gt = float(o.get("grand_total") or 0)
        if gt <= 0:
            continue
        sid = cust_sales.get(o.get("customer_id"), "")
        by_sales.setdefault(sid, []).append((o, gt))
    for sid in by_sales:
        by_sales[sid].sort(key=lambda t: str(t[0].get("created_at") or ""))

    sales_ids = list(by_sales.keys())
    # Rencana: tiap sales → receipt #1 parsial 50%; bila ada order ke-2 → lunas (sales pertama overpay→deposit).
    plans = []  # (order, gt, fraction, overpay)
    for idx, sid in enumerate(sales_ids):
        orders = by_sales[sid]
        if not orders:
            continue
        plans.append((orders[0][0], orders[0][1], 0.5, 0.0))
        if len(orders) > 1:
            overpay = round(orders[1][1] * 0.1, -3) if idx == 0 else 0.0
            plans.append((orders[1][0], orders[1][1], 1.0, overpay))

    seq = 0
    for o, gt, frac, overpay in plans:
        seq += 1
        applied = round(gt, 2) if frac >= 1.0 else round(gt * frac, -2)
        applied = min(applied, round(gt, 2))
        pay_amt = round(applied + overpay, 2)
        if pay_amt <= 0:
            continue
        rid = new_id("arc")
        number = f"AR-{seq:05d}"
        rdate = ago(days=5 * seq)
        unapplied = round(pay_amt - applied, 2)
        payments = list(o.get("payments") or [])
        payments.append({"id": new_id("pay"), "amount": applied, "receipt_id": rid,
                         "receipt_number": number, "method": "transfer", "date": rdate,
                         "created_at": rdate})
        paid_total = round(sum(float(p.get("amount", 0) or 0) for p in payments), 2)
        status = "paid" if paid_total >= gt - 0.01 else ("partial" if paid_total > 0.01 else "unpaid")
        await db.sales_orders.update_one(
            {"id": o["id"]}, {"$set": {"payments": payments, "paid_total": paid_total,
                                       "payment_status": status, "updated_at": now_iso()}})
        await db.ar_receipts.insert_one({
            "id": rid, "number": number, "customer_id": o.get("customer_id"),
            "customer_name": o.get("customer_name", ""), "entity_id": o.get("entity_id", "ent_ksc"),
            "receipt_date": rdate, "method": "transfer", "amount": pay_amt,
            "used_deposit": 0.0, "total_funds": pay_amt,
            "applied_total": applied, "unapplied_amount": unapplied, "deposit_delta": unapplied,
            "allocations": [{"order_id": o["id"], "order_number": o.get("number", o["id"]),
                             "applied": applied, "outstanding_after": round(gt - paid_total, 2),
                             "payment_status": status}],
            "notes": "Pembayaran (seed)" + (" — overpayment→deposit" if unapplied > 0 else ""),
            "status": "posted", "created_by": "seed", "created_by_name": "System Seed",
            "created_at": rdate, "updated_at": rdate})
        # P2-5 — overpayment → deposit customer.
        if unapplied > 0:
            await db.customers.update_one({"id": o.get("customer_id")},
                                          {"$inc": {"deposit_balance": unapplied}})
        # P0-1 — posting kas masuk (transfer → kas_besar gabungan).
        cnum = await next_doc_number("cash_transactions", "number", "CASH-")
        await db.cash_transactions.insert_one({
            "id": new_id("cash"), "number": cnum, "cash_type": "kas_besar", "direction": "in",
            "amount": pay_amt, "category": "penagihan",
            "description": f"Penerimaan {number} — {o.get('customer_name', '')}",
            "entity_id": "all", "ref_type": "ar_receipt", "ref_id": rid,
            "txn_date": rdate, "status": "posted", "created_by": "seed",
            "created_at": rdate, "updated_at": rdate})
    print(f"✅ EPIC3 AR receipt → {seq} receipt (lintas {len(sales_ids)} sales) + cash posting + deposit (P0-1/P1-2/P2-5)")

    # ── C) EPIC4: rate insentif default (entity 'all' × kategori) ──
    if await db.incentive_rates.count_documents({}) == 0:
        rate_default = {"Batik": 3000, "Tenun": 3500, "Lurik": 2000, "Songket": 6000,
                        "Ulos": 4500, "Jumputan": 2500, "Endek": 4000}
        cats = [c for c in await db.products.distinct("category") if c]
        irate_docs = []
        for cat in sorted(set(cats) | set(rate_default)):
            irate_docs.append({
                "id": new_id("irate"), "entity_id": "all", "category": cat,
                "incentive_unit": "meter", "per_unit_amount": float(rate_default.get(cat, 2500)),
                "discount_threshold_type": "pct", "discount_threshold": 10.0,
                "discount_mechanic": "tier_factor", "discount_factor": 0.5,
                "discount_potong_rp": 0.0, "margin_cap_pct": 50.0,
                "status": "active", "created_at": now_iso(), "updated_at": now_iso(),
            })
        if irate_docs:
            await db.incentive_rates.insert_many(irate_docs)
            print(f"✅ EPIC4 incentive rates → {len(irate_docs)} kategori")



async def seed_entities_and_backfill():
    """Multi-Entity (Fase 0): seed entitas legal + tag entity_id ke data transaksi.

    Distribusi realistis: ~70% ke PT Kain Suka Cita, ~30% ke CV Kanda Suka,
    agar Entity Switcher punya data untuk difilter. Lalu generate notifikasi
    dari kondisi REAL (stok menipis / reservasi mendekati kedaluwarsa).
    """
    await db.business_entities.insert_many([
        {"id": "ent_ksc", "legal_name": "PT Kain Suka Cita", "short_name": "KSC",
         "type": "PT", "npwp": "01.234.567.8-901.000",
         "address": "Jl. Soekarno Hatta No. 100", "city": "Bandung",
         "default_tax_mode": "ppn", "doc_prefix": "KSC", "logo_url": "",
         "status": "active", "created_by": "seed", "created_at": now_iso(), "updated_at": now_iso()},
        {"id": "ent_kanda", "legal_name": "CV Kanda Suka", "short_name": "Kanda",
         "type": "CV", "npwp": "02.345.678.9-012.000",
         "address": "Jl. Mangga Dua Raya No. 22", "city": "Jakarta",
         "default_tax_mode": "non_ppn", "doc_prefix": "KANDA", "logo_url": "",
         "status": "active", "created_by": "seed", "created_at": now_iso(), "updated_at": now_iso()},
    ])
    tagged = 0
    # Multi-entity (F0): entity adalah properti CUSTOMER; sales_orders & invoices
    # MEWARISI entity customer-nya agar relasi customer↔SO↔invoice TIDAK terputus
    # lintas-entitas. (Bug lama: tagging acak per-dokumen membuat customer "yatim"
    # di entitas berbeda dari SO-nya → user sales tak bisa memilih customer sama sekali.)
    # Sebagian kecil customer ditaruh di CV Kanda untuk variasi Entity Switcher,
    # sisanya di PT Kain Suka Cita (entitas utama tim sales).
    KANDA_CUSTOMERS = {"cust_moda_surabaya"}
    cust_entity = {}
    for c in await db.customers.find({}, {"_id": 0, "id": 1}).to_list(2000):
        ent = "ent_kanda" if c["id"] in KANDA_CUSTOMERS else "ent_ksc"
        cust_entity[c["id"]] = ent
        await db.customers.update_one({"id": c["id"]}, {"$set": {"entity_id": ent}})
        tagged += 1
    # Sales orders mewarisi entity customer-nya; tanpa customer → ent_ksc.
    for o in await db.sales_orders.find(
        {}, {"_id": 0, "id": 1, "customer_id": 1, "has_backorder": 1}
    ).to_list(3000):
        ent = cust_entity.get(o.get("customer_id"), "ent_ksc")
        await db.sales_orders.update_one({"id": o["id"]}, {"$set": {"entity_id": ent}})
        # Sinkronkan entity baris backorder HANYA bila array-nya ada (hindari error path).
        if o.get("has_backorder"):
            await db.sales_orders.update_one(
                {"id": o["id"], "backorders.0": {"$exists": True}},
                {"$set": {"backorders.$[].entity_id": ent}})
        tagged += 1
    # Invoices mewarisi entity customer (atau dari SO bila customer tak terpetakan).
    for inv in await db.invoices.find(
        {}, {"_id": 0, "id": 1, "customer_id": 1, "order_id": 1, "sales_order_id": 1}
    ).to_list(3000):
        ent = cust_entity.get(inv.get("customer_id"))
        if not ent:
            oid = inv.get("order_id") or inv.get("sales_order_id")
            so = await db.sales_orders.find_one({"id": oid}, {"_id": 0, "entity_id": 1}) if oid else None
            ent = (so or {}).get("entity_id") or "ent_ksc"
        await db.invoices.update_one({"id": inv["id"]}, {"$set": {"entity_id": ent}})
        tagged += 1
    # Purchase orders: acak ~70/30 (berbasis vendor, tak terkait customer) → variasi entitas.
    for d in await db.purchase_orders.find({}, {"_id": 0, "id": 1}).to_list(2000):
        ent = "ent_kanda" if random.random() < 0.3 else "ent_ksc"
        await db.purchase_orders.update_one({"id": d["id"]}, {"$set": {"entity_id": ent}})
        tagged += 1
    # F2b — pin demo Pending SO (SO-0009 → cust_textile_medan = ent_ksc) + PO incoming batik ke
    # entitas yang SAMA (ent_ksc) agar coverage Pending SO selalu "Terjamin".
    await db.sales_orders.update_one(
        {"number": "SO-0009"},
        {"$set": {"entity_id": "ent_ksc", "backorders.$[].entity_id": "ent_ksc"}})
    await db.purchase_orders.update_many(
        {"status": {"$in": ["pending", "created", "approved", "sent"]},
         "items.product_id": "prod_batik_mega"},
        {"$set": {"entity_id": "ent_ksc"}})
    # Notifikasi awal dari data nyata
    try:
        from services.notification_service import generate_system_notifications
        created = await generate_system_notifications()
    except Exception as e:  # pragma: no cover
        created = 0
        print(f"  (notif generate skipped: {e})")
    print(f"✅ Entities seeded (2) · entity_id tagged → {tagged} dok · {created} notifikasi")


async def backfill_order_pricing():
    """Fase 1B — hitung ulang breakdown harga (diskon item/order + PPN) untuk tiap
    sales_order memakai engine YANG SAMA dengan create_order, agar seed tidak drift
    dari aplikasi (PPN mengikuti PKP/non-PKP entitas; invarian total_amount tetap GROSS)."""
    from services.config_service import compute_order_pricing, evaluate_approval
    gs = await db.system_settings.find_one({"scope": "global"}, {"_id": 0}) or {}
    default_term = (gs.get("finance", {}) or {}).get("default_payment_term_code", "NET30")
    terms = {t["code"]: t for t in await db.payment_terms.find({}, {"_id": 0}).to_list(50)}
    patched = 0
    for o in await db.sales_orders.find({}, {"_id": 0}).to_list(500):
        raw_items = [{
            "product_id": it.get("product_id"), "sku": it.get("sku"),
            "product_name": it.get("product_name"), "quantity": it.get("quantity", 0),
            "unit": it.get("unit", "meter"), "price": it.get("price", 0),
            "discount_percent": it.get("discount_percent", 0) or 0,
        } for it in o.get("items", [])]
        pricing = await compute_order_pricing(
            raw_items, o.get("entity_id"), o.get("order_discount_percent", 0) or 0)
        term_code = o.get("payment_term_code") or default_term
        appr = await evaluate_approval("sales_order", pricing["grand_total"], o.get("entity_id"))
        await db.sales_orders.update_one({"id": o["id"]}, {"$set": {
            "items": pricing["items"], "total_amount": pricing["total_amount"],
            "items_discount_total": pricing["items_discount_total"],
            "order_discount_percent": pricing["order_discount_percent"],
            "order_discount_amount": pricing["order_discount_amount"],
            "discount_total": pricing["discount_total"],
            "net_subtotal": pricing["net_subtotal"], "dpp": pricing["dpp"],
            "ppn_rate": pricing["ppn_rate"], "ppn_mode": pricing["ppn_mode"],
            "is_pkp": pricing["is_pkp"], "ppn_amount": pricing["ppn_amount"],
            "grand_total": pricing["grand_total"],
            "payment_term_code": term_code,
            "payment_term_name": (terms.get(term_code) or {}).get("name", term_code),
            "approval_required": appr["requires_approval"],
            "required_approval_role": appr["required_role"],
            "approval_amount": pricing["grand_total"],
        }})
        patched += 1
    print(f"✅ Order pricing backfilled (diskon+PPN+approval, engine create_order) → {patched} order")


async def seed_price_approvals():
    """Sub-fase 1.7 — contoh special price (1 approved + 1 pending), idempotent."""
    if await db.price_approvals.count_documents({}) > 0:
        return 0
    custs = await db.customers.find({"status": "active"}, {"_id": 0}).sort("created_at", 1).to_list(5)
    prods = await db.products.find({"status": "active"}, {"_id": 0}).sort("created_at", 1).to_list(5)
    if not custs or not prods:
        return 0
    sales_user = await db.users.find_one({"role": "sales"}, {"_id": 0}) or {}
    mgr = await db.users.find_one({"role": "manager"}, {"_id": 0}) or {}
    future = (datetime.now(timezone.utc) + timedelta(days=120)).date().isoformat() + "T23:59:59+00:00"
    c0, p0 = custs[0], prods[0]
    c1 = custs[1] if len(custs) > 1 else custs[0]
    p1 = prods[1] if len(prods) > 1 else prods[0]
    docs = [
        {
            "id": new_id("pra"), "entity_id": c0.get("entity_id") or "ent_ksc",
            "customer_id": c0["id"], "customer_name": c0.get("name", ""),
            "product_id": p0["id"], "sku": p0.get("sku", ""), "product_name": p0.get("name", ""),
            "normal_price": round(float(p0.get("price", 0) or 0), 2),
            "requested_price": round(float(p0.get("price", 0) or 0) * 0.85, 2),
            "min_quantity": 20, "unit": p0.get("base_unit", "meter"),
            "reason": "Repeat order volume besar — nego harga grosir",
            "valid_from": now_iso(), "valid_until": future,
            "status": "approved", "attachments": [],
            "requested_by": sales_user.get("id"), "requested_by_name": sales_user.get("name", "Sales"),
            "approved_by": mgr.get("id"), "approved_by_name": mgr.get("name", "Manager"),
            "decision_notes": "Disetujui untuk pelanggan loyal", "decided_at": now_iso(),
            "created_at": now_iso(), "updated_at": now_iso(),
        },
        {
            "id": new_id("pra"), "entity_id": c1.get("entity_id") or "ent_ksc",
            "customer_id": c1["id"], "customer_name": c1.get("name", ""),
            "product_id": p1["id"], "sku": p1.get("sku", ""), "product_name": p1.get("name", ""),
            "normal_price": round(float(p1.get("price", 0) or 0), 2),
            "requested_price": round(float(p1.get("price", 0) or 0) * 0.90, 2),
            "min_quantity": 10, "unit": p1.get("base_unit", "meter"),
            "reason": "Permintaan diskon promo pameran",
            "valid_from": now_iso(), "valid_until": "",
            "status": "pending", "attachments": [],
            "requested_by": sales_user.get("id"), "requested_by_name": sales_user.get("name", "Sales"),
            "approved_by": None, "approved_by_name": None,
            "decision_notes": "", "decided_at": None,
            "created_at": now_iso(), "updated_at": now_iso(),
        },
    ]
    await db.price_approvals.insert_many(docs)
    print(f"✅ Price approvals seeded ({len(docs)})")
    return len(docs)


async def seed_pegging_examples():
    """Sub-fase 1.7 — contoh pegging/earmark (soft hold roll ke customer), idempotent.
    Invarian (verify_data_integrity): earmarked_for terisi ⟹ status 'available'."""
    if await db.inventory_rolls.count_documents({"earmarked_for": {"$ne": None}}) > 0:
        return 0
    admin = await db.users.find_one({"role": "admin"}, {"_id": 0}) or {}
    by_name = admin.get("name", "System Seed")
    rolls = await db.inventory_rolls.find(
        {"status": "available", "length_remaining": {"$gt": 0}}, {"_id": 0}
    ).sort("created_at", 1).to_list(5000)
    cust_by_entity = {}
    notes = ["Hold untuk repeat order bulanan", "Earmark menunggu PO customer"]
    pegged = 0
    for r in rolls:
        if pegged >= 2:
            break
        owner = r.get("owner_entity_id")
        if owner not in cust_by_entity:
            cust_by_entity[owner] = await db.customers.find_one(
                {"entity_id": owner, "status": "active"}, {"_id": 0}
            )
        cu = cust_by_entity.get(owner)
        if not cu:
            continue
        ear = {"type": "customer", "id": cu["id"], "name": cu.get("name", cu["id"]),
               "note": notes[pegged], "by": by_name, "at": now_iso()}
        await db.inventory_rolls.update_one(
            {"id": r["id"]}, {"$set": {"earmarked_for": ear, "updated_at": now_iso()}})
        pegged += 1
    print(f"✅ Pegging examples seeded ({pegged} roll di-earmark)")
    return pegged


async def seed_shipment_examples():
    """Sub-fase 1.8 — normalisasi SO lama berstatus 'dispatched' ke vocabulary baru
    (shipped/done/partially_shipped) + buat record `shipments` (No. Surat Jalan). Idempotent.
    Invarian: shipped_qty≤quantity; Σshipments.qty==Σtask.shipped_qty; status SO⟺progres task."""
    if await db.shipments.count_documents({}) > 0:
        return 0
    sos = await db.sales_orders.find({"status": "dispatched"}, {"_id": 0}).sort("created_at", 1).to_list(100)
    seq = 0
    total_ship = 0

    def _mk(o, t, qty, partial):
        nonlocal seq
        seq += 1
        return {
            "id": new_id("shp"), "shipment_no": f"SJ-{seq:05d}",
            "order_id": o["id"], "order_number": o.get("number", ""), "task_id": t["id"],
            "allocation_id": t.get("allocation_id"), "warehouse_id": t.get("warehouse_id"),
            "warehouse_name": t.get("warehouse_name", ""), "warehouse_city": t.get("warehouse_city", ""),
            "product_id": t.get("product_id"), "product_name": t.get("product_name", ""),
            "sku": t.get("sku", ""), "qty": round(qty, 2), "unit": t.get("unit", "meter"),
            "rolls": [], "is_partial": partial, "status": "dispatched",
            "created_by": "System Seed", "created_at": o.get("created_at", now_iso()),
        }

    for idx, o in enumerate(sos):
        tasks = await db.wms_tasks.find(
            {"order_id": o["id"], "flow_type": "outbound"}, {"_id": 0}
        ).sort("created_at", 1).to_list(100)
        if not tasks:
            await db.sales_orders.update_one({"id": o["id"]}, {"$set": {"status": "confirmed"}})
            continue
        make_partial = (idx == len(sos) - 1 and len(sos) >= 3)
        if make_partial:
            t0 = tasks[0]
            q0 = float(t0.get("quantity", 0) or 0)
            half = round(max(1.0, int(q0 / 2)), 2)
            await db.wms_tasks.update_one({"id": t0["id"]}, {"$set": {
                "picked_qty": q0, "shipped_qty": half, "status": "partially_shipped", "updated_at": now_iso()}})
            await db.shipments.insert_one(_mk(o, t0, half, True)); total_ship += 1
            for t in tasks[1:]:
                q = float(t.get("quantity", 0) or 0)
                await db.wms_tasks.update_one({"id": t["id"]}, {"$set": {
                    "picked_qty": q, "shipped_qty": 0, "status": "packing", "updated_at": now_iso()}})
            await db.sales_orders.update_one({"id": o["id"]}, {"$set": {
                "status": "partially_shipped", "updated_at": now_iso()}})
        else:
            for t in tasks:
                q = float(t.get("quantity", 0) or 0)
                await db.wms_tasks.update_one({"id": t["id"]}, {"$set": {
                    "picked_qty": q, "shipped_qty": q, "status": "dispatched", "updated_at": now_iso()}})
                await db.shipments.insert_one(_mk(o, t, q, False)); total_ship += 1
            await db.sales_orders.update_one({"id": o["id"]}, {"$set": {
                "status": ("done" if idx == 0 else "shipped"), "updated_at": now_iso()}})
    print(f"✅ Shipment examples seeded ({total_ship} shipment, {len(sos)} SO dinormalisasi)")
    return total_ship


async def seed_tax_invoice_examples():
    """Sub-fase 1.9 — contoh Faktur Pajak Jual (tax_invoices), idempotent.
    Pilih 1 SO entitas PKP (default_tax_mode=ppn) dgn ppn_amount>0 & status terkonfirmasi ke atas.
    Invarian: PPN==DPP×rate; Grand==DPP+PPN; ref order valid; is_pkp & ppn>0; nomor unik."""
    if await db.tax_invoices.count_documents({}) > 0:
        return 0
    admin = await db.users.find_one({"role": "admin"}, {"_id": 0}) or {}
    by_name = admin.get("name", "System Seed")
    pkp_entities = {e["id"]: e for e in await db.business_entities.find(
        {"default_tax_mode": "ppn"}, {"_id": 0}).to_list(50)}
    eligible_status = {"confirmed", "partially_picked", "picked",
                       "partially_shipped", "shipped", "done"}
    orders = await db.sales_orders.find(
        {"status": {"$in": list(eligible_status)}}, {"_id": 0}).sort("created_at", 1).to_list(200)
    seq = 0
    made = 0
    for o in orders:
        if made >= 2:
            break
        entity = pkp_entities.get(o.get("entity_id"))
        if not entity or float(o.get("ppn_amount", 0) or 0) <= 0:
            continue
        customer = await db.customers.find_one({"id": o.get("customer_id")}, {"_id": 0}) or {}
        addrs = customer.get("addresses", []) or []
        addr = next((a for a in addrs if a.get("is_primary")), addrs[0] if addrs else {})
        items = [{"product_name": it.get("product_name", ""), "sku": it.get("sku", ""),
                  "quantity": float(it.get("quantity", 0) or 0), "unit": it.get("unit", ""),
                  "price": float(it.get("price", 0) or 0), "subtotal": float(it.get("subtotal", 0) or 0),
                  "discount_amount": float(it.get("discount_amount", 0) or 0),
                  "line_total": float(it.get("line_total", it.get("subtotal", 0)) or 0)}
                 for it in o.get("items", [])]
        seq += 1
        fkt = {
            "id": new_id("fkt"), "number": f"FKT-{seq:05d}", "nsfp": "",
            "kode_transaksi": "01", "status": "normal",
            "replaces_id": None, "replaced_by_id": None, "cancel_reason": "",
            "faktur_date": now_iso(),
            "order_id": o["id"], "order_number": o.get("number", ""),
            "entity_id": entity["id"],
            "seller_name": entity.get("legal_name", "Kain Nusantara"),
            "seller_npwp": entity.get("npwp", ""),
            "seller_address": f"{entity.get('address','')}, {entity.get('city','')}".strip(", "),
            "customer_id": customer.get("id", o.get("customer_id")),
            "customer_name": o.get("customer_name", customer.get("name", "")),
            "customer_npwp": customer.get("npwp", ""),
            "customer_address": f"{addr.get('address','')}, {addr.get('city','')}".strip(", "),
            "has_customer_npwp": bool(customer.get("npwp")),
            "items": items,
            "total_amount": float(o.get("total_amount", 0) or 0),
            "discount_total": float(o.get("discount_total", 0) or 0),
            "net_subtotal": float(o.get("net_subtotal", 0) or 0),
            "dpp": float(o.get("dpp", 0) or 0),
            "ppn_rate": float(o.get("ppn_rate", 0) or 0),
            "ppn_mode": o.get("ppn_mode", "excluded"),
            "ppn_amount": float(o.get("ppn_amount", 0) or 0),
            "grand_total": float(o.get("grand_total", 0) or 0),
            "is_pkp": True,
            "created_by": by_name, "created_at": now_iso(), "updated_at": now_iso(),
        }
        await db.tax_invoices.insert_one(dict(fkt))
        made += 1
    print(f"✅ Tax invoice examples seeded ({made} Faktur Pajak)")
    return made


async def seed_sales_returns_examples():
    """Sub-fase 1.11 — contoh Returns & Barang Sisa (sales_returns), idempotent.
    Membuat 1 return retur (pending_approval) + 1 barang sisa/bs (draft) dari SO eligible."""
    if await db.sales_returns.count_documents({}) > 0:
        return 0

    allowed_statuses = {"confirmed", "partially_picked", "picked",
                        "partially_shipped", "shipped", "done"}
    orders = await db.sales_orders.find(
        {"status": {"$in": list(allowed_statuses)}}, {"_id": 0}
    ).sort("created_at", 1).to_list(20)

    if not orders:
        print("⚠️  seed_sales_returns: tidak ada SO eligible, skip.")
        return 0

    made = 0
    now = now_iso()

    # ── Return 1: retur (pending_approval) dari SO-0001 ───────────────────
    so1 = next((o for o in orders if o["status"] == "done"), orders[0])
    items_so1 = so1.get("items", [])[:2]
    return_items_1 = [
        {
            "product_id":        it.get("product_id", "prod_batik_tulis"),
            "product_name":      it.get("product_name", "Batik Tulis"),
            "quantity_returned": round(float(it.get("quantity", 10)) * 0.2, 1),
            "unit":              it.get("unit", "meter"),
            "reason":            "Cacat produksi — motif buram",
            "condition":         "damaged",
        }
        for it in items_so1
    ] or [{
        "product_id":        "prod_batik_tulis",
        "product_name":      "Batik Tulis Solo",
        "quantity_returned": 5.0,
        "unit":              "meter",
        "reason":            "Cacat produksi — motif buram",
        "condition":         "damaged",
    }]

    ret1_number = "SRET-00001"
    ret1 = {
        "id":           new_id("sret"),
        "number":       ret1_number,
        "order_id":     so1["id"],
        "order_number": so1.get("number", so1["id"]),
        "customer_id":  so1.get("customer_id", ""),
        "customer_name":so1.get("customer_name", ""),
        "entity_id":    so1.get("entity_id", "ent_ksc"),
        "return_type":  "retur",
        "status":       "pending_approval",
        "items":        return_items_1,
        "notes":        "Pelanggan komplain: 2 rol kain motif tidak sesuai pesanan.",
        "attachments":  [],
        "stock_adjusted": False,
        "created_by":   "sales@kainnusantara.id",
        "approved_by":  None, "approved_at": None,
        "rejected_by":  None, "rejected_at": None, "reject_reason": None,
        "created_at":   now, "updated_at": now,
    }
    await db.sales_returns.insert_one(ret1)
    made += 1

    # ── Return 2: bs/Barang Sisa (draft) dari SO-0002 ─────────────────────
    so2 = next(
        (o for o in orders if o["id"] != so1["id"] and o["status"] in {"shipped", "partially_shipped"}),
        next((o for o in orders if o["id"] != so1["id"]), None),
    )
    if so2:
        items_so2 = so2.get("items", [])[:1]
        return_items_2 = [
            {
                "product_id":        it.get("product_id", "prod_tenun_ikat"),
                "product_name":      it.get("product_name", "Tenun Ikat"),
                "quantity_returned": round(float(it.get("quantity", 8)) * 0.15, 1),
                "unit":              it.get("unit", "meter"),
                "reason":            "Sisa produksi — kain tidak habis terpakai",
                "condition":         "ok",
            }
            for it in items_so2
        ] or [{
            "product_id":        "prod_tenun_ikat",
            "product_name":      "Tenun Ikat NTT",
            "quantity_returned": 3.0,
            "unit":              "meter",
            "reason":            "Sisa produksi",
            "condition":         "ok",
        }]

        ret2_number = "SRET-00002"
        ret2 = {
            "id":           new_id("sret"),
            "number":       ret2_number,
            "order_id":     so2["id"],
            "order_number": so2.get("number", so2["id"]),
            "customer_id":  so2.get("customer_id", ""),
            "customer_name":so2.get("customer_name", ""),
            "entity_id":    so2.get("entity_id", "ent_ksc"),
            "return_type":  "bs",
            "status":       "draft",
            "items":        return_items_2,
            "notes":        "Kain sisa dari pengiriman terakhir dikembalikan ke gudang.",
            "attachments":  [],
            "stock_adjusted": False,
            "created_by":   "sales@kainnusantara.id",
            "approved_by":  None, "approved_at": None,
            "rejected_by":  None, "rejected_at": None, "reject_reason": None,
            "created_at":   now, "updated_at": now,
        }
        await db.sales_returns.insert_one(ret2)
        made += 1

    print(f"✅ Sales return examples seeded ({made} dokumen: retur + BS)")
    return made


async def seed_special_order_examples():
    """Sub-fase 1.12 — contoh Special Orders (special_orders), idempotent.
    Membuat 2 special order: 1 draft (budget rendah) + 1 confirmed (approved)."""
    if await db.special_orders.count_documents({}) > 0:
        return 0

    customers = {c["id"]: c for c in await db.customers.find({}, {"_id": 0}).to_list(10)}
    now = now_iso()

    cust1 = customers.get("cust_toko_kain", {})
    cust1_addr = (cust1.get("addresses") or [{}])[0]
    entity_id1 = "ent_ksc"

    cust2 = customers.get("cust_butik_bali", {})
    cust2_addr = (cust2.get("addresses") or [{}])[0]
    entity_id2 = "ent_kanda"

    made = 0

    # ── Special Order 1: Batik Motif Custom — draft (budget < threshold) ──
    sord1_id = new_id("sord")
    sord1 = {
        "id":            sord1_id,
        "number":        "SORD-260618-0001",
        "status":        "draft",
        "type":          "special_order",
        "customer_id":   cust1.get("id", "cust_toko_kain"),
        "customer_name": cust1.get("name", "Toko Kain Sejahtera"),
        "customer_email":cust1.get("email", ""),
        "customer_phone":cust1.get("phone", ""),
        "shipping_address": cust1_addr,
        "custom_item": {
            "description":    "Batik Tulis Motif Parang Rusak — edisi ulang tahun perusahaan",
            "specifications": {
                "motif":    "Parang Rusak Barong",
                "warna":    "Biru Indigo + Coklat Sogan",
                "panjang":  "12 meter per rol",
                "lebar":    "110 cm",
                "proses":   "Tulis tangan",
                "bahan":    "Primissima 100% katun",
            },
            "quantity":    20.0,
            "unit":        "meter",
            "target_price":350_000,
            "notes":       "Deadline: 45 hari kerja. Contoh motif sudah disetujui.",
        },
        "total_amount":    7_000_000.0,
        "requires_approval": False,
        "approval_threshold": 10_000_000,
        "expected_delivery": "2026-08-15",
        "entity_id":     entity_id1,
        "notes":         "Order khusus untuk acara HUT-25 pelanggan.",
        "status_history": [{"status": "draft", "timestamp": now, "user": "sales@kainnusantara.id"}],
        "created_at":    now, "created_by": "sales@kainnusantara.id",
        "updated_at":    now,
    }
    await db.special_orders.insert_one(sord1)
    made += 1

    # ── Special Order 2: Songket Premium — confirmed ────────────────────────
    sord2_id = new_id("sord")
    sord2 = {
        "id":            sord2_id,
        "number":        "SORD-260618-0002",
        "status":        "confirmed",
        "type":          "special_order",
        "customer_id":   cust2.get("id", "cust_butik_bali"),
        "customer_name": cust2.get("name", "Butik Bali Indah"),
        "customer_email":cust2.get("email", ""),
        "customer_phone":cust2.get("phone", ""),
        "shipping_address": cust2_addr,
        "custom_item": {
            "description":    "Kain Songket Bali Premium — untuk koleksi haute couture",
            "specifications": {
                "motif":    "Merak Ngigel",
                "benang":   "Emas 24K + Sutra ATBM",
                "lebar":    "115 cm",
                "berat":    "450 gr/m",
                "finishing":"Edging bordir manual",
            },
            "quantity":    8.0,
            "unit":        "meter",
            "target_price":850_000,
            "notes":       "Setiap meter dikerjakan 1 pengrajin. Estimasi 60 hari.",
        },
        "total_amount":    6_800_000.0,
        "requires_approval": False,
        "approval_threshold": 10_000_000,
        "expected_delivery": "2026-09-01",
        "entity_id":     entity_id2,
        "notes":         "Sudah down payment 30% (IDR 2.040.000).",
        "status_history": [
            {"status": "draft",     "timestamp": ago(days=5), "user": "sales@kainnusantara.id"},
            {"status": "confirmed", "timestamp": ago(days=3), "user": "admin@kainnusantara.id"},
        ],
        "confirmed_at":  ago(days=3),
        "created_at":    ago(days=5), "created_by": "sales@kainnusantara.id",
        "updated_at":    ago(days=3),
    }
    await db.special_orders.insert_one(sord2)
    made += 1

    print(f"✅ Special order examples seeded ({made} dokumen: draft + confirmed)")
    return made


async def seed_purchase_approval_examples():
    """Fase 3 — contoh PO untuk alur Approval Pembelian (waiting/approved/rejected).
    PO bernilai > Rp 100 jt → butuh approval role 'manager' (sesuai approval_rules)."""
    # PO-00007 — MENUNGGU approval (belum ada inbound task; task baru dibuat saat approve)
    await db.purchase_orders.insert_one({
        "id": "po_007", "po_number": "PO-00007",
        "supplier_name": "Palembang Silk House", "supplier_contact": "Ibu Sri | 081299900004",
        "supplier_npwp": "24.444.555.6-404.000",
        "warehouse_id": "wh_jakarta", "status": "waiting_approval",
        "approval_required": True, "required_approval_role": "manager", "approval_status": "pending",
        "items": [
            {"product_id": "prod_songket_palembang", "sku": "SGK-PLB-001",
             "product_name": "Songket Palembang Benang Emas",
             "quantity": 320.0, "received_qty": 0.0, "unit": "meter", "price": 420000, "status": "pending"},
        ],
        "warehouse_name": "Gudang Jakarta Utara", "warehouse_city": "Jakarta",
        "total_amount": 134400000.0,
        "expected_delivery_date": ago(days=-7),
        "notes": "Restock songket Q2 — menunggu persetujuan manajemen",
        "timeline": [
            {"event": "created", "label": "PO dibuat", "actor": "Admin",
             "at": ago(days=2), "note": "1 item · Rp 134.400.000"},
            {"event": "submitted_for_approval", "label": "Menunggu persetujuan manager",
             "actor": "Admin", "at": ago(days=2), "note": "nilai melebihi batas"},
        ],
        "created_by": "Admin", "created_at": ago(days=2), "updated_at": ago(days=2),
    })
    # PO-00008 — DITOLAK
    await db.purchase_orders.insert_one({
        "id": "po_008", "po_number": "PO-00008",
        "supplier_name": "Bali Weave Studio", "supplier_contact": "Ibu Kadek | 081388800006",
        "supplier_npwp": "26.666.777.8-406.000",
        "warehouse_id": "wh_surabaya", "status": "rejected",
        "approval_required": True, "required_approval_role": "manager", "approval_status": "rejected",
        "rejected_by": "Sari Dewi", "rejection_reason": "Harga di atas anggaran, negosiasi ulang.",
        "items": [
            {"product_id": "prod_tenun_ikat", "sku": "TNI-GRGD-001",
             "product_name": "Tenun Ikat Garuda Premium",
             "quantity": 700.0, "received_qty": 0.0, "unit": "meter", "price": 200000, "status": "cancelled"},
        ],
        "warehouse_name": "Gudang Surabaya Rungkut", "warehouse_city": "Surabaya",
        "total_amount": 140000000.0,
        "expected_delivery_date": ago(days=-10),
        "notes": "Permintaan tenun ikat partai besar",
        "timeline": [
            {"event": "created", "label": "PO dibuat", "actor": "Admin",
             "at": ago(days=5), "note": "1 item · Rp 140.000.000"},
            {"event": "submitted_for_approval", "label": "Menunggu persetujuan manager",
             "actor": "Admin", "at": ago(days=5), "note": "nilai melebihi batas"},
            {"event": "rejected", "label": "Ditolak", "actor": "Sari Dewi",
             "at": ago(days=4), "note": "Harga di atas anggaran, negosiasi ulang."},
        ],
        "created_by": "Admin", "created_at": ago(days=5), "updated_at": ago(days=4),
    })
    # PO-00009 — DISETUJUI (status pending, ada inbound task menunggu receiving)
    task9_id = new_id("wms")
    await db.purchase_orders.insert_one({
        "id": "po_009", "po_number": "PO-00009",
        "supplier_name": "Cirebon Craft", "supplier_contact": "Pak Wahyu | 081234500001",
        "supplier_npwp": "21.111.222.3-401.000",
        "warehouse_id": "wh_jakarta", "status": "pending",
        "approval_required": True, "required_approval_role": "manager", "approval_status": "approved",
        "approved_by": "Sari Dewi", "approved_at": ago(days=3),
        "items": [
            {"product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
             "product_name": "Batik Mega Mendung Premium",
             "quantity": 800.0, "received_qty": 0.0, "unit": "meter", "price": 165000,
             "status": "pending", "inbound_task_id": task9_id},
        ],
        "warehouse_name": "Gudang Jakarta Utara", "warehouse_city": "Jakarta",
        "total_amount": 132000000.0,
        "expected_delivery_date": ago(days=-5),
        "notes": "Disetujui manajemen — menunggu kedatangan barang",
        "timeline": [
            {"event": "created", "label": "PO dibuat", "actor": "Admin",
             "at": ago(days=4), "note": "1 item · Rp 132.000.000"},
            {"event": "submitted_for_approval", "label": "Menunggu persetujuan manager",
             "actor": "Admin", "at": ago(days=4), "note": "nilai melebihi batas"},
            {"event": "approved", "label": "Disetujui", "actor": "Sari Dewi",
             "at": ago(days=3), "note": "oleh role manager"},
        ],
        "created_by": "Admin", "created_at": ago(days=4), "updated_at": ago(days=3),
    })
    await db.wms_tasks.insert_one({
        "id": task9_id, "flow_type": "inbound", "source_type": "purchase_order", "task_subtype": "receiving",
        "po_id": "po_009", "po_number": "PO-00009",
        "product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
        "product_name": "Batik Mega Mendung Premium",
        "warehouse_id": "wh_jakarta", "warehouse_name": "Gudang Jakarta Utara",
        "expected_qty": 800.0, "received_qty": 0.0, "quantity": 0.0,
        "unit": "meter", "status": "pending", "supplier_name": "Cirebon Craft",
        "bin_id": "", "batch": "", "lot": "", "scan_log": [], "escalation": None,
        "created_at": ago(days=3), "updated_at": ago(days=3),
    })
    # PO-00010 — MENUNGGU approval BERJENJANG (Fase 7.1): nilai ≥ Rp 500jt → 2 tingkat
    # (L1 Manager, L2 Direksi/admin). Keduanya masih PENDING (antri di tingkat 1).
    await db.purchase_orders.insert_one({
        "id": "po_010", "po_number": "PO-00010",
        "supplier_name": "Palembang Silk House", "supplier_contact": "Ibu Sri | 081299900004",
        "supplier_npwp": "24.444.555.6-404.000",
        "warehouse_id": "wh_jakarta", "status": "waiting_approval",
        "approval_required": True, "required_approval_role": "manager", "approval_status": "pending",
        "approval_chain": [
            {"level": 1, "required_role": "manager", "label": "Approval", "status": "pending",
             "approved_by": "", "approved_by_id": "", "approved_at": ""},
            {"level": 2, "required_role": "admin", "label": "Direksi", "status": "pending",
             "approved_by": "", "approved_by_id": "", "approved_at": ""},
        ],
        "approval_level_current": 1, "approval_levels_total": 2,
        "approval_amount": 588000000.0, "approval_reason": "amount_threshold",
        "price_deviation": {"flagged": False},
        "items": [
            {"product_id": "prod_songket_palembang", "sku": "SGK-PLB-001",
             "product_name": "Songket Palembang Benang Emas",
             "quantity": 1400.0, "received_qty": 0.0, "unit": "meter", "price": 420000, "status": "pending"},
        ],
        "warehouse_name": "Gudang Jakarta Utara", "warehouse_city": "Jakarta",
        "total_amount": 588000000.0,
        "expected_delivery_date": ago(days=-14),
        "notes": "Order besar songket — butuh persetujuan berjenjang (Manager → Direksi)",
        "timeline": [
            {"event": "created", "label": "PO dibuat", "actor": "Admin",
             "at": ago(days=1), "note": "1 item · Rp 588.000.000"},
            {"event": "submitted_for_approval", "label": "Menunggu persetujuan manager",
             "actor": "Admin", "at": ago(days=1), "note": "nilai ≥ Rp 500jt → 2 tingkat (Manager, Direksi)"},
        ],
        "created_by": "Admin", "created_at": ago(days=1), "updated_at": ago(days=1),
    })
    # PO-00011 — BERJENJANG, tingkat 1 (Manager) SUDAH disetujui, menunggu tingkat 2 (Direksi/admin).
    await db.purchase_orders.insert_one({
        "id": "po_011", "po_number": "PO-00011",
        "supplier_name": "Bali Weave Studio", "supplier_contact": "Ibu Kadek | 081388800006",
        "supplier_npwp": "26.666.777.8-406.000",
        "warehouse_id": "wh_surabaya", "status": "waiting_approval",
        "approval_required": True, "required_approval_role": "admin", "approval_status": "pending",
        "approval_chain": [
            {"level": 1, "required_role": "manager", "label": "Approval", "status": "approved",
             "approved_by": "Dewi Rahayu", "approved_by_id": "user_manager_01", "approved_at": ago(days=1)},
            {"level": 2, "required_role": "admin", "label": "Direksi", "status": "pending",
             "approved_by": "", "approved_by_id": "", "approved_at": ""},
        ],
        "approval_level_current": 2, "approval_levels_total": 2,
        "approval_amount": 520000000.0, "approval_reason": "amount_threshold",
        "price_deviation": {"flagged": False},
        "items": [
            {"product_id": "prod_tenun_ikat", "sku": "TNI-GRGD-001",
             "product_name": "Tenun Ikat Garuda Premium",
             "quantity": 2600.0, "received_qty": 0.0, "unit": "meter", "price": 200000, "status": "pending"},
        ],
        "warehouse_name": "Gudang Surabaya Rungkut", "warehouse_city": "Surabaya",
        "total_amount": 520000000.0,
        "expected_delivery_date": ago(days=-12),
        "notes": "Tenun ikat partai besar — Manager sudah setuju, menunggu persetujuan Direksi",
        "timeline": [
            {"event": "created", "label": "PO dibuat", "actor": "Admin",
             "at": ago(days=2), "note": "1 item · Rp 520.000.000"},
            {"event": "submitted_for_approval", "label": "Menunggu persetujuan manager",
             "actor": "Admin", "at": ago(days=2), "note": "nilai ≥ Rp 500jt → 2 tingkat"},
            {"event": "approved_level", "label": "Disetujui tingkat 1 (Approval)",
             "actor": "Dewi Rahayu", "at": ago(days=1), "note": "Lanjut ke Direksi"},
        ],
        "created_by": "Admin", "created_at": ago(days=2), "updated_at": ago(days=1),
    })
    print("✅ Purchase approval examples seeded (PO-00007 waiting, PO-00008 rejected, PO-00009 approved, PO-00010/00011 multi-level)")


async def seed_suppliers():
    """Fase 3 — master supplier (mencakup semua supplier_name di PO)."""
    suppliers = [
        {"name": "Cirebon Craft",        "npwp": "21.111.222.3-401.000", "pic_name": "Pak Wahyu",
         "phone": "081234500001", "city": "Cirebon",   "goods_type": "Batik & Kain Cap",        "entity_id": "ent_ksc",   "lead_time_days": 7},
        {"name": "NTT Weaving Co",        "npwp": "22.222.333.4-402.000", "pic_name": "Ibu Agnes",
         "phone": "082345600002", "city": "Kupang",    "goods_type": "Tenun Ikat",              "entity_id": "ent_ksc",   "lead_time_days": 21},
        {"name": "Solo Weave",            "npwp": "23.333.444.5-403.000", "pic_name": "Pak Joko",
         "phone": "085012300003", "city": "Solo",      "goods_type": "Lurik & Benang",          "entity_id": "ent_ksc",   "lead_time_days": 10},
        {"name": "Palembang Silk House",  "npwp": "24.444.555.6-404.000", "pic_name": "Ibu Sri",
         "phone": "081299900004", "city": "Palembang", "goods_type": "Songket & Benang Emas",   "entity_id": "ent_ksc",   "lead_time_days": 14},
        {"name": "Toba Craft",            "npwp": "",                     "pic_name": "Pak Sahat",
         "phone": "081377700005", "city": "Medan",     "goods_type": "Ulos",                    "entity_id": "ent_kanda", "lead_time_days": 18},
        {"name": "Bali Weave Studio",     "npwp": "26.666.777.8-406.000", "pic_name": "Ibu Kadek",
         "phone": "081388800006", "city": "Denpasar",  "goods_type": "Endek & Tenun Bali",      "entity_id": "ent_kanda", "lead_time_days": 12},
    ]
    docs = []
    for i, s in enumerate(suppliers, start=1):
        docs.append({
            "id": new_id("sup"), "code": f"SUP-{i:05d}", "name": s["name"],
            "npwp": s["npwp"], "pic_name": s["pic_name"], "phone": s["phone"],
            "email": f"sales@{s['name'].lower().replace(' ', '')}.co.id", "address": "",
            "city": s["city"], "goods_type": s["goods_type"], "payment_term_code": "NET30",
            "lead_time_days": s["lead_time_days"],
            "entity_id": s["entity_id"], "notes": "", "status": "active", "created_by": "seed",
            "created_at": ago(days=120), "updated_at": ago(days=120),
        })
    await db.suppliers.insert_many(docs)
    # Link existing PO supplier_name → supplier_id (FK)
    sup_by_name = {d["name"]: d["id"] for d in docs}
    for name, sid in sup_by_name.items():
        await db.purchase_orders.update_many({"supplier_name": name}, {"$set": {"supplier_id": sid}})
    print(f"✅ Suppliers seeded ({len(docs)}) + PO supplier_id linked")


async def seed_supplier_price_lists():
    """Depth #3 — daftar harga beli (price-list) per (supplier, product).

    Dipakai untuk auto-isi harga PO/PR. Harga = SNAPSHOT supplier (≈ harga_pokok),
    unit = base_unit produk (UOM engine). Beberapa entri pakai MOQ untuk demo tier.
    """
    suppliers = {s["name"]: s for s in await db.suppliers.find({}, {"_id": 0}).to_list(500)}
    products = await db.products.find({}, {"_id": 0}).to_list(500)
    # Map supplier_name produk → entri price-list (1 entri default + 1 tier MOQ tertentu).
    docs = []
    for p in products:
        sup = suppliers.get(p.get("supplier", ""))
        if not sup:
            continue
        base_unit = p.get("base_unit", "meter")
        base_price = float(p.get("harga_pokok", 0) or p.get("price", 0) or 0)
        if base_price <= 0:
            continue
        # Entri standar (tanpa MOQ)
        docs.append({
            "id": new_id("spl"), "supplier_id": sup["id"], "supplier_name": sup["name"],
            "product_id": p["id"], "sku": p.get("sku", ""), "product_name": p.get("name", ""),
            "price": round(base_price, 2), "unit": base_unit, "min_qty": 0.0,
            "lead_time_days": 0, "valid_from": "", "valid_until": "", "currency": "IDR",
            "entity_id": sup.get("entity_id", "ent_ksc"), "notes": "Harga standar (seed)",
            "status": "active", "created_by": "seed",
            "created_at": ago(days=90), "updated_at": ago(days=90),
        })
        # Entri tier diskon volume (MOQ 200) — 5% lebih murah
        docs.append({
            "id": new_id("spl"), "supplier_id": sup["id"], "supplier_name": sup["name"],
            "product_id": p["id"], "sku": p.get("sku", ""), "product_name": p.get("name", ""),
            "price": round(base_price * 0.95, 2), "unit": base_unit, "min_qty": 200.0,
            "lead_time_days": 0, "valid_from": "", "valid_until": "", "currency": "IDR",
            "entity_id": sup.get("entity_id", "ent_ksc"), "notes": "Tier volume ≥200 (seed)",
            "status": "active", "created_by": "seed",
            "created_at": ago(days=90), "updated_at": ago(days=90),
        })
    if docs:
        await db.supplier_price_lists.insert_many(docs)
    print(f"✅ Supplier price-lists seeded ({len(docs)})")


async def seed_cash_transactions():
    """Fase 3 — contoh transaksi kas kecil (per entitas) + kas besar (gabungan)."""
    examples = [
        {"cash_type": "kas_besar", "direction": "in",  "amount": 100000000, "category": "modal",
         "description": "Setoran modal awal kas besar grup", "entity_id": "all",      "days": 60},
        {"cash_type": "kas_kecil", "direction": "in",  "amount": 10000000,  "category": "transfer",
         "description": "Top-up kas kecil PT Kain Suka Cita", "entity_id": "ent_ksc",  "days": 45},
        {"cash_type": "kas_kecil", "direction": "out", "amount": 1500000,   "category": "operasional",
         "description": "Biaya operasional gudang Bandung",   "entity_id": "ent_ksc",  "days": 30},
        {"cash_type": "kas_kecil", "direction": "out", "amount": 750000,    "category": "pembelian",
         "description": "Pembelian bahan printing",           "entity_id": "ent_ksc",  "days": 20},
        {"cash_type": "kas_kecil", "direction": "in",  "amount": 5000000,   "category": "transfer",
         "description": "Top-up kas kecil CV Kanda Suka",     "entity_id": "ent_kanda","days": 15},
        {"cash_type": "kas_kecil", "direction": "out", "amount": 1200000,   "category": "operasional",
         "description": "Biaya kirim sample ke customer",     "entity_id": "ent_kanda","days": 7},
    ]
    docs = []
    for i, e in enumerate(examples, start=1):
        docs.append({
            "id": new_id("cash"), "number": f"CASH-{i:05d}",
            "cash_type": e["cash_type"], "direction": e["direction"], "amount": float(e["amount"]),
            "category": e["category"], "description": e["description"], "entity_id": e["entity_id"],
            "ref_type": "manual", "ref_id": "", "txn_date": ago(days=e["days"]),
            "status": "posted", "created_by": "seed",
            "created_at": ago(days=e["days"]), "updated_at": ago(days=e["days"]),
        })
    await db.cash_transactions.insert_many(docs)
    print(f"✅ Cash transactions seeded ({len(docs)})")


async def seed_bank_accounts():
    """EPIC7-B — akun kas/bank + tautkan transaksi kas (account_id) + rekonsiliasi."""
    accounts = [
        {"id": "bank_bca_ksc", "name": "BCA Operasional KSC", "account_type": "bank",
         "bank_name": "BCA", "account_number": "0123456789", "entity_id": "ent_ksc",
         "opening_balance": 50000000.0},
        {"id": "bank_kas_ksc", "name": "Kas Kecil KSC", "account_type": "cash",
         "bank_name": "", "account_number": "", "entity_id": "ent_ksc", "opening_balance": 2000000.0},
        {"id": "bank_kas_kanda", "name": "Kas Kecil Kanda", "account_type": "cash",
         "bank_name": "", "account_number": "", "entity_id": "ent_kanda", "opening_balance": 1000000.0},
        {"id": "bank_kas_besar", "name": "Kas Besar Grup", "account_type": "cash",
         "bank_name": "", "account_number": "", "entity_id": "all", "opening_balance": 0.0},
    ]
    docs = []
    for a in accounts:
        docs.append({**a, "currency": "IDR", "note": "", "is_active": True,
                     "created_at": ago(days=90), "updated_at": ago(days=90)})
    await db.bank_accounts.insert_many(docs)

    # Tautkan transaksi kas yang ada ke akun (by cash_type + entity)
    def _acc_for(t):
        if t.get("cash_type") == "kas_besar":
            return "bank_kas_besar"
        return "bank_kas_ksc" if t.get("entity_id") == "ent_ksc" else "bank_kas_kanda"

    cash_txns = await db.cash_transactions.find({}, {"_id": 0, "id": 1, "cash_type": 1, "entity_id": 1, "direction": 1}).to_list(1000)
    for idx, t in enumerate(cash_txns):
        # ~setengah ditandai sudah terekonsiliasi (yang 'in' & indeks genap)
        reconciled = (t.get("direction") == "in") or (idx % 2 == 0)
        await db.cash_transactions.update_one(
            {"id": t["id"]},
            {"$set": {"account_id": _acc_for(t), "reconciled": bool(reconciled),
                      "reconciled_at": ago(days=5) if reconciled else ""}},
        )
    print(f"✅ Bank accounts seeded ({len(docs)}) + {len(cash_txns)} cash txns ditautkan")


async def seed_purchase_returns():
    """Depth #1 — contoh retur beli (pending_approval, belum sesuaikan stok)."""
    returns = [
        {"id": new_id("pret"), "number": "PRET-00001",
         "supplier_name": "NTT Weaving Co", "supplier_id": "",
         "po_id": "po_002", "po_number": "PO-00002", "warehouse_id": "wh_surabaya",
         "warehouse_name": "Gudang Surabaya Rungkut", "entity_id": "ent_ksc",
         "items": [{"product_id": "prod_tenun_ikat", "sku": "TNI-GRGD-001",
                    "product_name": "Tenun Ikat Garuda Premium", "quantity": 12.0, "unit": "meter",
                    "price": 200000, "subtotal": 2400000, "reason": "cacat", "condition": "damaged"}],
         "total_amount": 2400000.0, "reason": "Sebagian gulungan cacat tenun (belang warna)",
         "notes": "Foto sudah dikirim ke supplier via WA",
         "status": "pending_approval", "debit_note_number": "", "stock_adjusted": False,
         "created_by": "Eko Prasetyo", "approved_by": None, "approved_at": None,
         "rejected_by": None, "rejected_at": None, "reject_reason": None,
         "created_at": ago(days=6), "updated_at": ago(days=6)},
        {"id": new_id("pret"), "number": "PRET-00002",
         "supplier_name": "Cirebon Craft", "supplier_id": "",
         "po_id": "po_001", "po_number": "PO-00001", "warehouse_id": "wh_jakarta",
         "warehouse_name": "Gudang Jakarta Utara", "entity_id": "ent_ksc",
         "items": [{"product_id": "prod_batik_mega", "sku": "BTK-MEGA-001",
                    "product_name": "Batik Mega Mendung Premium", "quantity": 5.0, "unit": "meter",
                    "price": 165000, "subtotal": 825000, "reason": "salah_kirim", "condition": "ok"}],
         "total_amount": 825000.0, "reason": "Motif tidak sesuai PO",
         "notes": "", "status": "draft", "debit_note_number": "", "stock_adjusted": False,
         "created_by": "Admin", "approved_by": None, "approved_at": None,
         "rejected_by": None, "rejected_at": None, "reject_reason": None,
         "created_at": ago(days=2), "updated_at": ago(days=2)},
    ]
    # link supplier_id by name
    sup_map = {s["name"]: s["id"] for s in await db.suppliers.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
    for r in returns:
        r["supplier_id"] = sup_map.get(r["supplier_name"], "")
    await db.purchase_returns.insert_many(returns)
    print(f"✅ Purchase returns seeded ({len(returns)})")


async def seed_po_payments():
    """Backfill field keuangan default untuk PO lama.

    P0-B (SSOT AP): pembayaran tidak lagi dicatat di level PO. Hutang & pembayaran
    supplier dikelola via Vendor Bill (menu "Tagihan Supplier"). Maka demo
    pembayaran PO-level lama DIHAPUS; PO-00002 tampil sebagai PO selesai yang
    siap ditagih lewat Vendor Bill.
    """
    await db.purchase_orders.update_many(
        {"amount_paid": {"$exists": False}},
        {"$set": {"amount_paid": 0.0, "returned_amount": 0.0, "payment_status": "unpaid", "payments": []}})
    print("✅ PO financial fields backfilled (pembayaran via Vendor Bill / SSOT)")


async def seed_requisitions():
    """Depth #2a — contoh Purchase Requisition (PR) hulu procurement."""
    sup_map = {s["name"]: s for s in await db.suppliers.find({}, {"_id": 0}).to_list(500)}
    wh = (await db.warehouses.find_one({"id": "wh_jakarta"}, {"_id": 0})
          or await db.warehouses.find_one({}, {"_id": 0}))
    prods = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(50)}

    def line(pid, qty):
        p = prods.get(pid, {})
        price = float(p.get("harga_pokok", 0) or p.get("price", 0) or 0)
        return {"product_id": pid, "sku": p.get("sku", ""), "product_name": p.get("name", ""),
                "description": p.get("name", ""), "quantity": float(qty),
                "unit": p.get("base_unit", "meter"), "est_price": price,
                "subtotal": round(price * qty, 2), "note": ""}

    def mkdoc(num, items, status, source, supplier_name, appr, created_by, days):
        total = round(sum(i["subtotal"] for i in items), 2)
        sup = sup_map.get(supplier_name, {})
        return {
            "id": new_id("pr"), "number": num, "entity_id": "ent_ksc",
            "warehouse_id": wh["id"], "warehouse_name": wh["name"],
            "items": items, "total_est_amount": total,
            "source": source, "source_ref_id": "",
            "preferred_supplier_id": sup.get("id", ""), "preferred_supplier_name": sup.get("name", supplier_name),
            "reason": "Restock kebutuhan produksi & penjualan", "needed_by_date": "",
            "notes": "", "status": status,
            "approval_required": appr,
            "required_approval_role": "manager" if appr else None,
            "approval_status": "approved" if status == "approved" else ("pending" if status == "pending_approval" else "not_submitted"),
            "po_id": "", "po_number": "",
            "created_by": created_by,
            "approved_by": "Rina Manajer" if status == "approved" else None,
            "approved_at": ago(days=days) if status == "approved" else None,
            "rejected_by": None, "rejected_at": None, "reject_reason": None,
            "created_at": ago(days=days), "updated_at": ago(days=days),
        }

    prs = [
        mkdoc("PR-00001", [line("prod_songket_palembang", 600), line("prod_ulos_batak", 500)],
              "approved", "reorder", "Palembang Silk House", False, "Eko Prasetyo", 5),
        mkdoc("PR-00002", [line("prod_batik_mega", 800)],
              "pending_approval", "manual", "Cirebon Craft", True, "Eko Prasetyo", 2),
        mkdoc("PR-00003", [line("prod_endek_bali", 400)],
              "draft", "manual", "Bali Weave Studio", False, "Admin", 1),
    ]
    # PR-00004 — CONVERTED → PO-00009 (rantai PR→PO untuk EPIC6 Document Relations).
    # Profil item/supplier sengaja cocok dengan po_009 (Cirebon Craft, Batik Mega 800m).
    pr_converted = mkdoc("PR-00004", [line("prod_batik_mega", 800)],
                         "approved", "reorder", "Cirebon Craft", True, "Eko Prasetyo", 6)
    pr_converted.update({
        "status": "converted", "approval_status": "approved",
        "po_id": "po_009", "po_number": "PO-00009",
        "converted_by": "Admin", "converted_at": ago(days=4),
    })
    prs.append(pr_converted)
    await db.purchase_requisitions.insert_many(prs)
    print(f"✅ Purchase requisitions seeded ({len(prs)})")


async def seed_qc_quarantine_examples():
    """Depth #3a — contoh task inbound `qc_pending` + roll `quarantine` (demo inspeksi QC).
    Dipanggil SETELAH generate_rolls_from_balances agar rebuild_balance konsisten."""
    from services.roll_service import rebuild_balance
    # Pilih PO dengan item sebagai sumber demo (supplier ter-link untuk skenario retur)
    po = await db.purchase_orders.find_one(
        {"items.0": {"$exists": True}}, {"_id": 0}, sort=[("created_at", 1)])
    if not po or not po.get("items"):
        print("⚠️  QC demo dilewati (tidak ada PO berisi item).")
        return
    item = po["items"][0]
    pid = item["product_id"]
    wid = po.get("warehouse_id") or "wh_jakarta"
    owner = po.get("entity_id") or "ent_ksc"
    prod = await db.products.find_one({"id": pid}, {"_id": 0}) or {}
    wh = await db.warehouses.find_one({"id": wid}, {"_id": 0}) or {}
    qqty = 75.0
    lot = f"LOT-QC-{po.get('po_number', 'PO')}"
    task_id = new_id("wms")
    roll_seq = await db.inventory_rolls.count_documents({}) + 1
    await db.inventory_rolls.insert_one({
        "id": new_id("roll"), "product_id": pid, "owner_entity_id": owner,
        "ownership_type": "internal", "consignor_ref": None,
        "warehouse_id": wid, "bin_id": None, "lot": lot,
        "batch": lot.replace("LOT", "BATCH"), "roll_no": f"RL-{roll_seq:05d}",
        "length_initial": qqty, "length_remaining": qqty,
        "unit": prod.get("base_unit", "meter"), "grade": "A",
        "status": "quarantine", "qc_task_id": task_id, "tracking_mode": "barcode",
        "earmarked_for": None, "location_type": "warehouse_bin", "reserved_ref": None,
        "unit_cost": None, "acquired": {"via": "inbound", "ref_id": po["id"], "date": now_iso()},
        "rfid_tag_id": None, "is_remnant": False,
        "created_at": now_iso(), "updated_at": now_iso(),
        "created_by": "seed", "created_by_name": "System Seed",
    })
    await db.wms_tasks.insert_one({
        "id": task_id, "flow_type": "inbound", "source_type": "purchase_order",
        "task_subtype": "receiving", "po_id": po["id"], "po_number": po.get("po_number", ""),
        "product_id": pid, "sku": prod.get("sku", ""), "product_name": prod.get("name", ""),
        "warehouse_id": wid, "warehouse_name": wh.get("name", ""),
        "expected_qty": qqty, "received_qty": qqty, "quantity": qqty, "quarantine_qty": qqty,
        "unit": prod.get("base_unit", "meter"), "status": "qc_pending", "qc_status": "pending",
        "supplier_name": po.get("supplier_name", ""), "lot": lot,
        "created_at": now_iso(), "updated_at": now_iso(), "created_by": "seed",
    })
    await rebuild_balance(pid, wid, owner)
    print(f"✅ QC demo: 1 task qc_pending + roll quarantine {qqty}m ({prod.get('name','')})")



async def seed_all(db_instance=None):
    """
    Run the complete seed pipeline. Can be called from an external module
    (e.g. FastAPI endpoint) by passing a Motor DB instance.

    Returns a summary dict with counts of inserted records.
    """
    if db_instance is not None:
        init_with_db(db_instance)
    if db is None:
        raise RuntimeError(
            "Seed pipeline requires a DB instance. "
            "Either call init_with_db(db) first or pass db_instance to seed_all()."
        )

    print("\n🚀 Starting Kain Nusantara Realistic Seed...\n")
    await clear_collections()
    await seed_users()
    await seed_uoms()
    await seed_warehouses()
    await seed_products()
    await seed_customers()
    await seed_crm()
    await seed_inventory_initial()
    await seed_inventory_movements_initial()
    await seed_purchase_orders()
    await seed_sales_orders()
    await backfill_order_snapshots()
    await seed_document_templates()
    await seed_permissions()
    await seed_audit_logs()
    await seed_entities_and_backfill()
    # Fase 0.5 — Roll-as-SSOT: backfill owner + generate rolls + rebuild balances
    await db.inventory_balances.update_many(
        {"owner_entity_id": {"$exists": False}}, {"$set": {"owner_entity_id": "ent_ksc"}}
    )
    await db.inventory_movements.update_many(
        {"owner_entity_id": {"$exists": False}}, {"$set": {"owner_entity_id": "ent_ksc"}}
    )
    from services.roll_service import generate_rolls_from_balances
    roll_result = await generate_rolls_from_balances(created_by="seed")
    print(f"✅ Inventory rolls generated ({roll_result.get('rolls', 0)} rolls · {roll_result.get('segments', 0)} segmen)")
    # Fase 1A — Configuration Foundation defaults
    from services.config_service import seed_config_defaults
    cfg = await seed_config_defaults()
    print(f"✅ Config defaults seeded (settings {cfg.get('settings',0)} · payment_terms {cfg.get('payment_terms',0)} · approval_rules {cfg.get('approval_rules',0)})")
    # Sub-fase 1.7 — Special Price / Approval Harga (contoh)
    await seed_price_approvals()
    # Sub-fase 1.7 — Pegging/Earmark (contoh soft hold roll → customer)
    await seed_pegging_examples()
    # Fase 1B — backfill pricing (diskon+PPN) agar seed konsisten dgn create_order
    await backfill_order_pricing()
    # Sub-fase 1.8 — normalisasi SO terkirim → status baru + shipments (contoh)
    await seed_shipment_examples()
    # Sub-fase 1.9 — Faktur Pajak Jual (contoh)
    await seed_tax_invoice_examples()
    # Sub-fase 1.11 — Returns & Barang Sisa
    await seed_sales_returns_examples()
    # Sub-fase 1.12 — Special Orders
    await seed_special_order_examples()
    # Fase 3 — Procurement: master supplier (+ link PO) + pengelolaan kas
    await seed_purchase_approval_examples()
    await seed_suppliers()
    await seed_supplier_price_lists()
    await seed_cash_transactions()
    await seed_bank_accounts()
    await seed_purchase_returns()
    await seed_po_payments()
    await seed_requisitions()
    # Depth #3a — QC Hold demo (task qc_pending + roll quarantine)
    await seed_qc_quarantine_examples()
    # EPIC2 — master kategori + snapshot kategori SO line (AKHIR: setelah semua mutasi items)
    await finalize_epic2_categories()
    # EPIC3 — costing (harga_pokok + roll cost) + contoh AR receipt (parsial)
    await finalize_epic3_costing_and_ar()
    # EPIC7-C — bagan akun baku + auto-posting jurnal dari SSOT (idempotent)
    from services import gl_service
    await gl_service.seed_default_coa()
    gl_result = await gl_service.backfill_journals()
    print(f"   [EPIC7-C] Journal posted: {gl_result}")
    # F0-A — enrich entitas + pastikan user ber-entitas (idempotent, tahan timing)
    from services.entity_context_service import ensure_entity_defaults, ensure_user_entities
    en = await ensure_entity_defaults()
    un = await ensure_user_entities()
    print(f"   [F0-A] entity enrich: {en} | user entity ensured: {un}")
    # F0-C — backfill entity_id ke SEMUA koleksi SCOPED (PALING AKHIR: setelah CoA & shipment seed).
    #   wms_tasks←PO/SO · shipments←SO · gl_accounts→primary · catch-all→primary. Idempotent.
    #   Menjaga GATE `verify_entity_scoping.py` (DB CHECK) tetap HIJAU di clean-seed.
    from scripts.migrate_entity_scoping import run_full_migration
    f0c_ok = await run_full_migration()
    print(f"   [F0-C] entity scoping backfill: {'✅ LULUS' if f0c_ok else '❌ ADA SISA'}")
    # F2 (UoM SSOT) — backfill roll_count/on_hand_roll_count ke balances (PALING AKHIR: setelah semua mutasi roll/QC).
    from services.roll_service import backfill_roll_counts
    rc = await backfill_roll_counts()
    print(f"   [F2-UoM] roll_count backfilled ke {rc} balance")
    # F4 (Status SO 2-level) — backfill stage+sub_status ke SEMUA sales_orders (additive, idempotent).
    from services.so_status import backfill_so_status
    so_stat = await backfill_so_status(db)
    print(f"   [F4-Status] stage/sub_status backfilled ke {so_stat['updated']}/{so_stat['total']} SO "
          f"(invalid={so_stat['invalid']})")
    print("\n✅ All realistic seed data inserted successfully!")

    # Compute summary counts
    summary = {
        "users": await db.users.count_documents({}),
        "products": await db.products.count_documents({}),
        "customers": await db.customers.count_documents({}),
        "warehouses": await db.warehouses.count_documents({}),
        "purchase_orders": await db.purchase_orders.count_documents({}),
        "sales_orders": await db.sales_orders.count_documents({}),
        "inbound_tasks": await db.wms_tasks.count_documents({"flow_type": "inbound"}),
        "outbound_tasks": await db.wms_tasks.count_documents({"flow_type": "outbound"}),
        "inventory_balances": await db.inventory_balances.count_documents({}),
        "inventory_movements": await db.inventory_movements.count_documents({}),
        "inventory_rolls": await db.inventory_rolls.count_documents({}),
        "audit_logs": await db.audit_logs.count_documents({}),
        "price_approvals": await db.price_approvals.count_documents({}),
        "sales_returns": await db.sales_returns.count_documents({}),
        "special_orders": await db.special_orders.count_documents({}),
        "purchase_requisitions": await db.purchase_requisitions.count_documents({}),
        "bank_accounts": await db.bank_accounts.count_documents({}),
    }
    return summary


async def main():
    """Standalone CLI entry point — creates its own DB connection."""
    mongo_url = os.environ["MONGO_URL"]
    client = AsyncIOMotorClient(mongo_url)
    db_instance = client[os.environ["DB_NAME"]]
    summary = await seed_all(db_instance)
    client.close()
    print("\n📋 Summary:")
    print(f"  - {summary['users']} Users (admin, sales, manager, warehouse×2)")
    print(f"  - {summary['products']} Products (Batik, Tenun, Lurik, Songket, Ulos, Jumputan, Endek)")
    print(f"  - {summary['customers']} Customers")
    print(f"  - {summary['warehouses']} Warehouses (Jakarta, Bandung, Surabaya)")
    print(f"  - {summary['purchase_orders']} Purchase Orders (PO-00001 → PO-00006)")
    print(f"  - {summary['sales_orders']} Sales Orders (SO-0001 → SO-0009)")
    print(f"  - {summary['inbound_tasks']} Inbound tasks · {summary['outbound_tasks']} Outbound tasks")
    print(f"  - {summary['inventory_balances']} inventory balances · {summary['inventory_movements']} movements")
    print(f"  - {summary['inventory_rolls']} inventory rolls (Roll-as-SSOT)")
    print(f"  - {summary['audit_logs']} audit logs")


if __name__ == "__main__":
    asyncio.run(main())
