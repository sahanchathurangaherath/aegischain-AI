from datetime import timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from inventory.models import InventoryBalance, InventoryScan, Product, Warehouse
from sales.models import SalesOrder, SalesOrderItem


class SalesOrderFulfillmentTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            product_code="FG-WIDGET-001",
            name="Precision Widget",
            category="FINISHED_GOOD",
            unit_of_measure="EA",
            unit_price=Decimal("40.00"),
            unit_volume_cbm=Decimal("0.5000"),
        )
        self.warehouse = Warehouse.objects.create(
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
            total_capacity=100,
        )
        self.balance = InventoryBalance.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            quantity_on_hand=100,
        )
        self.so = SalesOrder.objects.create(
            so_number="SO-2026-001",
            customer_name="Acme Corp",
            customer_email="orders@acme.local",
            customer_phone="0115551234",
            shipping_address="50 Market St",
            shipping_city="Colombo",
            shipping_state="Western",
            shipping_country="Sri Lanka",
            shipping_postal_code="00300",
            warehouse=self.warehouse,
            required_date=timezone.now().date() + timedelta(days=5),
        )
        SalesOrderItem.objects.create(
            sales_order=self.so,
            product=self.product,
            quantity_ordered=30,
            unit_price=Decimal("40.00"),
        )

    def test_confirm_and_fulfill_order_updates_stock_and_logs_out_scan(self):
        # Verify initial warehouse utilization: 100 units * 0.5 cbm / 100 cbm = 50.00%
        self.assertEqual(self.warehouse.update_utilization(), Decimal("50.00"))

        # 1. Confirm reserves 30 units
        self.so.confirm_order()
        self.so.refresh_from_db()
        self.balance.refresh_from_db()
        self.assertEqual(self.so.status, "CONFIRMED")
        self.assertEqual(self.balance.quantity_reserved, 30)
        self.assertEqual(self.balance.quantity_available, 70)

        # 2. Fulfill deducts 30 units from on-hand and reserved, and logs an OUT scan
        self.so.fulfill_order(scanned_by="packer_1")
        self.so.refresh_from_db()
        self.balance.refresh_from_db()
        self.assertEqual(self.so.status, "SHIPPED")
        self.assertIsNotNone(self.so.shipped_date)
        self.assertEqual(self.balance.quantity_on_hand, 70)
        self.assertEqual(self.balance.quantity_reserved, 0)
        self.assertEqual(self.balance.quantity_available, 70)

        out_scan = InventoryScan.objects.filter(
            reference_number="SO-2026-001", scan_type="OUT"
        ).first()
        self.assertIsNotNone(out_scan)
        self.assertEqual(out_scan.quantity, 30)
        self.assertTrue(out_scan.is_processed)

    def test_confirm_order_rejects_insufficient_stock(self):
        SalesOrderItem.objects.create(
            sales_order=self.so,
            product=self.product,
            quantity_ordered=200,
            unit_price=Decimal("40.00"),
        )
        with self.assertRaises(ValidationError):
            self.so.confirm_order()