from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from core.models import TimeStampedModel, UUIDModel, ActiveModel

class Supplier(TimeStampedModel, ActiveModel):
    """
    Supplier Master Data
    """
    
    SUPPLIER_TYPE_CHOICES = [
        ('MANUFACTURER', 'Manufacturer'),
        ('DISTRIBUTOR', 'Distributor'),
        ('WHOLESALER', 'Wholesaler'),
        ('SERVICE', 'Service Provider'),
    ]
    
    PAYMENT_TERM_CHOICES = [
        ('NET_30', 'Net 30 Days'),
        ('NET_60', 'Net 60 Days'),
        ('COD', 'Cash on Delivery'),
        ('ADVANCE', 'Advance Payment'),
    ]
    
    # Basic Information
    supplier_code = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Unique supplier identifier (e.g., SUP-001)"
    )
    name = models.CharField(max_length=200)
    supplier_type = models.CharField(max_length=20, choices=SUPPLIER_TYPE_CHOICES)
    
    # Contact Information
    contact_person = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    website = models.URLField(blank=True)
    
    # Address
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    
    # Business Terms
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERM_CHOICES)
    lead_time_days = models.IntegerField(
        default=14,
        help_text="Standard lead time in days"
    )
    minimum_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    # Performance Metrics
    reliability_score = models.FloatField(
        default=100.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Supplier reliability score (0-100)"
    )
    on_time_delivery_rate = models.FloatField(
        default=100.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Percentage of on-time deliveries"
    )
    quality_rating = models.FloatField(
        default=5.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)],
        help_text="Quality rating (1-5 stars)"
    )
    
    # Risk Assessment
    risk_level = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low Risk'),
            ('MEDIUM', 'Medium Risk'),
            ('HIGH', 'High Risk'),
            ('CRITICAL', 'Critical Risk'),
        ],
        default='MEDIUM'
    )
    
    # Tax & Legal
    tax_id = models.CharField(max_length=50, blank=True)
    is_approved = models.BooleanField(default=False)
    approval_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['supplier_code']
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'
    
    def __str__(self):
        return f"{self.supplier_code} - {self.name}"
    
    def update_reliability_score(self):
        """Calculate reliability based on historical performance"""
        # This will be implemented when we have shipment data
        pass


class PurchaseOrder(TimeStampedModel):
    """
    Purchase Order Header
    Represents orders placed with suppliers
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted to Supplier'),
        ('CONFIRMED', 'Confirmed by Supplier'),
        ('SHIPPED', 'Shipped'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Fully Received'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Header Information
    po_number = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Purchase Order Number (e.g., PO-2024-001)"
    )
    supplier = models.ForeignKey(
        'Supplier',
        on_delete=models.PROTECT,
        related_name='purchase_orders'
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        help_text="Destination warehouse"
    )
    
    # Dates
    order_date = models.DateField(default=timezone.now)
    expected_delivery_date = models.DateField()
    actual_delivery_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Financial
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=0
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # Additional Info
    payment_terms = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.CharField(max_length=100, default='system')
    
    class Meta:
        ordering = ['-order_date', '-po_number']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'
        indexes = [
            models.Index(fields=['-order_date']),
            models.Index(fields=['status']),
            models.Index(fields=['supplier']),
        ]
    
    def __str__(self):
        return f"{self.po_number} - {self.supplier.supplier_code}"
    
    def calculate_totals(self):
        """Calculate subtotal and total from line items"""
        items = self.items.all()
        self.subtotal = sum(item.line_total for item in items)
        self.tax_amount = self.subtotal * Decimal('0.10')  # 10% tax
        self.total_amount = self.subtotal + self.tax_amount
        self.save()
    
    @property
    def is_overdue(self):
        """Check if delivery is overdue"""
        if self.status in ['RECEIVED', 'CANCELLED']:
            return False
        return timezone.now().date() > self.expected_delivery_date
    
    @property
    def days_until_delivery(self):
        """Days until expected delivery"""
        delta = self.expected_delivery_date - timezone.now().date()
        return delta.days


class PurchaseOrderItem(TimeStampedModel):
    """
    Purchase Order Line Items
    Individual products in a purchase order
    """
    
    purchase_order = models.ForeignKey(
        'PurchaseOrder',
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.PROTECT,
        related_name='purchase_order_items'
    )
    
    # Quantities
    quantity_ordered = models.IntegerField(
        validators=[MinValueValidator(1)]
    )
    quantity_received = models.IntegerField(default=0)
    
    # Pricing
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # Additional Info
    expected_delivery_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['purchase_order', 'id']
        verbose_name = 'Purchase Order Item'
        verbose_name_plural = 'Purchase Order Items'
    
    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.product.product_code} x {self.quantity_ordered}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate line total"""
        self.line_total = self.quantity_ordered * self.unit_price
        super().save(*args, **kwargs)
        
        # Update PO totals
        if self.purchase_order_id:
            self.purchase_order.calculate_totals()
    
    @property
    def quantity_pending(self):
        """Quantity still to be received"""
        return self.quantity_ordered - self.quantity_received
    
    @property
    def is_fully_received(self):
        """Check if item is fully received"""
        return self.quantity_received >= self.quantity_ordered


class Shipment(TimeStampedModel):
    """
    Shipment Tracking
    Tracks deliveries from suppliers
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Pickup'),
        ('IN_TRANSIT', 'In Transit'),
        ('DELAYED', 'Delayed'),
        ('ARRIVED', 'Arrived at Warehouse'),
        ('RECEIVED', 'Received and Verified'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Shipment Information
    shipment_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Tracking number or shipment ID"
    )
    purchase_order = models.ForeignKey(
        'PurchaseOrder',
        on_delete=models.CASCADE,
        related_name='shipments'
    )
    
    # Dates
    shipped_date = models.DateField(null=True, blank=True)
    expected_arrival_date = models.DateField()
    actual_arrival_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # Carrier Information
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    
    # Delay Tracking
    delay_days = models.IntegerField(
        default=0,
        help_text="Number of days delayed"
    )
    delay_reason = models.TextField(blank=True)
    
    # Additional Info
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-expected_arrival_date']
        verbose_name = 'Shipment'
        verbose_name_plural = 'Shipments'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['expected_arrival_date']),
        ]
    
    def __str__(self):
        return f"{self.shipment_number} - {self.purchase_order.po_number}"
    
    def update_delay(self):
        """Calculate delay if shipment is late"""
        if self.actual_arrival_date:
            # Use actual arrival
            delta = self.actual_arrival_date - self.expected_arrival_date
            self.delay_days = max(0, delta.days)
        elif self.status not in ['RECEIVED', 'CANCELLED']:
            # Not yet received - check if overdue
            today = timezone.now().date()
            if today > self.expected_arrival_date:
                delta = today - self.expected_arrival_date
                self.delay_days = delta.days
                if self.status != 'DELAYED':
                    self.status = 'DELAYED'
        
        self.save()
    
    @property
    def is_delayed(self):
        """Check if shipment is delayed"""
        return self.delay_days > 0
    
    @property
    def days_in_transit(self):
        """Calculate days in transit"""
        if self.shipped_date:
            end_date = self.actual_arrival_date or timezone.now().date()
            delta = end_date - self.shipped_date
            return delta.days
        return 0
