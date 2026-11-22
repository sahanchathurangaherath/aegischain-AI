from datetime import timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from inventory.models import Product, Warehouse
from procurement.models import PurchaseOrder, PurchaseOrderItem, Shipment, Supplier


class PurchaseOrderStateTransitionTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            supplier_code="SUP-001",
            name="Apex Steel Suppliers",
            supplier_type="MANUFACTURER",
            contact_person="John Silva",
            email="john@apexsteel.local",
            phone="0119998888",
            address="10 Metal Park",
            city="Colombo",
            state="Western",
            country="Sri Lanka",
            postal_code="00200",
            payment_terms="NET_30",
            lead_time_days=14,
            quality_rating=4.5,
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
            total_capacity=5000,
        )
        self.product = Product.objects.create(
            product_code="RM-STEEL-001",
            name="Structural Steel Plate",
            category="RAW_MATERIAL",
            unit_of_measure="KG",
            unit_price=Decimal("25.00"),
        )
        self.po = PurchaseOrder.objects.create(
            po_number="PO-2026-001",
            supplier=self.supplier,
            warehouse=self.warehouse,
            expected_delivery_date=timezone.now().date() + timedelta(days=14),
        )
        PurchaseOrderItem.objects.create(
            purchase_order=self.po,
            product=self.product,
            quantity_ordered=100,
            unit_price=Decimal("25.00"),
        )

    def test_valid_purchase_order_state_transitions(self):
        self.assertEqual(self.po.status, "DRAFT")
        self.assertEqual(self.po.subtotal, Decimal("2500.00"))
        self.assertEqual(self.po.total_amount, Decimal("2750.00"))

        self.po.transition_to("SUBMITTED")
        self.assertEqual(self.po.status, "SUBMITTED")

        self.po.transition_to("CONFIRMED")
        self.assertEqual(self.po.status, "CONFIRMED")

        self.po.transition_to("SHIPPED")
        self.assertEqual(self.po.status, "SHIPPED")

        self.po.transition_to("PARTIALLY_RECEIVED")
        self.assertEqual(self.po.status, "PARTIALLY_RECEIVED")

        self.po.transition_to("RECEIVED")
        self.assertEqual(self.po.status, "RECEIVED")
        self.assertIsNotNone(self.po.actual_delivery_date)

    def test_invalid_purchase_order_transitions_rejected(self):
        # Cannot jump directly from DRAFT to RECEIVED
        with self.assertRaises(ValidationError):
            self.po.transition_to("RECEIVED")

        # Move to CANCELLED, then verify terminal state rejects further transitions
        self.po.transition_to("CANCELLED")
        with self.assertRaises(ValidationError):
            self.po.transition_to("SUBMITTED")

    def test_supplier_reliability_calculation(self):
        today = timezone.now().date()
        Shipment.objects.create(
            shipment_number="SHP-001",
            purchase_order=self.po,
            expected_arrival_date=today - timedelta(days=5),
            actual_arrival_date=today - timedelta(days=5),
            delay_days=0,
            status="RECEIVED",
        )
        Shipment.objects.create(
            shipment_number="SHP-002",
            purchase_order=self.po,
            expected_arrival_date=today - timedelta(days=10),
            actual_arrival_date=today - timedelta(days=7),
            delay_days=3,
            status="RECEIVED",
        )
        self.supplier.update_reliability_score()
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.on_time_delivery_rate, 50.0)
