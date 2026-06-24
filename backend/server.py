"""Kain Nusantara API — modular FastAPI application."""
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from db import client
import bootstrap

# Import all routers
from routers import (
    auth, users, dashboard, products, customers, warehouses, uoms,
    inventory, sales_orders, invoices, wms, documents, admin,
    reporting, audit, cycle_count, onboarding, label_printer, transfers,
    purchase_orders, inbound_receiving, outbound_picking,
    entities, notifications, settings, price_approvals, pegging, tax_invoices,
    sales_returns, special_orders, approval_rules, approval_requests,
    suppliers, cash, purchase_returns, purchase_requisitions, vendor_bills,
    landed_cost, input_tax, rfq, qc_inspection, crm, home, categories,
    costing, ar_receipts, incentive_rates, ar_aging, bank, gl, pricelist, product_templates,
    stock_buckets, pos
)

# ─── App factory ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bootstrap.run_bootstrap()
    # Sub-fase 1.7 — init object storage (best-effort; tak menggagalkan startup)
    try:
        from services.storage_service import init_storage
        await init_storage()
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("server").warning("[storage] init dilewati: %s", exc)
    yield
    client.close()


app = FastAPI(title="Kain Nusantara API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
for module in [
    auth, users, dashboard, products, customers, warehouses, uoms,
    inventory, sales_orders, invoices, wms, documents, admin,
    reporting, audit, cycle_count, onboarding, label_printer, transfers,
    purchase_orders, inbound_receiving, outbound_picking,
    entities, notifications, settings, price_approvals, pegging, tax_invoices,
    sales_returns, special_orders, approval_rules, approval_requests,
    suppliers, cash, purchase_returns, purchase_requisitions, vendor_bills,
    landed_cost, input_tax, rfq, qc_inspection, crm, home, categories,
    costing, ar_receipts, incentive_rates, ar_aging, bank, gl, pricelist, product_templates,
    stock_buckets, pos
]:
    app.include_router(module.router)


@app.get("/api/")
async def root():
    return {"message": "Kain Nusantara API aktif"}
