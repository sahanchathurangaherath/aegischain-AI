
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from core.models import TimeStampedModel



class SalesOrder(TimeStampedModel):
    """
    Sales Order Header
    Customer orders for products
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('CONFIRMED', 'Confirmed'),
        ('PROCESSING', 'Processing'),
        ('PACKED', 'Packed'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low Priority'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High Priority'),
        ('URGENT', 'Urgent'),
    ]
    
    # Header Information
    so_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Sales Order Number (e.g., SO-2024-001)"
    )
    
    # Customer Information
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    
    # Shipping Address
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_country = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    
    # Warehouse
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.PROTECT,
        related_name='sales_orders',
        help_text="Fulfillment warehouse"
    )
    
    # Dates
    order_date = models.DateField(default=timezone.now)
    required_date = models.DateField(
        help_text="Customer requested delivery date"
    )
    promised_date = models.DateField(
        null=True, blank=True,
        help_text="Promised delivery date to customer"
    )
    shipped_date = models.DateField(null=True, blank=True)
    delivered_date = models.DateField(null=True, blank=True)
    
    # Status & Priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='NORMAL')
    
    # Financial
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Additional Info
    notes = models.TextField(blank=True)
    created_by = models.CharField(max_length=100, default='system')
    
    class Meta:
        ordering = ['-order_date', '-so_number']
        verbose_name = 'Sales Order'
        verbose_name_plural = 'Sales Orders'
        indexes = [
            models.Index(fields=['-order_date']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
        ]
    
    def __str__(self):
        return f"{self.so_number} - {self.customer_name}"
    
    def calculate_totals(self):
        """Calculate subtotal and total from line items"""
        items = self.items.all()
        self.subtotal = sum(item.line_total for item in items)
        self.tax_amount = self.subtotal * Decimal('0.10')  # 10% tax
        self.total_amount = self.subtotal + self.tax_amount + self.shipping_cost
        self.save()
    
    @property
    def is_overdue(self):
        """Check if order is overdue"""
        if self.status in ['DELIVERED', 'CANCELLED']:
            return False
        return timezone.now().date() > self.required_date
    
    @property
    def can_fulfill(self):
        """Check if all items can be fulfilled from inventory"""
        for item in self.items.all():
            if not item.can_fulfill:
                return False
        return True

    def confirm_order(self):
        """Confirm a DRAFT order and atomically reserve stock for all line items."""
        from inventory.models import InventoryBalance

        with transaction.atomic():
            if self.status != 'DRAFT':
                raise ValidationError(f"Only DRAFT orders can be confirmed (current: {self.status}).")

            items = list(self.items.select_related('product').all())
            if not items:
                raise ValidationError("Cannot confirm a sales order with no line items.")

            for item in items:
                balance = InventoryBalance.objects.select_for_update().filter(
                    product=item.product,
                    warehouse=self.warehouse,
                ).first()
                if not balance or balance.quantity_available < item.quantity_pending:
                    raise ValidationError(
                        f"Insufficient available stock for {item.product.product_code} at {self.warehouse.warehouse_code}."
                    )
                balance.quantity_reserved += item.quantity_pending
                balance.save()

            self.status = 'CONFIRMED'
            self.save(update_fields=['status', 'updated_at'])

    def fulfill_order(self, scanned_by: str = 'system'):
        """Ship a confirmed/packed order, deducting reserved and on-hand stock and logging OUT scans."""
        from inventory.models import InventoryBalance, InventoryScan

        with transaction.atomic():
            if self.status not in ('CONFIRMED', 'PROCESSING', 'PACKED'):
                raise ValidationError(f"Cannot fulfill order in '{self.status}' status.")

            for item in self.items.select_related('product').all():
                qty = item.quantity_pending
                if qty <= 0:
                    continue

                balance = InventoryBalance.objects.select_for_update().get(
                    product=item.product,
                    warehouse=self.warehouse,
                )
                balance.quantity_reserved = max(0, balance.quantity_reserved - qty)
                balance.quantity_on_hand -= qty
                balance.save()

                item.quantity_fulfilled = item.quantity_ordered
                item.save(update_fields=['quantity_fulfilled', 'updated_at'])

                InventoryScan.objects.create(
                    product=item.product,
                    warehouse=self.warehouse,
                    scan_type='OUT',
                    quantity=qty,
                    scanned_by=scanned_by,
                    reference_number=self.so_number,
                    notes=f"Auto-recorded from fulfillment of {self.so_number}",
                    is_processed=True,
                    processed_at=timezone.now(),
                )

            self.status = 'SHIPPED'
            self.shipped_date = timezone.now().date()
            self.save(update_fields=['status', 'shipped_date', 'updated_at'])


class SalesOrderItem(TimeStampedModel):
    """
    Sales Order Line Items
    Individual products in a sales order
    """
    
    sales_order = models.ForeignKey(
        'SalesOrder',
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.PROTECT,
        related_name='sales_order_items'
    )
    
    # Quantities
    quantity_ordered = models.IntegerField(
        validators=[MinValueValidator(1)]
    )
    quantity_fulfilled = models.IntegerField(default=0)
    
    # Pricing
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # Additional Info
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['sales_order', 'id']
        verbose_name = 'Sales Order Item'
        verbose_name_plural = 'Sales Order Items'
    
    def __str__(self):
        return f"{self.sales_order.so_number} - {self.product.product_code} x {self.quantity_ordered}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate line total with discount"""
        gross_amount = self.quantity_ordered * self.unit_price
        discount_amount = gross_amount * (Decimal(str(self.discount_percent)) / Decimal('100'))
        self.line_total = gross_amount - discount_amount
        super().save(*args, **kwargs)
        
        # Update SO totals
        if self.sales_order_id:
            self.sales_order.calculate_totals()
    
    @property
    def quantity_pending(self):
        """Quantity still to be fulfilled"""
        return self.quantity_ordered - self.quantity_fulfilled
    
    @property
    def is_fully_fulfilled(self):
        """Check if item is fully fulfilled"""
        return self.quantity_fulfilled >= self.quantity_ordered
    
    @property
    def can_fulfill(self):
        """Check if enough inventory available"""
        from inventory.models import InventoryBalance
        
        try:
            balance = InventoryBalance.objects.get(
                product=self.product,
                warehouse=self.sales_order.warehouse
            )
            return balance.quantity_available >= self.quantity_pending
        except InventoryBalance.DoesNotExist:
            return False


