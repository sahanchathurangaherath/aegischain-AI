from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import random

from inventory.models import Product, Warehouse
from procurement.models import Supplier, PurchaseOrder, PurchaseOrderItem, Shipment
from sales.models import SalesOrder, SalesOrderItem


class Command(BaseCommand):
    help = 'Seed Phase 3 data: Purchase Orders, Sales Orders, Shipments'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("Phase 3 - Seeding Procurement & Sales Data")
        self.stdout.write("=" * 60)
        
        with transaction.atomic():
            self.clear_phase3_data()
            purchase_orders = self.create_purchase_orders()
            self.create_shipments(purchase_orders)
            self.create_sales_orders()
        
        self.print_summary()

    def clear_phase3_data(self):
        """Clear Phase 3 data only"""
        self.stdout.write("\nClearing Phase 3 data...")
        SalesOrderItem.objects.all().delete()
        SalesOrder.objects.all().delete()
        Shipment.objects.all().delete()
        PurchaseOrderItem.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("✓ Phase 3 data cleared"))

    def create_purchase_orders(self):
        """Create sample purchase orders"""
        self.stdout.write("\nCreating purchase orders...")
        
        suppliers = list(Supplier.objects.all())
        warehouses = list(Warehouse.objects.all())
        products = list(Product.objects.all())
        
        statuses = ['CONFIRMED', 'SHIPPED', 'RECEIVED', 'SUBMITTED']
        
        purchase_orders = []
        
        for i in range(1, 11):  # Create 10 POs
            supplier = random.choice(suppliers)
            warehouse = random.choice(warehouses)
            
            order_date = timezone.now().date() - timedelta(days=random.randint(5, 60))
            expected_delivery = order_date + timedelta(days=supplier.lead_time_days)
            
            po = PurchaseOrder.objects.create(
                po_number=f'PO-2024-{i:04d}',
                supplier=supplier,
                warehouse=warehouse,
                order_date=order_date,
                expected_delivery_date=expected_delivery,
                status=random.choice(statuses),
                payment_terms=supplier.payment_terms,
                created_by='system'
            )
            
            # Add 2-5 items to each PO
            num_items = random.randint(2, 5)
            for _ in range(num_items):
                product = random.choice(products)
                quantity = random.randint(50, 500)
                
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    product=product,
                    quantity_ordered=quantity,
                    quantity_received=quantity if po.status == 'RECEIVED' else random.randint(0, quantity),
                    unit_price=product.unit_price
                )
            
            po.calculate_totals()
            purchase_orders.append(po)
            self.stdout.write(f"  ✓ Created: {po}")
        
        return purchase_orders

    def create_shipments(self, purchase_orders):
        """Create shipments for POs"""
        self.stdout.write("\nCreating shipments...")
        
        carriers = ['FedEx', 'UPS', 'DHL', 'USPS', 'Local Freight']
        
        for po in purchase_orders:
            if po.status in ['SHIPPED', 'RECEIVED']:
                shipped_date = po.order_date + timedelta(days=random.randint(1, 3))
                actual_arrival = None
                delay_days = 0
                status = 'IN_TRANSIT'
                
                if po.status == 'RECEIVED':
                    # Simulate some delays
                    if random.random() > 0.7:  # 30% chance of delay
                        delay_days = random.randint(1, 7)
                    actual_arrival = po.expected_delivery_date + timedelta(days=delay_days)
                    status = 'RECEIVED'
                
                shipment = Shipment.objects.create(
                    shipment_number=f'SHIP-{po.po_number}',
                    purchase_order=po,
                    shipped_date=shipped_date,
                    expected_arrival_date=po.expected_delivery_date,
                    actual_arrival_date=actual_arrival,
                    status=status,
                    carrier=random.choice(carriers),
                    tracking_number=f'TRK{random.randint(100000, 999999)}',
                    delay_days=delay_days
                )
                
                if delay_days > 0:
                    shipment.delay_reason = random.choice([
                        'Weather conditions',
                        'Customs delay',
                        'Carrier delay',
                        'Traffic congestion'
                    ])
                    shipment.save()
                
                self.stdout.write(f"  ✓ Created: {shipment}")

    def create_sales_orders(self):
        """Create sample sales orders"""
        self.stdout.write("\nCreating sales orders...")
        
        warehouses = list(Warehouse.objects.all())
        products = list(Product.objects.all())
        
        customers = [
            {'name': 'ABC Corporation', 'email': 'orders@abccorp.com', 'phone': '+1-555-1001'},
            {'name': 'XYZ Industries', 'email': 'purchasing@xyzind.com', 'phone': '+1-555-1002'},
            {'name': 'Global Retail Inc', 'email': 'orders@globalretail.com', 'phone': '+1-555-1003'},
            {'name': 'Tech Solutions Ltd', 'email': 'procurement@techsol.com', 'phone': '+1-555-1004'},
            {'name': 'Premier Manufacturing', 'email': 'orders@premiermfg.com', 'phone': '+1-555-1005'},
        ]
        
        statuses = ['CONFIRMED', 'PROCESSING', 'PACKED', 'SHIPPED', 'DELIVERED']
        priorities = ['NORMAL', 'HIGH', 'URGENT', 'LOW']
        
        for i in range(1, 16):  # Create 15 sales orders
            customer = random.choice(customers)
            warehouse = random.choice(warehouses)
            
            order_date = timezone.now().date() - timedelta(days=random.randint(1, 30))
            required_date = order_date + timedelta(days=random.randint(3, 14))
            
            so = SalesOrder.objects.create(
                so_number=f'SO-2024-{i:04d}',
                customer_name=customer['name'],
                customer_email=customer['email'],
                customer_phone=customer['phone'],
                warehouse=warehouse,
                order_date=order_date,
                required_date=required_date,
                status=random.choice(statuses),
                priority=random.choice(priorities),
                shipping_address=f'{random.randint(100, 999)} Business Street',
                shipping_city=random.choice(['New York', 'Chicago', 'Los Angeles', 'Houston']),
                shipping_state=random.choice(['NY', 'IL', 'CA', 'TX']),
                shipping_country='USA',
                shipping_postal_code=f'{random.randint(10000, 99999)}',
                shipping_cost=Decimal(str(random.uniform(10, 50)))
            )
            
            # Add 1-4 items to each SO
            num_items = random.randint(1, 4)
            for _ in range(num_items):
                product = random.choice(products)
                quantity = random.randint(10, 100)
                
                SalesOrderItem.objects.create(
                    sales_order=so,
                    product=product,
                    quantity_ordered=quantity,
                    quantity_fulfilled=quantity if so.status == 'DELIVERED' else random.randint(0, quantity),
                    unit_price=product.unit_price * Decimal('1.5'),  # Mark up 50%
                    discount_percent=random.choice([0, 5, 10, 15])
                )
            
            so.calculate_totals()
            self.stdout.write(f"  ✓ Created: {so}")

    def print_summary(self):
        """Print summary"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✓ Phase 3 data creation complete!"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"\nSummary:")
        self.stdout.write(f"  - Purchase Orders: {PurchaseOrder.objects.count()}")
        self.stdout.write(f"  - PO Items: {PurchaseOrderItem.objects.count()}")
        self.stdout.write(f"  - Shipments: {Shipment.objects.count()}")
        self.stdout.write(f"  - Sales Orders: {SalesOrder.objects.count()}")
        self.stdout.write(f"  - SO Items: {SalesOrderItem.objects.count()}")
        self.stdout.write("=" * 60)