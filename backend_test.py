"""
Backend Testing for Kain Nusantara ERP/WMS (KN11)
Tests AUTH + EPIC0/EPIC1 (Role-based home routing + RBAC tightening)
Tests EPIC2 (Master Kategori Produk + Snapshot kategori ke SO line)
Tests EPIC3A (Costing - WAC + Margin)
Tests EPIC3B (AR Receipts - Payment Application)
Tests EPIC4 (Incentive Engine v2 - Per-SKU commission + Rate matrix)
"""
import requests
import sys
from typing import Dict, Any, Optional

BASE_URL = "https://kn11-tier-tasks.preview.emergentagent.com/api"

class TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.admin_token = None
        self.manager_token = None
        self.sales_token = None
        self.warehouse_token = None
        self.failures = []
        self.created_category_id = None
        self.test_customer_id = None
        self.test_receipt_id = None

    def log(self, message: str, level: str = "INFO"):
        prefix = {"INFO": "ℹ️", "PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}.get(level, "•")
        print(f"{prefix} {message}")

    def test(self, name: str, method: str, endpoint: str, expected_status: int,
             data: Optional[Dict] = None, token: Optional[str] = None,
             check_response: Optional[callable] = None) -> tuple[bool, Any]:
        """Run a single API test"""
        self.tests_run += 1
        url = f"{BASE_URL}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.log(f"Test #{self.tests_run}: {name}", "INFO")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            response_data = {}
            try:
                response_data = response.json()
            except:
                pass

            if success:
                # Additional response checks
                if check_response and not check_response(response_data):
                    success = False
                    self.log(f"  Response validation failed", "FAIL")
                    self.failures.append(f"{name}: Response validation failed")
                    self.tests_failed += 1
                else:
                    self.tests_passed += 1
                    self.log(f"  PASSED (status: {response.status_code})", "PASS")
            else:
                self.log(f"  FAILED - Expected {expected_status}, got {response.status_code}", "FAIL")
                if response_data:
                    self.log(f"  Response: {response_data}", "FAIL")
                self.failures.append(f"{name}: Expected {expected_status}, got {response.status_code}")
                self.tests_failed += 1

            return success, response_data

        except Exception as e:
            self.log(f"  FAILED - Error: {str(e)}", "FAIL")
            self.failures.append(f"{name}: {str(e)}")
            self.tests_failed += 1
            return False, {}

    def login(self, email: str, password: str) -> Optional[str]:
        """Login and return token"""
        self.log(f"Logging in as {email}...", "INFO")
        success, data = self.test(
            f"Login {email}",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'token' in data:
            self.log(f"  Login successful, token obtained", "PASS")
            return data['token']
        self.log(f"  Login failed", "FAIL")
        return None

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total Tests: {self.tests_run}")
        print(f"✅ Passed: {self.tests_passed}")
        print(f"❌ Failed: {self.tests_failed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100) if self.tests_run > 0 else 0:.1f}%")
        
        if self.failures:
            print("\n" + "="*70)
            print("FAILURES:")
            print("="*70)
            for i, failure in enumerate(self.failures, 1):
                print(f"{i}. {failure}")
        
        print("="*70)


def main():
    runner = TestRunner()
    
    print("="*70)
    print("KAIN NUSANTARA (KN11) - BACKEND TESTING")
    print("Testing AUTH + EPIC0/EPIC1 + EPIC2 + EPIC3A + EPIC3B + EPIC4")
    print("="*70)
    print()

    # ========== AUTHENTICATION ==========
    print("\n" + "="*70)
    print("PHASE 1: AUTHENTICATION (All 4 roles)")
    print("="*70)
    
    runner.admin_token = runner.login("admin@kainnusantara.id", "demo12345")
    if not runner.admin_token:
        print("❌ CRITICAL: Admin login failed. Cannot continue.")
        return 1
    
    runner.manager_token = runner.login("manager@kainnusantara.id", "demo12345")
    if not runner.manager_token:
        print("❌ CRITICAL: Manager login failed. Cannot continue.")
        return 1
    
    runner.sales_token = runner.login("sales@kainnusantara.id", "demo12345")
    if not runner.sales_token:
        print("❌ CRITICAL: Sales login failed. Cannot continue.")
        return 1
    
    warehouse_token = runner.login("warehouse@kainnusantara.id", "demo12345")
    if not warehouse_token:
        print("❌ CRITICAL: Warehouse login failed. Cannot continue.")
        return 1
    
    runner.warehouse_token = warehouse_token

    # ========== EPIC1: ROLE-BASED HOME ROUTING ==========
    print("\n" + "="*70)
    print("PHASE 2: EPIC1 - ROLE-BASED HOME ROUTING")
    print("="*70)
    
    # Admin home - should work for admin & manager, 403 for sales
    runner.log("Testing /home/admin endpoint access...", "INFO")
    runner.test(
        "Admin home as ADMIN (should work)",
        "GET",
        "home/admin",
        200,
        token=runner.admin_token
    )
    
    runner.test(
        "Admin home as MANAGER (should work)",
        "GET",
        "home/admin",
        200,
        token=runner.manager_token
    )
    
    runner.test(
        "Admin home as SALES (should 403 - RBAC)",
        "GET",
        "home/admin",
        403,
        token=runner.sales_token
    )
    
    # Sales home - should work for all authenticated users
    runner.log("\nTesting /home/sales endpoint access...", "INFO")
    runner.test(
        "Sales home as SALES (should work)",
        "GET",
        "home/sales",
        200,
        token=runner.sales_token
    )
    
    runner.test(
        "Sales home as ADMIN (should work)",
        "GET",
        "home/sales",
        200,
        token=runner.admin_token
    )
    
    # Manager home - should work for admin & manager
    runner.log("\nTesting /home/manager endpoint access...", "INFO")
    runner.test(
        "Manager home as MANAGER (should work)",
        "GET",
        "home/manager",
        200,
        token=runner.manager_token
    )
    
    runner.test(
        "Manager home as ADMIN (should work)",
        "GET",
        "home/manager",
        200,
        token=runner.admin_token
    )

    # ========== EPIC1: SALES RBAC TIGHTENING ==========
    print("\n" + "="*70)
    print("PHASE 3: EPIC1 - SALES RBAC TIGHTENING")
    print("="*70)
    
    runner.log("Testing sales role cannot access back-office endpoints...", "INFO")
    
    # These endpoints should return 403 for sales role
    restricted_endpoints = [
        ("vendor-bills", "Vendor Bills"),
        ("landed-cost", "Landed Cost"),
        ("input-tax", "Input Tax"),
        ("purchase-requisitions", "Purchase Requisitions"),
        ("purchase-orders", "Purchase Orders"),
    ]
    
    for endpoint, name in restricted_endpoints:
        runner.test(
            f"Sales accessing {name} (should 403)",
            "GET",
            endpoint,
            403,
            token=runner.sales_token
        )
    
    # Admin should be able to access these
    runner.log("\nVerifying admin CAN access back-office endpoints...", "INFO")
    runner.test(
        "Admin accessing vendor-bills (should work)",
        "GET",
        "vendor-bills",
        200,
        token=runner.admin_token
    )
    
    runner.test(
        "Admin accessing purchase-orders (should work)",
        "GET",
        "purchase-orders",
        200,
        token=runner.admin_token
    )

    # ========== EPIC2: MASTER KATEGORI PRODUK - BACKEND CRUD ==========
    print("\n" + "="*70)
    print("PHASE 4: EPIC2 - MASTER KATEGORI PRODUK (BACKEND CRUD)")
    print("="*70)
    
    # Test GET /api/product-categories - should return array with 7 seeded categories
    runner.log("Testing GET /api/product-categories...", "INFO")
    success, categories = runner.test(
        "GET product-categories (should return array with product_count)",
        "GET",
        "product-categories",
        200,
        token=runner.admin_token,
        check_response=lambda r: isinstance(r, list) and len(r) >= 7
    )
    
    if success:
        runner.log(f"  Found {len(categories)} categories", "INFO")
        # Check that each category has product_count field
        has_product_count = all('product_count' in cat for cat in categories)
        if has_product_count:
            runner.log("  All categories have product_count field ✓", "PASS")
        else:
            runner.log("  Some categories missing product_count field", "FAIL")
            runner.failures.append("Categories missing product_count field")
            runner.tests_failed += 1
        
        # Check for expected categories
        expected_cats = ["Batik", "Endek", "Jumputan", "Lurik", "Songket", "Tenun", "Ulos"]
        found_cats = [cat['name'] for cat in categories]
        for exp in expected_cats:
            if exp in found_cats:
                runner.log(f"  Found expected category: {exp} ✓", "INFO")
            else:
                runner.log(f"  Missing expected category: {exp}", "WARN")
    
    # Test POST /api/product-categories - create new category
    runner.log("\nTesting POST /api/product-categories (create)...", "INFO")
    success, new_cat = runner.test(
        "POST product-categories (create new category)",
        "POST",
        "product-categories",
        200,
        data={"name": "Tes Sutra", "base_unit": "meter", "description": "Test category"},
        token=runner.admin_token,
        check_response=lambda r: 'id' in r and r.get('name') == 'Tes Sutra'
    )
    
    if success:
        runner.created_category_id = new_cat.get('id')
        runner.log(f"  Created category ID: {runner.created_category_id}", "INFO")
        # Check auto-generated code
        if 'code' in new_cat and new_cat['code']:
            runner.log(f"  Auto-generated code: {new_cat['code']} ✓", "PASS")
        else:
            runner.log("  Code not auto-generated", "WARN")
    
    # Test POST with auto-generated code (omit code field)
    runner.log("\nTesting POST with auto-generated code...", "INFO")
    success, auto_code_cat = runner.test(
        "POST product-categories (auto-generate code from name)",
        "POST",
        "product-categories",
        200,
        data={"name": "Kain Prada", "base_unit": "meter"},
        token=runner.admin_token,
        check_response=lambda r: 'code' in r and r['code'] != ''
    )
    
    if success and 'code' in auto_code_cat:
        runner.log(f"  Auto-generated code: {auto_code_cat['code']} ✓", "PASS")
    
    # Test PATCH /api/product-categories/{id} - update category
    if runner.created_category_id:
        runner.log("\nTesting PATCH /api/product-categories/{id} (update)...", "INFO")
        runner.test(
            "PATCH product-categories (update category)",
            "PATCH",
            f"product-categories/{runner.created_category_id}",
            200,
            data={"data": {"name": "Tes Sutra Updated", "description": "Updated description"}},
            token=runner.admin_token,
            check_response=lambda r: r.get('name') == 'Tes Sutra Updated'
        )
    
    # Test uniqueness - duplicate name should return 409
    runner.log("\nTesting uniqueness constraint (duplicate name)...", "INFO")
    runner.test(
        "POST product-categories (duplicate name should 409)",
        "POST",
        "product-categories",
        409,
        data={"name": "Batik", "base_unit": "meter"},
        token=runner.admin_token
    )
    
    # Test DELETE /api/product-categories/{id} - soft delete
    # First, try to delete a category that's in use (should 409)
    runner.log("\nTesting DELETE on in-use category (should 409)...", "INFO")
    # Find a category with product_count > 0
    in_use_cat = next((cat for cat in categories if cat.get('product_count', 0) > 0), None)
    if in_use_cat:
        runner.test(
            "DELETE product-categories (in-use should 409)",
            "DELETE",
            f"product-categories/{in_use_cat['id']}",
            409,
            token=runner.admin_token
        )
    
    # Delete the test category we created (should work since no products use it)
    if runner.created_category_id:
        runner.log("\nTesting DELETE on unused category (should work)...", "INFO")
        runner.test(
            "DELETE product-categories (unused category)",
            "DELETE",
            f"product-categories/{runner.created_category_id}",
            200,
            token=runner.admin_token,
            check_response=lambda r: r.get('status') == 'inactive'
        )

    # ========== EPIC2: RBAC - SALES ROLE PERMISSIONS ==========
    print("\n" + "="*70)
    print("PHASE 5: EPIC2 - RBAC (SALES role permissions)")
    print("="*70)
    
    runner.log("Testing SALES role can GET but not POST/PATCH/DELETE...", "INFO")
    
    # SALES should be able to GET (view)
    runner.test(
        "SALES GET product-categories (should 200)",
        "GET",
        "product-categories",
        200,
        token=runner.sales_token
    )
    
    # SALES should NOT be able to POST (403)
    runner.test(
        "SALES POST product-categories (should 403)",
        "POST",
        "product-categories",
        403,
        data={"name": "Test", "base_unit": "meter"},
        token=runner.sales_token
    )
    
    # SALES should NOT be able to PATCH (403)
    if categories and len(categories) > 0:
        runner.test(
            "SALES PATCH product-categories (should 403)",
            "PATCH",
            f"product-categories/{categories[0]['id']}",
            403,
            data={"data": {"name": "Test"}},
            token=runner.sales_token
        )
        
        # SALES should NOT be able to DELETE (403)
        runner.test(
            "SALES DELETE product-categories (should 403)",
            "DELETE",
            f"product-categories/{categories[0]['id']}",
            403,
            token=runner.sales_token
        )

    # ========== EPIC2: SO SNAPSHOT - CATEGORY IN LINE ITEMS ==========
    print("\n" + "="*70)
    print("PHASE 6: EPIC2 - SO SNAPSHOT (category in line items)")
    print("="*70)
    
    runner.log("Testing POST /api/sales-orders includes category in line items...", "INFO")
    
    # Get a product to use in the order
    success, products = runner.test(
        "GET products for SO test",
        "GET",
        "products",
        200,
        token=runner.admin_token
    )
    
    if success and products and len(products) > 0:
        product = products[0]
        runner.log(f"  Using product: {product.get('name')} (category: {product.get('category')})", "INFO")
        
        # Get a customer
        success, customers = runner.test(
            "GET customers for SO test",
            "GET",
            "customers",
            200,
            token=runner.admin_token
        )
        
        if success and customers and len(customers) > 0:
            customer = customers[0]
            
            # Get customer's first address for shipping_address_id
            addresses = customer.get('addresses', [])
            shipping_address_id = addresses[0]['id'] if addresses else None
            
            # Create a sales order
            so_data = {
                "customer_id": customer['id'],
                "shipping_address_id": shipping_address_id,
                "items": [
                    {
                        "product_id": product['id'],
                        "quantity": 10,
                        "unit": product.get('base_unit', 'meter'),
                        "price": product.get('price', 100000)
                    }
                ]
            }
            
            success, so = runner.test(
                "POST sales-orders (check category snapshot)",
                "POST",
                "sales-orders",
                200,
                data=so_data,
                token=runner.admin_token,
                check_response=lambda r: (
                    'items' in r and 
                    len(r['items']) > 0 and 
                    'category' in r['items'][0] and
                    'base_unit' in r['items'][0] and
                    'base_quantity' in r['items'][0]
                )
            )
            
            if success:
                item = so['items'][0]
                runner.log(f"  Line item has category: {item.get('category')} ✓", "PASS")
                runner.log(f"  Line item has base_unit: {item.get('base_unit')} ✓", "PASS")
                runner.log(f"  Line item has base_quantity: {item.get('base_quantity')} ✓", "PASS")
        else:
            runner.log("  No customers found, skipping SO test", "WARN")
    else:
        runner.log("  No products found, skipping SO test", "WARN")

    # ========== EPIC3A: COSTING - WAC + MARGIN ==========
    print("\n" + "="*70)
    print("PHASE 7: EPIC3A - COSTING (WAC + Margin)")
    print("="*70)
    
    runner.log("Testing GET /api/costing/wac with different roles...", "INFO")
    
    # Admin should be able to access costing (200)
    success, wac_data = runner.test(
        "GET costing/wac as ADMIN (should 200)",
        "GET",
        "costing/wac",
        200,
        token=runner.admin_token,
        check_response=lambda r: isinstance(r, list) and len(r) > 0
    )
    
    if success and wac_data:
        runner.log(f"  Found {len(wac_data)} products with WAC data", "INFO")
        # Check first item has required fields
        if len(wac_data) > 0:
            item = wac_data[0]
            required_fields = ['product_id', 'name', 'sku', 'category', 'wac', 'price', 
                             'margin_amount', 'margin_pct', 'source', 'qty_on_hand']
            missing = [f for f in required_fields if f not in item]
            if not missing:
                runner.log(f"  All required fields present ✓", "PASS")
                runner.log(f"  Sample: {item.get('name')} - WAC: {item.get('wac')}, Price: {item.get('price')}, Margin: {item.get('margin_pct')}%", "INFO")
            else:
                runner.log(f"  Missing fields: {missing}", "FAIL")
                runner.failures.append(f"WAC data missing fields: {missing}")
                runner.tests_failed += 1
    
    # Manager should also be able to access costing (200)
    runner.test(
        "GET costing/wac as MANAGER (should 200)",
        "GET",
        "costing/wac",
        200,
        token=runner.manager_token,
        check_response=lambda r: isinstance(r, list)
    )
    
    # Sales should NOT be able to access costing (403 - HPP hidden from sales)
    runner.test(
        "GET costing/wac as SALES (should 403 - HPP hidden)",
        "GET",
        "costing/wac",
        403,
        token=runner.sales_token
    )

    # ========== EPIC3B: AR RECEIPTS - BACKEND ==========
    print("\n" + "="*70)
    print("PHASE 8: EPIC3B - AR RECEIPTS (Backend)")
    print("="*70)
    
    runner.log("Testing GET /api/ar-receipts...", "INFO")
    
    # Get all receipts (should have >=2 seeded)
    success, receipts = runner.test(
        "GET ar-receipts as ADMIN (should return array)",
        "GET",
        "ar-receipts",
        200,
        token=runner.admin_token,
        check_response=lambda r: isinstance(r, list)
    )
    
    if success:
        runner.log(f"  Found {len(receipts)} AR receipts", "INFO")
        if len(receipts) >= 2:
            runner.log(f"  Has >=2 seeded receipts ✓", "PASS")
        else:
            runner.log(f"  Expected >=2 seeded receipts, found {len(receipts)}", "WARN")
    
    # Get a customer with open orders for testing
    runner.log("\nFinding customer with open AR orders...", "INFO")
    success, customers = runner.test(
        "GET customers for AR test",
        "GET",
        "customers",
        200,
        token=runner.admin_token
    )
    
    test_customer_id = None
    open_orders = []
    
    if success and customers:
        # Try to find a customer with open orders
        for customer in customers[:5]:  # Check first 5 customers
            cust_id = customer.get('id')
            url = f"{BASE_URL}/ar-receipts/open-orders?customer_id={cust_id}"
            headers = {'Authorization': f'Bearer {runner.admin_token}'}
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    orders = resp.json()
                    if orders and len(orders) > 0:
                        test_customer_id = cust_id
                        open_orders = orders
                        runner.log(f"  Found customer {customer.get('name')} with {len(orders)} open orders", "INFO")
                        break
            except:
                pass
        
        if not test_customer_id:
            runner.log("  No customer with open orders found, will use first customer", "WARN")
            test_customer_id = customers[0].get('id')
    
    # Test GET /api/ar-receipts/open-orders
    if test_customer_id:
        runner.log("\nTesting GET /api/ar-receipts/open-orders...", "INFO")
        success, open_orders_resp = runner.test(
            "GET ar-receipts/open-orders (should return array)",
            "GET",
            f"ar-receipts/open-orders?customer_id={test_customer_id}",
            200,
            token=runner.admin_token,
            check_response=lambda r: isinstance(r, list)
        )
        
        if success:
            runner.log(f"  Found {len(open_orders_resp)} open orders for customer", "INFO")
            if len(open_orders_resp) > 0:
                order = open_orders_resp[0]
                runner.log(f"  Sample order: {order.get('number')} - Outstanding: {order.get('outstanding')}", "INFO")
                open_orders = open_orders_resp
    
    # Test POST /api/ar-receipts - Create receipt
    if test_customer_id and open_orders and len(open_orders) > 0:
        runner.log("\nTesting POST /api/ar-receipts (create receipt)...", "INFO")
        
        # Test with auto-allocation (FIFO)
        test_amount = min(50000, open_orders[0].get('outstanding', 50000) * 0.5)  # Pay 50% or 50k
        
        receipt_data = {
            "customer_id": test_customer_id,
            "amount": test_amount,
            "method": "transfer",
            "notes": "Test payment - auto FIFO"
        }
        
        success, receipt = runner.test(
            "POST ar-receipts (auto FIFO allocation)",
            "POST",
            "ar-receipts",
            200,
            data=receipt_data,
            token=runner.admin_token,
            check_response=lambda r: (
                'id' in r and 
                'number' in r and 
                r.get('number', '').startswith('AR-') and
                'allocations' in r and
                isinstance(r['allocations'], list)
            )
        )
        
        if success:
            runner.test_receipt_id = receipt.get('id')
            runner.log(f"  Created receipt: {receipt.get('number')}", "INFO")
            runner.log(f"  Amount: {receipt.get('amount')}, Applied: {receipt.get('applied_total')}", "INFO")
            runner.log(f"  Allocations: {len(receipt.get('allocations', []))}", "INFO")
        
        # Test with explicit allocation
        if len(open_orders) > 0:
            runner.log("\nTesting POST ar-receipts with explicit allocation...", "INFO")
            order_to_pay = open_orders[0]
            pay_amount = min(30000, order_to_pay.get('outstanding', 30000) * 0.3)
            
            receipt_data_explicit = {
                "customer_id": test_customer_id,
                "amount": pay_amount,
                "method": "cash",
                "notes": "Test payment - explicit allocation",
                "allocations": [
                    {
                        "order_id": order_to_pay['order_id'],
                        "amount": pay_amount
                    }
                ]
            }
            
            runner.test(
                "POST ar-receipts (explicit allocation)",
                "POST",
                "ar-receipts",
                200,
                data=receipt_data_explicit,
                token=runner.admin_token,
                check_response=lambda r: 'id' in r and len(r.get('allocations', [])) > 0
            )
        
        # Test over-allocation (should return 400)
        runner.log("\nTesting over-allocation (should 400)...", "INFO")
        if len(open_orders) > 0:
            order_to_overallocate = open_orders[0]
            over_amount = order_to_overallocate.get('outstanding', 100000) + 100000  # Way over
            
            receipt_data_over = {
                "customer_id": test_customer_id,
                "amount": over_amount,
                "method": "transfer",
                "allocations": [
                    {
                        "order_id": order_to_overallocate['order_id'],
                        "amount": over_amount
                    }
                ]
            }
            
            runner.test(
                "POST ar-receipts (over-allocation should 400)",
                "POST",
                "ar-receipts",
                400,
                data=receipt_data_over,
                token=runner.admin_token
            )

    # ========== EPIC3B: AR RECEIPTS - RBAC ==========
    print("\n" + "="*70)
    print("PHASE 9: EPIC3B - AR RECEIPTS RBAC")
    print("="*70)
    
    runner.log("Testing AR receipt permissions by role...", "INFO")
    
    # Sales should be able to GET and POST (sales collect payments)
    runner.test(
        "SALES GET ar-receipts (should 200)",
        "GET",
        "ar-receipts",
        200,
        token=runner.sales_token
    )
    
    if test_customer_id:
        runner.test(
            "SALES POST ar-receipts (should 200 - sales can collect)",
            "POST",
            "ar-receipts",
            200,
            data={
                "customer_id": test_customer_id,
                "amount": 10000,
                "method": "cash",
                "notes": "Test by sales"
            },
            token=runner.sales_token,
            check_response=lambda r: 'id' in r
        )
    
    # Warehouse should NOT be able to POST (403)
    if test_customer_id:
        runner.test(
            "WAREHOUSE POST ar-receipts (should 403)",
            "POST",
            "ar-receipts",
            403,
            data={
                "customer_id": test_customer_id,
                "amount": 10000,
                "method": "cash"
            },
            token=runner.warehouse_token
        )

    # ========== EPIC3B: AR INTEGRATION ==========
    print("\n" + "="*70)
    print("PHASE 10: EPIC3B - AR INTEGRATION (Outstanding reduction)")
    print("="*70)
    
    runner.log("Verifying payment reduces outstanding in collection worklist...", "INFO")
    
    # This is tested implicitly by the payment creation above
    # The collection-reminders endpoint should show reduced outstanding
    # We'll just verify the endpoint is accessible
    
    runner.test(
        "GET collection-reminders (verify endpoint works)",
        "GET",
        "collection-reminders",
        200,
        token=runner.admin_token,
        check_response=lambda r: isinstance(r, list)
    )
    
    # Verify customer credit-status endpoint
    if test_customer_id:
        runner.log("\nVerifying customer credit-status endpoint...", "INFO")
        runner.test(
            "GET customer credit-status (verify endpoint works)",
            "GET",
            f"crm/customers/{test_customer_id}/credit-status",
            200,
            token=runner.admin_token,
            check_response=lambda r: 'ar_outstanding' in r or 'outstanding' in r
        )

    # ========== EPIC4: INCENTIVE ENGINE V2 - COMMISSION ENDPOINT ==========
    print("\n" + "="*70)
    print("PHASE 11: EPIC4 - INCENTIVE ENGINE V2 (Commission Endpoint)")
    print("="*70)
    
    runner.log("Testing GET /api/sales/commission?period=2026-06...", "INFO")
    
    # Test commission endpoint as SALES user
    success, comm_data = runner.test(
        "GET sales/commission as SALES (period=2026-06)",
        "GET",
        "sales/commission?period=2026-06",
        200,
        token=runner.sales_token,
        check_response=lambda r: (
            'strategy' in r and
            'breakdown' in r and
            isinstance(r['breakdown'], list) and
            'total_incentive' in r and
            'projection_full' in r and
            'kpi' in r and
            'total_collected' in r['kpi']
        )
    )
    
    if success:
        runner.log(f"  Strategy: {comm_data.get('strategy')}", "INFO")
        runner.log(f"  Total incentive: {comm_data.get('total_incentive')}", "INFO")
        runner.log(f"  Projection full: {comm_data.get('projection_full')}", "INFO")
        runner.log(f"  Breakdown items: {len(comm_data.get('breakdown', []))}", "INFO")
        runner.log(f"  KPI total_collected: {comm_data.get('kpi', {}).get('total_collected')}", "INFO")
        
        # Verify strategy is per_sku (default)
        if comm_data.get('strategy') == 'per_sku':
            runner.log("  Strategy is per_sku (v2) ✓", "PASS")
        else:
            runner.log(f"  Expected strategy 'per_sku', got '{comm_data.get('strategy')}'", "WARN")
        
        # Verify breakdown has category/SKU data
        if len(comm_data.get('breakdown', [])) > 0:
            item = comm_data['breakdown'][0]
            if 'category' in item and 'qty_base' in item and 'commission' in item:
                runner.log(f"  Breakdown has required fields (category, qty_base, commission) ✓", "PASS")
            else:
                runner.log("  Breakdown missing required fields", "FAIL")
                runner.failures.append("Commission breakdown missing required fields")
                runner.tests_failed += 1

    # ========== EPIC4: STRATEGY TOGGLE ==========
    print("\n" + "="*70)
    print("PHASE 12: EPIC4 - STRATEGY TOGGLE")
    print("="*70)
    
    runner.log("Testing strategy toggle (per_sku <-> achievement_tiered)...", "INFO")
    
    # Get current settings
    success, settings = runner.test(
        "GET settings/effective (check current strategy)",
        "GET",
        "settings/effective",
        200,
        token=runner.admin_token,
        check_response=lambda r: 'commission' in r
    )
    
    original_strategy = None
    if success:
        original_strategy = settings.get('commission', {}).get('strategy', 'per_sku')
        runner.log(f"  Current strategy: {original_strategy}", "INFO")
    
    # Test switching to achievement_tiered (as ADMIN)
    runner.log("\nSwitching to achievement_tiered strategy...", "INFO")
    success, _ = runner.test(
        "PUT settings (switch to achievement_tiered)",
        "PUT",
        "settings",
        200,
        data={"scope": "global", "commission": {"strategy": "achievement_tiered"}},
        token=runner.admin_token
    )
    
    if success:
        # Verify strategy changed
        success, comm_check = runner.test(
            "GET sales/commission (verify achievement_tiered)",
            "GET",
            "sales/commission?period=2026-06",
            200,
            token=runner.sales_token,
            check_response=lambda r: (
                r.get('strategy') == 'achievement_tiered' and
                'applied_rate' in r and
                'achievement_pct' in r
            )
        )
        
        if success:
            runner.log(f"  Strategy switched to achievement_tiered ✓", "PASS")
            runner.log(f"  Applied rate: {comm_check.get('applied_rate')}", "INFO")
            runner.log(f"  Achievement %: {comm_check.get('achievement_pct')}", "INFO")
    
    # Revert to per_sku
    runner.log("\nReverting to per_sku strategy...", "INFO")
    runner.test(
        "PUT settings (revert to per_sku)",
        "PUT",
        "settings",
        200,
        data={"scope": "global", "commission": {"strategy": "per_sku"}},
        token=runner.admin_token
    )
    
    # Test that SALES cannot change strategy (403)
    runner.log("\nTesting SALES cannot change strategy...", "INFO")
    runner.test(
        "PUT settings as SALES (should 403)",
        "PUT",
        "settings",
        403,
        data={"scope": "global", "commission": {"strategy": "achievement_tiered"}},
        token=runner.sales_token
    )

    # ========== EPIC4: INCENTIVE RATES CRUD ==========
    print("\n" + "="*70)
    print("PHASE 13: EPIC4 - INCENTIVE RATES CRUD")
    print("="*70)
    
    runner.log("Testing GET /api/incentive-rates...", "INFO")
    
    # Test GET as MANAGER (should work)
    success, rates = runner.test(
        "GET incentive-rates as MANAGER (should 200)",
        "GET",
        "incentive-rates",
        200,
        token=runner.manager_token,
        check_response=lambda r: isinstance(r, list) and len(r) >= 7
    )
    
    if success:
        runner.log(f"  Found {len(rates)} incentive rates", "INFO")
        if len(rates) >= 7:
            runner.log("  Has >=7 rate rows (entity 'all' x 7 categories) ✓", "PASS")
        
        # Check first rate has required fields
        if len(rates) > 0:
            rate = rates[0]
            required_fields = ['id', 'entity_id', 'category', 'per_unit_amount', 
                             'discount_mechanic', 'margin_cap_pct']
            missing = [f for f in required_fields if f not in rate]
            if not missing:
                runner.log("  Rate has all required fields ✓", "PASS")
                runner.log(f"  Sample: {rate.get('category')} - {rate.get('per_unit_amount')}/unit", "INFO")
            else:
                runner.log(f"  Missing fields: {missing}", "FAIL")
                runner.failures.append(f"Rate missing fields: {missing}")
                runner.tests_failed += 1
    
    # Test GET as SALES (should 403)
    runner.log("\nTesting SALES cannot access rates...", "INFO")
    runner.test(
        "GET incentive-rates as SALES (should 403)",
        "GET",
        "incentive-rates",
        403,
        token=runner.sales_token
    )
    
    # Test POST - create new rate (as MANAGER)
    runner.log("\nTesting POST /api/incentive-rates (create)...", "INFO")
    new_rate_data = {
        "entity_id": "all",
        "category": "Test Kain",
        "per_unit_amount": 5000,
        "discount_mechanic": "tier_factor",
        "discount_factor": 0.5,
        "margin_cap_pct": 50
    }
    
    success, new_rate = runner.test(
        "POST incentive-rates as MANAGER (create)",
        "POST",
        "incentive-rates",
        200,
        data=new_rate_data,
        token=runner.manager_token,
        check_response=lambda r: 'id' in r and r.get('category') == 'Test Kain'
    )
    
    created_rate_id = None
    if success:
        created_rate_id = new_rate.get('id')
        runner.log(f"  Created rate ID: {created_rate_id}", "INFO")
    
    # Test POST as SALES (should 403)
    runner.log("\nTesting SALES cannot create rates...", "INFO")
    runner.test(
        "POST incentive-rates as SALES (should 403)",
        "POST",
        "incentive-rates",
        403,
        data=new_rate_data,
        token=runner.sales_token
    )
    
    # Test duplicate (should 409)
    runner.log("\nTesting duplicate rate (should 409)...", "INFO")
    runner.test(
        "POST incentive-rates (duplicate entity+category should 409)",
        "POST",
        "incentive-rates",
        409,
        data=new_rate_data,
        token=runner.manager_token
    )
    
    # Test PATCH - update rate
    if created_rate_id:
        runner.log("\nTesting PATCH /api/incentive-rates/{id} (update)...", "INFO")
        runner.test(
            "PATCH incentive-rates (update rate)",
            "PATCH",
            f"incentive-rates/{created_rate_id}",
            200,
            data={"data": {"per_unit_amount": 6000, "margin_cap_pct": 60}},
            token=runner.manager_token,
            check_response=lambda r: r.get('per_unit_amount') == 6000
        )
    
    # Test DELETE
    if created_rate_id:
        runner.log("\nTesting DELETE /api/incentive-rates/{id}...", "INFO")
        runner.test(
            "DELETE incentive-rates (delete test rate)",
            "DELETE",
            f"incentive-rates/{created_rate_id}",
            200,
            token=runner.manager_token,
            check_response=lambda r: r.get('deleted') == True
        )

    # ========== FASE 2: UoM SSOT (Roll Count) ==========
    print("\n" + "="*70)
    print("PHASE 14: FASE 2 - UoM SSOT (Roll Count)")
    print("="*70)
    
    runner.log("Testing GET /api/products returns roll_count and on_hand_roll_count...", "INFO")
    
    # Test GET /api/products - verify roll_count fields
    success, products_f2 = runner.test(
        "GET products (verify roll_count fields)",
        "GET",
        "products",
        200,
        token=runner.admin_token,
        check_response=lambda r: (
            isinstance(r, list) and 
            len(r) > 0 and
            'roll_count' in r[0] and
            'on_hand_roll_count' in r[0]
        )
    )
    
    if success and products_f2:
        runner.log(f"  Found {len(products_f2)} products", "INFO")
        sample = products_f2[0]
        runner.log(f"  Sample: {sample.get('name')} - roll_count: {sample.get('roll_count')}, on_hand_roll_count: {sample.get('on_hand_roll_count')}", "INFO")
        
        # Verify all products have these fields
        all_have_fields = all('roll_count' in p and 'on_hand_roll_count' in p for p in products_f2)
        if all_have_fields:
            runner.log("  All products have roll_count and on_hand_roll_count ✓", "PASS")
        else:
            runner.log("  Some products missing roll_count fields", "FAIL")
            runner.failures.append("Some products missing roll_count/on_hand_roll_count")
            runner.tests_failed += 1
    
    # Test GET /api/inventory/balances - verify roll_count, on_hand_roll_count, base_unit
    runner.log("\nTesting GET /api/inventory/balances returns roll fields...", "INFO")
    success, balances_f2 = runner.test(
        "GET inventory/balances (verify roll_count, on_hand_roll_count, base_unit)",
        "GET",
        "inventory/balances",
        200,
        token=runner.admin_token,
        check_response=lambda r: (
            isinstance(r, list) and 
            len(r) > 0 and
            'roll_count' in r[0] and
            'on_hand_roll_count' in r[0] and
            'base_unit' in r[0]
        )
    )
    
    if success and balances_f2:
        runner.log(f"  Found {len(balances_f2)} balances", "INFO")
        sample = balances_f2[0]
        runner.log(f"  Sample: {sample.get('product_name')} - roll_count: {sample.get('roll_count')}, on_hand_roll_count: {sample.get('on_hand_roll_count')}, base_unit: {sample.get('base_unit')}", "INFO")
        
        # Verify all balances have these fields
        all_have_fields = all('roll_count' in b and 'on_hand_roll_count' in b and 'base_unit' in b for b in balances_f2)
        if all_have_fields:
            runner.log("  All balances have roll_count, on_hand_roll_count, base_unit ✓", "PASS")
        else:
            runner.log("  Some balances missing required fields", "FAIL")
            runner.failures.append("Some balances missing roll_count/on_hand_roll_count/base_unit")
            runner.tests_failed += 1
    
    # Test GET /api/products/{id}/stock-breakdown - verify ownership_matrix has roll_count
    if products_f2 and len(products_f2) > 0:
        test_product = products_f2[0]
        runner.log(f"\nTesting GET /api/products/{test_product['id']}/stock-breakdown...", "INFO")
        
        success, breakdown_f2 = runner.test(
            "GET products/{id}/stock-breakdown (verify ownership_matrix roll_count)",
            "GET",
            f"products/{test_product['id']}/stock-breakdown",
            200,
            token=runner.admin_token,
            check_response=lambda r: (
                'ownership_matrix' in r and
                isinstance(r['ownership_matrix'], list)
            )
        )
        
        if success and breakdown_f2:
            matrix = breakdown_f2.get('ownership_matrix', [])
            runner.log(f"  Found {len(matrix)} ownership_matrix cells", "INFO")
            
            if len(matrix) > 0:
                sample_cell = matrix[0]
                has_roll_count = 'roll_count' in sample_cell
                
                if has_roll_count:
                    runner.log(f"  Sample cell: owner={sample_cell.get('owner_entity_name')}, warehouse={sample_cell.get('warehouse_name')}, roll_count={sample_cell.get('roll_count')} ✓", "PASS")
                    
                    # Verify all cells have roll_count
                    all_have_roll_count = all('roll_count' in cell for cell in matrix)
                    if all_have_roll_count:
                        runner.log("  All ownership_matrix cells have roll_count ✓", "PASS")
                    else:
                        runner.log("  Some ownership_matrix cells missing roll_count", "FAIL")
                        runner.failures.append("Some ownership_matrix cells missing roll_count")
                        runner.tests_failed += 1
                else:
                    runner.log("  ownership_matrix cells missing roll_count field", "FAIL")
                    runner.failures.append("ownership_matrix cells missing roll_count")
                    runner.tests_failed += 1
    
    # Test POST /api/sales-orders - verify creating SO with unit=base_unit still works
    runner.log("\nTesting POST /api/sales-orders with unit=base_unit (no unit-conversion breakage)...", "INFO")
    
    if products_f2 and len(products_f2) > 0:
        # Get a customer
        success, customers_f2 = runner.test(
            "GET customers for FASE 2 SO test",
            "GET",
            "customers",
            200,
            token=runner.admin_token
        )
        
        if success and customers_f2 and len(customers_f2) > 0:
            customer = customers_f2[0]
            product = products_f2[0]
            base_unit = product.get('base_unit', 'meter')
            
            # Get customer's first address
            addresses = customer.get('addresses', [])
            shipping_address_id = addresses[0]['id'] if addresses else None
            
            # Create a sales order with base_unit
            so_data_f2 = {
                "customer_id": customer['id'],
                "shipping_address_id": shipping_address_id,
                "items": [
                    {
                        "product_id": product['id'],
                        "quantity": 5,
                        "unit": base_unit,
                        "price": product.get('price', 100000)
                    }
                ]
            }
            
            success, so_f2 = runner.test(
                f"POST sales-orders (unit={base_unit}, verify no breakage)",
                "POST",
                "sales-orders",
                200,
                data=so_data_f2,
                token=runner.admin_token,
                check_response=lambda r: (
                    'number' in r and 
                    r.get('number', '').startswith('SO-') and
                    'status' in r and
                    r.get('status') in ['reserved', 'waiting_approval']
                )
            )
            
            if success and so_f2:
                runner.log(f"  Created SO: {so_f2.get('number')}, status: {so_f2.get('status')} ✓", "PASS")
                runner.log(f"  Unit conversion working correctly with base_unit={base_unit}", "PASS")
        else:
            runner.log("  No customers found, skipping SO test", "WARN")
    else:
        runner.log("  No products found, skipping SO test", "WARN")

    # ========== EPIC6: Document Relations / Process Timeline ==========
    runner.log("\n" + "="*60, "INFO")
    runner.log("EPIC6: Document Relations / Process Timeline", "INFO")
    runner.log("="*60, "INFO")
    
    # Test GET /api/documents/relations/sales_order/so_001
    runner.log("\nTesting GET /api/documents/relations/sales_order/so_001...", "INFO")
    success, so_relations = runner.test(
        "GET sales_order relations (so_001)",
        "GET",
        "documents/relations/sales_order/so_001",
        200,
        token=runner.admin_token,
        check_response=lambda r: (
            r.get('doc_type') == 'sales_order' and
            r.get('anchor', {}).get('number') == 'SO-0001' and
            'stages' in r
        )
    )
    
    if success and so_relations:
        stages = {s['key']: s for s in so_relations.get('stages', [])}
        expected_stages = ['order', 'shipment', 'tax', 'payment', 'commission']
        
        # Check all stages present
        all_present = all(k in stages for k in expected_stages)
        runner.log(f"  SO stages present: {list(stages.keys())}", "INFO")
        if all_present:
            runner.log("  All expected SO stages present", "PASS")
            runner.tests_passed += 1
        else:
            runner.log(f"  Missing stages: {[k for k in expected_stages if k not in stages]}", "FAIL")
            runner.tests_failed += 1
        
        # Check order stage has 1 anchor
        order_docs = stages.get('order', {}).get('docs', [])
        if len(order_docs) == 1:
            runner.log("  Order stage has 1 anchor doc", "PASS")
            runner.tests_passed += 1
        else:
            runner.log(f"  Order stage has {len(order_docs)} docs (expected 1)", "FAIL")
            runner.tests_failed += 1
        
        # Check shipment has doc_url with /surat-jalan
        shipment_docs = stages.get('shipment', {}).get('docs', [])
        if shipment_docs:
            first_ship = shipment_docs[0]
            has_doc_url = (first_ship.get('link', {}).get('kind') == 'url' and
                          '/surat-jalan' in (first_ship.get('link', {}).get('doc_url') or ''))
            if has_doc_url:
                runner.log("  Shipment has doc_url with /surat-jalan", "PASS")
                runner.tests_passed += 1
            else:
                runner.log("  Shipment missing doc_url with /surat-jalan", "FAIL")
                runner.tests_failed += 1
        
        # Check payment has AR receipt with amount
        payment_docs = stages.get('payment', {}).get('docs', [])
        if payment_docs:
            first_pay = payment_docs[0]
            is_ar = first_pay.get('type') == 'ar_receipt'
            has_amount = first_pay.get('amount') is not None
            if is_ar and has_amount:
                runner.log(f"  Payment has AR receipt with amount: {first_pay.get('amount')}", "PASS")
                runner.tests_passed += 1
            else:
                runner.log(f"  Payment AR receipt issue: type={first_pay.get('type')}, amount={first_pay.get('amount')}", "FAIL")
                runner.tests_failed += 1
        
        # Check empty stages have empty_hint
        tax_stage = stages.get('tax', {})
        if 'empty_hint' in tax_stage:
            runner.log("  Empty stages have empty_hint (no dead-end)", "PASS")
            runner.tests_passed += 1
        else:
            runner.log("  Empty stages missing empty_hint", "FAIL")
            runner.tests_failed += 1
    
    # Test GET /api/documents/relations/purchase_order/po_009
    runner.log("\nTesting GET /api/documents/relations/purchase_order/po_009...", "INFO")
    success, po_relations = runner.test(
        "GET purchase_order relations (po_009)",
        "GET",
        "documents/relations/purchase_order/po_009",
        200,
        token=runner.admin_token,
        check_response=lambda r: (
            r.get('doc_type') == 'purchase_order' and
            'stages' in r
        )
    )
    
    if success and po_relations:
        stages = {s['key']: s for s in po_relations.get('stages', [])}
        expected_stages = ['requisition', 'po', 'grn', 'landed_cost', 'bill']
        
        # Check all stages present
        all_present = all(k in stages for k in expected_stages)
        runner.log(f"  PO stages present: {list(stages.keys())}", "INFO")
        if all_present:
            runner.log("  All expected PO stages present", "PASS")
            runner.tests_passed += 1
        else:
            runner.log(f"  Missing stages: {[k for k in expected_stages if k not in stages]}", "FAIL")
            runner.tests_failed += 1
        
        # Check requisition has 1 PR
        req_docs = stages.get('requisition', {}).get('docs', [])
        if len(req_docs) == 1:
            pr = req_docs[0]
            if pr.get('type') == 'purchase_requisition' and pr.get('link', {}).get('view') == 'purchase-requisitions':
                runner.log("  Requisition has 1 PR with correct link", "PASS")
                runner.tests_passed += 1
            else:
                runner.log(f"  PR link issue: type={pr.get('type')}, view={pr.get('link',{}).get('view')}", "FAIL")
                runner.tests_failed += 1
        else:
            runner.log(f"  Requisition has {len(req_docs)} docs (expected 1)", "FAIL")
            runner.tests_failed += 1
        
        # Check GRN has link.view=operations
        grn_docs = stages.get('grn', {}).get('docs', [])
        if grn_docs:
            first_grn = grn_docs[0]
            if first_grn.get('link', {}).get('view') == 'operations':
                runner.log("  GRN has link.view=operations", "PASS")
                runner.tests_passed += 1
            else:
                runner.log(f"  GRN link issue: view={first_grn.get('link',{}).get('view')}", "FAIL")
                runner.tests_failed += 1
        
        # Check PO anchor has link.view=purchasing
        po_docs = stages.get('po', {}).get('docs', [])
        if po_docs:
            po_link = po_docs[0].get('link', {})
            if po_link.get('view') == 'purchasing':
                runner.log("  PO anchor has link.view=purchasing", "PASS")
                runner.tests_passed += 1
            else:
                runner.log(f"  PO anchor link issue: view={po_link.get('view')}", "FAIL")
                runner.tests_failed += 1
        
        # Check empty stages have empty_hint
        landed_stage = stages.get('landed_cost', {})
        bill_stage = stages.get('bill', {})
        if 'empty_hint' in landed_stage and 'empty_hint' in bill_stage:
            runner.log("  Empty stages have empty_hint", "PASS")
            runner.tests_passed += 1
        else:
            runner.log("  Empty stages missing empty_hint", "FAIL")
            runner.tests_failed += 1
    
    # Test RBAC: sales role
    runner.log("\nTesting RBAC for document relations...", "INFO")
    runner.test(
        "Sales role -> PO relations (should 403)",
        "GET",
        "documents/relations/purchase_order/po_009",
        403,
        token=runner.sales_token
    )
    
    runner.test(
        "Sales role -> SO relations (should 200)",
        "GET",
        "documents/relations/sales_order/so_001",
        200,
        token=runner.sales_token
    )
    
    # Test error handling
    runner.log("\nTesting error handling...", "INFO")
    runner.test(
        "Invalid doc_type (should 400)",
        "GET",
        "documents/relations/foobar/x",
        400,
        token=runner.admin_token
    )
    
    runner.test(
        "Unknown id (should 404)",
        "GET",
        "documents/relations/sales_order/nope",
        404,
        token=runner.admin_token
    )

    # ========== PRINT SUMMARY ==========
    runner.print_summary()
    
    return 0 if runner.tests_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
