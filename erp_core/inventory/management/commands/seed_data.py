from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
import random

from inventory.models import Product, Warehouse, InventoryBalance, InventoryScan
from procurement.models import Supplier


class Command(BaseCommand):
    help = 'Seed the database with sample data for AegisChain'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("AegisChain - Seed Data Creation")
        self.stdout.write("=" * 60)
        
        with transaction.atomic():
            self.clear_data()
            warehouses = self.create_warehouses()
            suppliers = self.create_suppliers()
            products = self.create_products()
            self.create_inventory_balances(products, warehouses)
            self.create_sample_scans(products, warehouses)
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✓ Seed data creation complete!"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"\nSummary:")
        self.stdout.write(f"  - Warehouses: {Warehouse.objects.count()}")
        self.stdout.write(f"  - Suppliers: {Supplier.objects.count()}")
        self.stdout.write(f"  - Products: {Product.objects.count()}")
        self.stdout.write(f"  - Inventory Balances: {InventoryBalance.objects.count()}")
        self.stdout.write(f"  - Scans: {InventoryScan.objects.count()}")
        self.stdout.write(f"\nAccess Django Admin at: http://localhost:8000/admin")
        self.stdout.write(f"Username: admin")
        self.stdout.write(f"Password: admin123")
        self.stdout.write("=" * 60)

    def clear_data(self):
        """Clear existing data"""
        self.stdout.write("\nClearing existing data...")
        InventoryScan.objects.all().delete()
        InventoryBalance.objects.all().delete()
        Product.objects.all().delete()
        Warehouse.objects.all().delete()
        Supplier.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("✓ Data cleared"))

    def create_warehouses(self):
        """Create sample warehouses"""
        self.stdout.write("\nCreating warehouses...")
        
        warehouses = [
            {
                'warehouse_code': 'WH-MAIN-01',
                'name': 'Main Distribution Center',
                'warehouse_type': 'MAIN',
                'address': '123 Industrial Park Drive',
                'city': 'Los Angeles',
                'state': 'California',
                'country': 'USA',
                'postal_code': '90001',
                'manager_name': 'John Smith',
                'phone': '+1-555-0101',
                'email': 'john.smith@aegischain.local',
                'total_capacity': 50000
            },
            {
                'warehouse_code': 'WH-REG-02',
                'name': 'East Coast Regional Hub',
                'warehouse_type': 'REGIONAL',
                'address': '456 Logistics Boulevard',
                'city': 'New York',
                'state': 'New York',
                'country': 'USA',
                'postal_code': '10001',
                'manager_name': 'Sarah Johnson',
                'phone': '+1-555-0102',
                'email': 'sarah.johnson@aegischain.local',
                'total_capacity': 30000
            },
            {
                'warehouse_code': 'WH-REG-03',
                'name': 'Midwest Regional Hub',
                'warehouse_type': 'REGIONAL',
                'address': '789 Commerce Street',
                'city': 'Chicago',
                'state': 'Illinois',
                'country': 'USA',
                'postal_code': '60601',
                'manager_name': 'Michael Chen',
                'phone': '+1-555-0103',
                'email': 'michael.chen@aegischain.local',
                'total_capacity': 25000
            }
        ]
        
        created = []
        for wh_data in warehouses:
            warehouse = Warehouse.objects.create(**wh_data)
            created.append(warehouse)
            self.stdout.write(f"  ✓ Created: {warehouse}")
        
        return created

    def create_suppliers(self):
        """Create sample suppliers"""
        self.stdout.write("\nCreating suppliers...")
        
        suppliers = [
            {
                'supplier_code': 'SUP-001',
                'name': 'Global Tech Components Inc.',
                'supplier_type': 'MANUFACTURER',
                'contact_person': 'David Lee',
                'email': 'david.lee@globaltech.com',
                'phone': '+1-555-1001',
                'address': '100 Tech Plaza',
                'city': 'San Jose',
                'state': 'California',
                'country': 'USA',
                'postal_code': '95101',
                'payment_terms': 'NET_30',
                'lead_time_days': 10,
                'minimum_order_value': Decimal('5000.00'),
                'reliability_score': 95.5,
                'on_time_delivery_rate': 98.0,
                'quality_rating': 4.8,
                'risk_level': 'LOW',
                'is_approved': True
            },
            {
                'supplier_code': 'SUP-002',
                'name': 'Reliable Materials Co.',
                'supplier_type': 'DISTRIBUTOR',
                'contact_person': 'Emily Rodriguez',
                'email': 'emily@reliablematerials.com',
                'phone': '+1-555-1002',
                'address': '200 Supply Chain Ave',
                'city': 'Houston',
                'state': 'Texas',
                'country': 'USA',
                'postal_code': '77001',
                'payment_terms': 'NET_60',
                'lead_time_days': 7,
                'minimum_order_value': Decimal('3000.00'),
                'reliability_score': 88.0,
                'on_time_delivery_rate': 92.0,
                'quality_rating': 4.5,
                'risk_level': 'MEDIUM',
                'is_approved': True
            },
            {
                'supplier_code': 'SUP-003',
                'name': 'Premium Parts Ltd.',
                'supplier_type': 'MANUFACTURER',
                'contact_person': 'James Wilson',
                'email': 'james@premiumparts.com',
                'phone': '+1-555-1003',
                'address': '300 Manufacturing Drive',
                'city': 'Detroit',
                'state': 'Michigan',
                'country': 'USA',
                'postal_code': '48201',
                'payment_terms': 'NET_30',
                'lead_time_days': 14,
                'minimum_order_value': Decimal('10000.00'),
                'reliability_score': 75.0,
                'on_time_delivery_rate': 85.0,
                'quality_rating': 4.0,
                'risk_level': 'HIGH',
                'is_approved': True
            }
        ]
        
        created = []
        for sup_data in suppliers:
            supplier = Supplier.objects.create(**sup_data)
            created.append(supplier)
            self.stdout.write(f"  ✓ Created: {supplier}")
        
        return created

    def create_products(self):
        """Create sample products"""
        self.stdout.write("\nCreating products...")
        
        products = [
            # Raw Materials
            {
                'product_code': 'RM-STEEL-001',
                'name': 'Steel Sheet - Grade A',
                'category': 'RAW_MATERIAL',
                'description': 'High-grade steel sheet for manufacturing',
                'unit_of_measure': 'KG',
                'unit_price': Decimal('5.50'),
                'reorder_point': 500,
                'safety_stock': 200,
                'lead_time_days': 10,
                'abc_classification': 'A'
            },
            {
                'product_code': 'RM-PLASTIC-001',
                'name': 'ABS Plastic Pellets',
                'category': 'RAW_MATERIAL',
                'description': 'Industrial grade ABS plastic',
                'unit_of_measure': 'KG',
                'unit_price': Decimal('3.20'),
                'reorder_point': 800,
                'safety_stock': 300,
                'lead_time_days': 7,
                'abc_classification': 'A'
            },
            # Components
            {
                'product_code': 'COMP-MOTOR-001',
                'name': 'Electric Motor - 1HP',
                'category': 'COMPONENT',
                'description': '1 Horsepower electric motor',
                'unit_of_measure': 'EA',
                'unit_price': Decimal('125.00'),
                'reorder_point': 50,
                'safety_stock': 20,
                'lead_time_days': 14,
                'abc_classification': 'B'
            },
            {
                'product_code': 'COMP-BEARING-001',
                'name': 'Ball Bearing - 6205',
                'category': 'COMPONENT',
                'description': 'Standard ball bearing 6205',
                'unit_of_measure': 'EA',
                'unit_price': Decimal('8.50'),
                'reorder_point': 200,
                'safety_stock': 100,
                'lead_time_days': 7,
                'abc_classification': 'B'
            },
            {
                'product_code': 'COMP-SENSOR-001',
                'name': 'Temperature Sensor',
                'category': 'COMPONENT',
                'description': 'Digital temperature sensor',
                'unit_of_measure': 'EA',
                'unit_price': Decimal('15.00'),
                'reorder_point': 100,
                'safety_stock': 50,
                'lead_time_days': 10,
                'abc_classification': 'B'
            },
            # Finished Goods
            {
                'product_code': 'FG-WIDGET-001',
                'name': 'Smart Widget Pro',
                'category': 'FINISHED_GOOD',
                'description': 'Premium smart widget with sensors',
                'unit_of_measure': 'EA',
                'unit_price': Decimal('299.99'),
                'reorder_point': 100,
                'safety_stock': 50,
                'lead_time_days': 5,
                'abc_classification': 'A'
            },
            {
                'product_code': 'FG-WIDGET-002',
                'name': 'Basic Widget',
                'category': 'FINISHED_GOOD',
                'description': 'Entry-level widget',
                'unit_of_measure': 'EA',
                'unit_price': Decimal('99.99'),
                'reorder_point': 200,
                'safety_stock': 100,
                'lead_time_days': 5,
                'abc_classification': 'B'
            },
            # Packaging
            {
                'product_code': 'PKG-BOX-001',
                'name': 'Shipping Box - Large',
                'category': 'PACKAGING',
                'description': 'Corrugated shipping box',
                'unit_of_measure': 'EA',
                'unit_price': Decimal('2.50'),
                'reorder_point': 500,
                'safety_stock': 200,
                'lead_time_days': 3,
                'abc_classification': 'C'
            },
            {
                'product_code': 'PKG-TAPE-001',
                'name': 'Packing Tape',
                'category': 'PACKAGING',
                'description': 'Heavy-duty packing tape',
                'unit_of_measure': 'EA',
                'unit_price': Decimal('4.99'),
                'reorder_point': 100,
                'safety_stock': 50,
                'lead_time_days': 3,
                'abc_classification': 'C'
            },
            # Consumables
            {
                'product_code': 'CONS-LUBRICANT-001',
                'name': 'Machine Lubricant',
                'category': 'CONSUMABLE',
                'description': 'Industrial machine lubricant',
                'unit_of_measure': 'L',
                'unit_price': Decimal('12.00'),
                'reorder_point': 50,
                'safety_stock': 20,
                'lead_time_days': 5,
                'abc_classification': 'C'
            }
        ]
        
        created = []
        for prod_data in products:
            product = Product.objects.create(**prod_data)
            created.append(product)
            self.stdout.write(f"  ✓ Created: {product}")
        
        return created

    def create_inventory_balances(self, products, warehouses):
        """Create initial inventory balances"""
        self.stdout.write("\nCreating inventory balances...")
        
        created = 0
        for product in products:
            for warehouse in warehouses:
                # Not all products in all warehouses
                if random.random() > 0.3:  # 70% chance of having stock
                    quantity = random.randint(
                        product.safety_stock,
                        product.reorder_point * 2
                    )
                    
                    balance = InventoryBalance.objects.create(
                        product=product,
                        warehouse=warehouse,
                        quantity_on_hand=quantity,
                        quantity_reserved=random.randint(0, int(quantity * 0.2))
                    )
                    created += 1
                    self.stdout.write(f"  ✓ {balance}")
        
        self.stdout.write(f"Created {created} inventory balances")

    def create_sample_scans(self, products, warehouses):
        """Create sample QR scan records"""
        self.stdout.write("\nCreating sample scans...")
        
        scan_types = ['IN', 'OUT', 'AUDIT']
        users = ['john.doe', 'jane.smith', 'mike.johnson', 'sarah.wilson']
        
        created = 0
        for _ in range(50):  # Create 50 sample scans
            product = random.choice(products)
            warehouse = random.choice(warehouses)
            scan_type = random.choice(scan_types)
            
            scan = InventoryScan.objects.create(
                product=product,
                warehouse=warehouse,
                scan_type=scan_type,
                quantity=random.randint(10, 100),
                scanned_by=random.choice(users),
                is_processed=random.choice([True, False])
            )
            created += 1
        
        self.stdout.write(f"Created {created} sample scans")