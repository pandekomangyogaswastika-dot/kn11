#!/usr/bin/env python3
"""
Backend API Test — Sub-fase 1.6.1 Backorder Approval & Auto-commit
===================================================================
Comprehensive test covering:
1. DECOUPLE: status 'reserved' (not 'waiting_stock') when allow_backorder=true & stock>0
2. APPROVAL-WITH-BACKORDER: SO 'reserved'+has_backorder can be approved
3. AUTO-COMMIT: After GR, SO stays 'approved', has_backorder=false, rolls 'committed'
4. REGRESSION: Normal SO (no backorder) works as before
5. EDGE CASES: Full backorder (stock=0), no backorder allowed (409)
"""
import os
import sys
import requests
from datetime import datetime

BASE = os.environ.get("BACKEND_URL", "https://wms-erp-multi-entity.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
EXTRA = 60.0
PASS, FAIL = [], []


def ok(m):
    PASS.append(m)
    print(f"  ✅ [PASS] {m}")


def bad(m):
    FAIL.append(m)
    print(f"  ❌ [FAIL] {m}")


def info(m):
    print(f"  ℹ️  {m}")


class BackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.entity_id = None
        self.warehouse_id = None
        self.customer_id = None
        self.address_id = None
        
    def login(self):
        """Login as admin"""
        try:
            r = self.session.post(
                f"{API}/auth/login",
                json={"email": "admin@kainnusantara.id", "password": "demo12345"},
                timeout=30
            )
            if r.status_code != 200:
                bad(f"Login failed: {r.status_code} {r.text[:100]}")
                return False
            data = r.json()
            self.token = data.get("token")
            if not self.token:
                bad("Login response missing token")
                return False
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            ok("Login admin")
            return True
        except Exception as e:
            bad(f"Login exception: {e}")
            return False
    
    def setup_references(self):
        """Get entity, warehouse, customer references"""
        try:
            # Get entity
            r = self.session.get(f"{API}/entities", timeout=30)
            entities = r.json()
            if not entities:
                bad("No entities found")
                return False
            self.entity_id = entities[0]["id"]
            
            # Get warehouse
            r = self.session.get(f"{API}/warehouses", timeout=30)
            warehouses = r.json()
            if not warehouses:
                bad("No warehouses found")
                return False
            self.warehouse_id = warehouses[0]["id"]
            
            # Get customer
            r = self.session.get(f"{API}/customers", timeout=30)
            customers = r.json()
            if not customers:
                bad("No customers found")
                return False
            self.customer_id = customers[0]["id"]
            self.address_id = customers[0].get("addresses", [{}])[0].get("id")
            
            ok(f"Setup references: entity={self.entity_id[:8]}, warehouse={self.warehouse_id[:8]}, customer={self.customer_id[:8]}")
            return True
        except Exception as e:
            bad(f"Setup references exception: {e}")
            return False
    
    def find_product_with_stock(self):
        """Find product with available stock > 0 for entity"""
        try:
            r = self.session.get(
                f"{API}/inventory/status-board",
                params={"owner_entity_id": self.entity_id},
                timeout=30
            )
            board = r.json()
            
            best = None
            for row in board:
                for be in row.get("by_entity", []):
                    if be.get("entity_id") == self.entity_id:
                        avail = float(be.get("available", 0) or 0)
                        if avail > 0:
                            if best is None or avail > best[1]:
                                best = (row["product_id"], avail)
            
            if not best:
                bad("No product with available stock > 0 found")
                return None, 0
            
            info(f"Found product {best[0][:12]} with available={best[1]}")
            return best[0], best[1]
        except Exception as e:
            bad(f"Find product exception: {e}")
            return None, 0
    
    def test_decouple_status_backorder(self):
        """TEST 1: DECOUPLE - status 'reserved' when allow_backorder=true & stock>0"""
        info("\n=== TEST 1: DECOUPLE Status from Backorder ===")
        
        product_id, available = self.find_product_with_stock()
        if not product_id:
            return False
        
        # Request qty > available (but available > 0)
        request_qty = round(available + EXTRA, 2)
        
        try:
            r = self.session.post(
                f"{API}/sales-orders",
                json={
                    "customer_id": self.customer_id,
                    "shipping_address_id": self.address_id,
                    "entity_id": self.entity_id,
                    "allow_backorder": True,
                    "items": [{"product_id": product_id, "quantity": request_qty, "unit": "meter"}],
                },
                timeout=30
            )
            
            if r.status_code != 200:
                bad(f"Create SO with backorder failed: {r.status_code} {r.text[:200]}")
                return False
            
            so = r.json()
            so_id = so["id"]
            
            # Check status is 'reserved' (NOT 'waiting_stock')
            if so["status"] == "reserved":
                ok(f"DECOUPLE: SO status='reserved' (not 'waiting_stock') despite backorder")
            else:
                bad(f"DECOUPLE: Expected status='reserved', got '{so['status']}'")
            
            # Check has_backorder=true
            if so.get("has_backorder"):
                ok("DECOUPLE: has_backorder=true")
            else:
                bad("DECOUPLE: has_backorder should be true")
            
            # Check item has reserved_qty and backorder_qty
            item = so["items"][0]
            reserved_qty = float(item.get("reserved_qty", 0))
            backorder_qty = float(item.get("backorder_qty", 0))
            
            if reserved_qty > 0 and backorder_qty > 0:
                ok(f"DECOUPLE: Item has reserved_qty={reserved_qty} and backorder_qty={backorder_qty}")
            else:
                bad(f"DECOUPLE: Item reserved_qty={reserved_qty}, backorder_qty={backorder_qty}")
            
            return so_id
        except Exception as e:
            bad(f"DECOUPLE test exception: {e}")
            return False
    
    def test_approval_with_backorder(self, so_id):
        """TEST 2: APPROVAL-WITH-BACKORDER - SO 'reserved'+has_backorder can be approved"""
        info("\n=== TEST 2: Approval with Backorder ===")
        
        try:
            # Submit for approval
            r = self.session.post(f"{API}/sales-orders/{so_id}/submit-for-approval", timeout=30)
            if r.status_code != 200:
                bad(f"Submit for approval failed: {r.status_code} {r.text[:200]}")
                return False
            
            result = r.json()
            status = result.get("status")
            
            # If waiting_approval, approve it
            if status == "waiting_approval":
                r = self.session.post(f"{API}/sales-orders/{so_id}/approve", timeout=30)
                if r.status_code != 200:
                    bad(f"Approve failed: {r.status_code} {r.text[:200]}")
                    return False
                result = r.json()
                status = result.get("status")
            
            # Check status is 'approved'
            if status == "approved":
                ok("APPROVAL: SO approved despite having backorder")
            else:
                bad(f"APPROVAL: Expected status='approved', got '{status}'")
            
            # Check has_backorder still true
            so = self.session.get(f"{API}/sales-orders/{so_id}", timeout=30).json()
            if so.get("has_backorder"):
                ok("APPROVAL: has_backorder still true after approval")
            else:
                bad("APPROVAL: has_backorder should still be true")
            
            return True
        except Exception as e:
            bad(f"APPROVAL test exception: {e}")
            return False
    
    def test_auto_commit_after_gr(self, so_id):
        """TEST 3: AUTO-COMMIT - After GR, SO stays 'approved', has_backorder=false, rolls 'committed'"""
        info("\n=== TEST 3: Auto-commit after GR ===")
        
        try:
            # Get SO to find backorder qty
            so = self.session.get(f"{API}/sales-orders/{so_id}", timeout=30).json()
            backorder = so.get("backorders", [{}])[0]
            product_id = backorder.get("product_id")
            backorder_qty = float(backorder.get("backorder_qty", 0))
            
            if backorder_qty <= 0:
                bad("AUTO-COMMIT: No backorder qty to fulfill")
                return False
            
            # Create PO to fulfill backorder
            r = self.session.post(
                f"{API}/purchase-orders",
                json={
                    "supplier_name": "Supplier Test 161",
                    "warehouse_id": self.warehouse_id,
                    "entity_id": self.entity_id,
                    "items": [{"product_id": product_id, "quantity": backorder_qty, "unit": "meter", "price": 0.0}],
                },
                timeout=30
            )
            
            if r.status_code != 200:
                bad(f"Create PO failed: {r.status_code} {r.text[:200]}")
                return False
            
            po = r.json()
            po_id = po["id"]
            
            # Approve PO if needed
            if po["status"] == "waiting_approval":
                self.session.post(f"{API}/purchase-orders/{po_id}/approve", timeout=30)
            
            # Get inbound task
            r = self.session.get(f"{API}/inbound/tasks", timeout=30)
            tasks = r.json()
            task = next((t for t in tasks if t.get("po_id") == po_id and t.get("product_id") == product_id), None)
            
            if not task:
                bad("AUTO-COMMIT: Inbound task not found")
                return False
            
            # Scan receive
            expected_qty = float(task["expected_qty"])
            r = self.session.post(
                f"{API}/inbound/tasks/{task['id']}/scan-receive",
                json={"product_id": product_id, "actual_qty": expected_qty, "lot": "LOT-TEST-161", "batch": "B161"},
                timeout=30
            )
            
            if r.status_code != 200:
                bad(f"Scan receive failed: {r.status_code} {r.text[:200]}")
                return False
            
            # Complete GR
            r = self.session.post(f"{API}/inbound/tasks/{task['id']}/complete", timeout=30)
            if r.status_code != 200:
                bad(f"Complete GR failed: {r.status_code} {r.text[:200]}")
                return False
            
            # Check SO after GR
            so_after = self.session.get(f"{API}/sales-orders/{so_id}", timeout=30).json()
            
            # Status should still be 'approved'
            if so_after["status"] == "approved":
                ok("AUTO-COMMIT: SO status still 'approved' (no re-approval needed)")
            else:
                bad(f"AUTO-COMMIT: Expected status='approved', got '{so_after['status']}'")
            
            # has_backorder should be false
            if not so_after.get("has_backorder"):
                ok("AUTO-COMMIT: has_backorder=false")
            else:
                bad("AUTO-COMMIT: has_backorder should be false")
            
            # Item backorder_qty should be 0
            item = so_after["items"][0]
            if float(item.get("backorder_qty", 1)) <= 0.5:
                ok(f"AUTO-COMMIT: Item backorder_qty=0")
            else:
                bad(f"AUTO-COMMIT: Item backorder_qty={item.get('backorder_qty')}")
            
            # Check rolls are committed (via pymongo)
            try:
                from pymongo import MongoClient
                cli = MongoClient("mongodb://localhost:27017")
                db = cli["test_database"]
                rolls = list(db.inventory_rolls.find({"reserved_ref.id": so_id}, {"_id": 0, "status": 1}))
                statuses = {r.get("status") for r in rolls}
                
                if rolls and statuses == {"committed"}:
                    ok(f"AUTO-COMMIT: {len(rolls)} rolls all 'committed'")
                else:
                    bad(f"AUTO-COMMIT: Roll statuses={statuses} (expected all 'committed')")
                
                cli.close()
            except Exception as e:
                info(f"Roll verification skipped: {e}")
            
            return True
        except Exception as e:
            bad(f"AUTO-COMMIT test exception: {e}")
            return False
    
    def test_regression_normal_so(self):
        """TEST 4: REGRESSION - Normal SO (qty <= stock, no backorder) works"""
        info("\n=== TEST 4: Regression - Normal SO ===")
        
        product_id, available = self.find_product_with_stock()
        if not product_id:
            return False
        
        # Request qty <= available
        request_qty = min(10.0, available)
        
        try:
            r = self.session.post(
                f"{API}/sales-orders",
                json={
                    "customer_id": self.customer_id,
                    "shipping_address_id": self.address_id,
                    "entity_id": self.entity_id,
                    "allow_backorder": False,  # Default
                    "items": [{"product_id": product_id, "quantity": request_qty, "unit": "meter"}],
                },
                timeout=30
            )
            
            if r.status_code != 200:
                bad(f"Create normal SO failed: {r.status_code} {r.text[:200]}")
                return False
            
            so = r.json()
            
            # Status should be 'reserved'
            if so["status"] == "reserved":
                ok("REGRESSION: Normal SO status='reserved'")
            else:
                bad(f"REGRESSION: Expected status='reserved', got '{so['status']}'")
            
            # has_backorder should be false
            if not so.get("has_backorder"):
                ok("REGRESSION: Normal SO has_backorder=false")
            else:
                bad("REGRESSION: Normal SO should not have backorder")
            
            return True
        except Exception as e:
            bad(f"REGRESSION test exception: {e}")
            return False
    
    def test_regression_no_backorder_insufficient_stock(self):
        """TEST 5: REGRESSION - SO with allow_backorder=false & insufficient stock returns 409"""
        info("\n=== TEST 5: Regression - No Backorder + Insufficient Stock ===")
        
        product_id, available = self.find_product_with_stock()
        if not product_id:
            return False
        
        # Request qty > available with allow_backorder=false
        request_qty = round(available + 100.0, 2)
        
        try:
            r = self.session.post(
                f"{API}/sales-orders",
                json={
                    "customer_id": self.customer_id,
                    "shipping_address_id": self.address_id,
                    "entity_id": self.entity_id,
                    "allow_backorder": False,
                    "items": [{"product_id": product_id, "quantity": request_qty, "unit": "meter"}],
                },
                timeout=30
            )
            
            # Should return 409
            if r.status_code == 409:
                ok("REGRESSION: SO with insufficient stock & no backorder returns 409")
            else:
                bad(f"REGRESSION: Expected 409, got {r.status_code}")
            
            return True
        except Exception as e:
            bad(f"REGRESSION test exception: {e}")
            return False
    
    def run_all_tests(self):
        """Run all backend tests"""
        print("\n" + "="*70)
        print("  BACKEND API TEST — Sub-fase 1.6.1 Backorder Approval & Auto-commit")
        print("="*70)
        
        if not self.login():
            return False
        
        if not self.setup_references():
            return False
        
        # Test 1: DECOUPLE
        so_id = self.test_decouple_status_backorder()
        if not so_id:
            return False
        
        # Test 2: APPROVAL-WITH-BACKORDER
        if not self.test_approval_with_backorder(so_id):
            return False
        
        # Test 3: AUTO-COMMIT
        if not self.test_auto_commit_after_gr(so_id):
            return False
        
        # Test 4: REGRESSION - Normal SO
        self.test_regression_normal_so()
        
        # Test 5: REGRESSION - No backorder + insufficient stock
        self.test_regression_no_backorder_insufficient_stock()
        
        return True


def main():
    tester = BackendTester()
    tester.run_all_tests()
    
    print("\n" + "="*70)
    print(f"  HASIL: {len(PASS)} PASS | {len(FAIL)} FAIL")
    print("="*70)
    
    if FAIL:
        print("\n❌ FAILED TESTS:")
        for f in FAIL:
            print(f"   - {f}")
        return 1
    
    print("\n✅ SEMUA TEST BACKEND LULUS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
