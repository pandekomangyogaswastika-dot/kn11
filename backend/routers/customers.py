"""Customers router: CRUD + addresses + CRM-lite (KN_17)."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, current_user, audit
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID
from schemas import CustomerAddress, CustomerCreate, GenericPatch, PaymentProfile
from services.customer_service import enrich_customer, scope_query, can_access_customer
from entity_scope import entity_ctx, resolve_list_scope, stamp_entity

router = APIRouter(prefix="/api")


@router.get("/customers")
async def list_customers(request: Request, entity_id: str = None,
                         segment: str = None, credit_status: str = None,
                         assigned_sales_id: str = None, with_credit: bool = True) -> List[Dict[str, Any]]:
    actor = await require_permission(request, "customer", "view")
    ctx = await entity_ctx(request)
    base: Dict[str, Any] = {}
    if segment:
        base["segment"] = segment
    if assigned_sales_id:
        base["assigned_sales_id"] = assigned_sales_id
    base = resolve_list_scope("customers", base, ctx, entity_id)  # entity isolation
    query = scope_query(actor, base)  # row-level: sales -> own customers
    rows = await db.customers.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    if with_credit:
        out = []
        for c in rows:
            ec = await enrich_customer(c, with_credit=True)
            if credit_status and ec.get("credit", {}).get("status") != credit_status:
                continue
            out.append(ec)
        return out
    return [safe_doc(c) for c in rows]


@router.post("/customers")
async def create_customer(payload: CustomerCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "customer", "create")
    count = await db.customers.count_documents({}) + 1
    # assigned_sales: eksplisit > (sales pembuat jadi pemilik, S40) > kosong
    assigned_id = payload.assigned_sales_id
    if not assigned_id and actor.get("role") == "sales":
        assigned_id = actor["id"]
    assigned_name = ""
    if assigned_id:
        su = await db.users.find_one({"id": assigned_id, "role": "sales"}, {"_id": 0, "name": 1})
        assigned_name = (su or {}).get("name", "")
    profile = (payload.payment_profile or PaymentProfile()).model_dump()
    contacts = [c.model_dump() for c in payload.contacts]
    if not contacts and payload.pic_name:
        contacts = [{"name": payload.pic_name, "role": "PIC", "phone": payload.phone,
                     "email": payload.email, "is_primary": True}]
    customer = {
        "id": new_id("cust"),
        "code": f"CUST-{count:04d}",
        "name": payload.name,
        "pic_name": payload.pic_name,
        "phone": payload.phone,
        "email": payload.email,
        "type": payload.type,
        "city": payload.city,
        "npwp": payload.npwp,
        "credit_limit": payload.credit_limit,
        "sales_pic": assigned_name or payload.sales_pic,
        "entity_id": payload.entity_id or DEFAULT_ENTITY_ID,
        "enforce_single_dye_lot": bool(payload.enforce_single_dye_lot),  # P0-4
        "lot_policy": payload.lot_policy or "",                          # P0-4 / KN_15
        "allocation_policy": {},
        # --- CRM-lite (KN_17) ---
        "assigned_sales_id": assigned_id or "",
        "assigned_sales_name": assigned_name,
        "segment": payload.segment or payload.type or "Retail",
        "tags": payload.tags or [],
        "contacts": contacts,
        "payment_profile": profile,
        "customer_group_id": "",
        "status": "active",
        "created_by": actor["name"],
        "created_at": now_iso(),
        "addresses": [
            CustomerAddress(
                recipient_name=payload.pic_name, phone=payload.phone,
                city=payload.city, address=payload.address, is_primary=True
            ).model_dump()
        ],
    }
    await db.customers.insert_one(customer)
    await audit(actor["name"], "customer_created", "customer", customer["id"], customer)
    return await enrich_customer(customer, with_credit=True)


@router.patch("/customers/{customer_id}")
async def update_customer(customer_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "customer", "update")
    existing = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0}))
    if not existing:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    if not await can_access_customer(actor, existing):
        raise HTTPException(status_code=403, detail="Customer ini bukan milik Anda")
    allowed = ["name", "pic_name", "phone", "email", "type", "city", "status", "addresses",
               "npwp", "credit_limit", "sales_pic", "entity_id",
               "enforce_single_dye_lot", "lot_policy", "allocation_policy",
               # CRM-lite
               "segment", "tags", "contacts", "payment_profile", "customer_group_id"]
    data = {k: v for k, v in payload.data.items() if k in allowed}
    data["updated_at"] = now_iso()
    customer = await db.customers.find_one_and_update(
        {"id": customer_id}, {"$set": data},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    await audit(actor["name"], "customer_updated", "customer", customer_id, customer)
    return await enrich_customer(customer, with_credit=True)


@router.post("/customers/{customer_id}/addresses")
async def add_customer_address(customer_id: str, payload: CustomerAddress, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "customer", "update")
    address = payload.model_dump()
    customer = await db.customers.find_one_and_update(
        {"id": customer_id},
        {"$push": {"addresses": address}, "$set": {"updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    await audit(actor["name"], "customer_address_added", "customer", customer_id, address)
    return safe_doc(customer)
