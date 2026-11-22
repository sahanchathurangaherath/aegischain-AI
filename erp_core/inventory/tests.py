from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase

from inventory.models import InventoryBalance, InventoryScan, Product, Warehouse


class InventoryScanMovementTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            product_code="RM-STEEL-001",
            name="Structural Steel Plate",
            category="RAW_MATERIAL",
            unit_of_measure="KG",
            unit_price=Decimal("25.00"),
            reorder_point=100,
            safety_stock=50,
            lead_time_days=7,
        )
        self.wh_main = Warehouse.objects.create(
            warehouse_code="WH-MAIN-01",
            name="Main Warehouse",
            warehouse_type="MAIN",
            address="100 Industrial Way",
            city="Colombo",
            state="Western",
            country="Sri Lanka",
            postal_code="00100",
            manager_name="Alice",
            phone="0112345678",
            email="main@aegischain.local",
            total_capacity=5000,
        )
        self.wh_regional = Warehouse.objects.create(
            warehouse_code="WH-REG-02",
            name="Regional Warehouse",
            warehouse_type="REGIONAL",
            address="200 Harbor Rd",
            city="Galle",
            state="Southern",
            country="Sri Lanka",
            postal_code="80000",
            manager_name="Bob",
            phone="0912345678",
            email="reg@aegischain.local",
            total_capacity=2000,
        )

    def test_in_out_transfer_and_audit_scans_update_balances(self):
        # 1. IN scan adds 200 units
        scan_in = InventoryScan.objects.create(
            product=self.product,
            warehouse=self.wh_main,
            scan_type="IN",
            quantity=200,
            scanned_by="operator_1",
        )
        scan_in.process_scan()

        main_balance = InventoryBalance.objects.get(product=self.product, warehouse=self.wh_main)
        self.assertEqual(main_balance.quantity_on_hand, 200)
        self.assertEqual(main_balance.quantity_available, 200)
        self.assertTrue(scan_in.is_processed)

        # 2. OUT scan deducts 50 units
        scan_out = InventoryScan.objects.create(
            product=self.product,
            warehouse=self.wh_main,
            scan_type="OUT",
            quantity=50,
            scanned_by="operator_1",
        )
        scan_out.process_scan()

        main_balance.refresh_from_db()
        self.assertEqual(main_balance.quantity_on_hand, 150)

        # 3. TRANSFER scan moves 40 units from WH-MAIN-01 to WH-REG-02
        scan_transfer = InventoryScan.objects.create(
            product=self.product,
            warehouse=self.wh_main,
            scan_type="TRANSFER",
            quantity=40,
            scanned_by="operator_1",
            reference_number="WH-REG-02",
        )
        scan_transfer.process_scan()

        main_balance.refresh_from_db()
        reg_balance = InventoryBalance.objects.get(product=self.product, warehouse=self.wh_regional)
        self.assertEqual(main_balance.quantity_on_hand, 110)
        self.assertEqual(reg_balance.quantity_on_hand, 40)

        # 4. AUDIT scan records physical count of 105 and computes variance (-5)
        scan_audit = InventoryScan.objects.create(
            product=self.product,
            warehouse=self.wh_main,
            scan_type="AUDIT",
            quantity=105,
            scanned_by="auditor_1",
        )
        scan_audit.process_scan()

        main_balance.refresh_from_db()
        self.assertEqual(main_balance.last_physical_count, 105)
        self.assertEqual(main_balance.variance, -5)

    def test_out_scan_rejects_insufficient_stock(self):
        InventoryBalance.objects.create(
            product=self.product,
            warehouse=self.wh_main,
            quantity_on_hand=20,
        )
        scan_out = InventoryScan.objects.create(
            product=self.product,
            warehouse=self.wh_main,
            scan_type="OUT",
            quantity=50,
            scanned_by="operator_1",
        )
        with self.assertRaises(ValidationError):
            scan_out.process_scan()
