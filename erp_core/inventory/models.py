from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from django.utils import timezone


from core.models import TimeStampedModel, ActiveModel


class Product(TimeStampedModel, ActiveModel):
    """
    Product Master Data
    Represents materials, components, or finished goods
    """
    
    CATEGORY_CHOICES = [
        ('RAW_MATERIAL', 'Raw Material'),
        ('COMPONENT', 'Component'),
        ('FINISHED_GOOD', 'Finished Good'),
        ('PACKAGING', 'Packaging Material'),
        ('CONSUMABLE', 'Consumable'),
    ]
    
    UOM_CHOICES = [
        ('EA', 'Each'),
        ('KG', 'Kilogram'),
        ('L', 'Liter'),
        ('M', 'Meter'),
        ('BOX', 'Box'),
        ('PALLET', 'Pallet'),
    ]
    
    # Basic Information
    product_code = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Unique product identifier (e.g., P-001, MAT-RAW-001)"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    
    # Specifications
    unit_of_measure = models.CharField(max_length=10, choices=UOM_CHOICES)
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Inventory Parameters
    reorder_point = models.IntegerField(
        default=100,
        help_text="Stock level that triggers reorder"
    )
    safety_stock = models.IntegerField(
        default=50,
        help_text="Minimum stock level to maintain"
    )
    lead_time_days = models.IntegerField(
        default=7,
        help_text="Standard procurement lead time"
    )
    
    # Classification
    abc_classification = models.CharField(
        max_length=1,
        choices=[('A', 'Class A'), ('B', 'Class B'), ('C', 'Class C')],
        default='B',
        help_text="ABC analysis classification"
    )
    
    # Additional Info
    barcode = models.CharField(max_length=100, blank=True, null=True)
    hs_code = models.CharField(max_length=20, blank=True, help_text="Harmonized System Code")
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['product_code']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        indexes = [
            models.Index(fields=['product_code']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"{self.product_code} - {self.name}"
    
    @property
    def is_below_reorder_point(self):
        """Check if current stock is below reorder point"""
        total_stock = sum(
            balance.quantity_on_hand 
            for balance in self.inventory_balances.all()  
        )
        return total_stock <= self.reorder_point




class Warehouse(TimeStampedModel, ActiveModel):
    """
    Warehouse/Storage Location Master Data
    """
    
    TYPE_CHOICES = [
        ('MAIN', 'Main Warehouse'),
        ('REGIONAL', 'Regional Warehouse'),
        ('TRANSIT', 'Transit Warehouse'),
        ('QUARANTINE', 'Quarantine Area'),
        ('RETURNS', 'Returns Area'),
    ]
    
    warehouse_code = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Unique warehouse identifier (e.g., WH-MAIN-01)"
    )
    name = models.CharField(max_length=200)
    warehouse_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # Location
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    
    # Contact
    manager_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    
    # Capacity
    total_capacity = models.IntegerField(
        help_text="Total capacity in cubic meters"
    )
    current_utilization = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Current utilization percentage"
    )
    
    class Meta:
        ordering = ['warehouse_code']
        verbose_name = 'Warehouse'
        verbose_name_plural = 'Warehouses'
    
    def __str__(self):
        return f"{self.warehouse_code} - {self.name}"
    
    def update_utilization(self):
        """Calculate and update current utilization"""
        # This would be calculated based on actual inventory
        # Placeholder for now
        pass





class InventoryBalance(TimeStampedModel):
    """
    Current inventory balance by product and warehouse
    This is the "single source of truth" for stock levels
    """
    
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='inventory_balances'
    )
    warehouse = models.ForeignKey(
        'Warehouse',
        on_delete=models.CASCADE,
        related_name='inventory_balances'
    )
    
    # Quantities
    quantity_on_hand = models.IntegerField(
        default=0,
        help_text="Physical stock in warehouse"
    )
    quantity_reserved = models.IntegerField(
        default=0,
        help_text="Stock reserved for sales orders"
    )
    quantity_in_transit = models.IntegerField(
        default=0,
        help_text="Stock being transferred"
    )
    
    # Calculated fields
    quantity_available = models.IntegerField(
        default=0,
        help_text="Available for sale = On Hand - Reserved"
    )
    
    # Last physical count
    last_physical_count = models.IntegerField(null=True, blank=True)
    last_count_date = models.DateTimeField(null=True, blank=True)
    variance = models.IntegerField(
        default=0,
        help_text="Difference between system and physical count"
    )
    
    class Meta:
        unique_together = ('product', 'warehouse')
        ordering = ['warehouse', 'product']
        verbose_name = 'Inventory Balance'
        verbose_name_plural = 'Inventory Balances'
        indexes = [
            models.Index(fields=['product', 'warehouse']),
            models.Index(fields=['quantity_available']),
        ]
    
    def __str__(self):
        return f"{self.product.product_code} @ {self.warehouse.warehouse_code}: {self.quantity_on_hand}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate quantity_available before saving"""
        self.quantity_available = self.quantity_on_hand - self.quantity_reserved
        super().save(*args, **kwargs)
    
    def update_variance(self, physical_count):
        """Update variance after physical count"""
        self.last_physical_count = physical_count
        self.last_count_date = timezone.now()
        self.variance = physical_count - self.quantity_on_hand
        self.save()
    
    @property
    def is_below_safety_stock(self):
        """Check if stock is below safety stock level"""
        return self.quantity_available < self.product.safety_stock
    
    @property
    def is_below_reorder_point(self):
        """Check if stock is below reorder point"""
        return self.quantity_available < self.product.reorder_point
    



class InventoryScan(TimeStampedModel):
    """
    QR Code Scan Events for Physical Inventory Tracking
    Every physical movement is recorded here
    """
    
    SCAN_TYPE_CHOICES = [
        ('IN', 'Goods Receipt'),
        ('OUT', 'Goods Issue'),
        ('TRANSFER', 'Transfer'),
        ('AUDIT', 'Physical Count'),
        ('ADJUSTMENT', 'Adjustment'),
    ]
    
    # Unique scan identifier
    scan_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    
    # What was scanned
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='scans'
    )
    warehouse = models.ForeignKey(
        'Warehouse',
        on_delete=models.CASCADE,
        related_name='scans'
    )
    
    # Scan details
    scan_type = models.CharField(max_length=20, choices=SCAN_TYPE_CHOICES)
    quantity = models.IntegerField()
    
    # Who and when
    scanned_by = models.CharField(
        max_length=100,
        help_text="User who performed the scan"
    )
    scanned_at = models.DateTimeField(auto_now_add=True)
    
    # Reference
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="PO number, SO number, Transfer number, etc."
    )
    
    # Location details
    bin_location = models.CharField(
        max_length=50,
        blank=True,
        help_text="Specific bin/rack location"
    )
    
    # Additional info
    notes = models.TextField(blank=True)
    
    # Processing status
    is_processed = models.BooleanField(
        default=False,
        help_text="Has this scan been processed to update inventory?"
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-scanned_at']
        verbose_name = 'Inventory Scan'
        verbose_name_plural = 'Inventory Scans'
        indexes = [
            models.Index(fields=['scanned_at']),
            models.Index(fields=['product', 'warehouse']),
            models.Index(fields=['scan_type']),
            models.Index(fields=['is_processed']),
        ]
    
    def __str__(self):
        return f"{self.scan_type} - {self.product.product_code} x {self.quantity} @ {self.warehouse.warehouse_code}"
    
    def process_scan(self):
        """
        Process this scan and update inventory balance
        This will be called automatically or manually
        """
        if self.is_processed:
            return  # Already processed
        
        # Get or create inventory balance
        balance, created = InventoryBalance.objects.get_or_create(
            product=self.product,
            warehouse=self.warehouse,
            defaults={'quantity_on_hand': 0}
        )
        
        # Update quantity based on scan type
        if self.scan_type == 'IN':
            balance.quantity_on_hand += self.quantity
        elif self.scan_type == 'OUT':
            balance.quantity_on_hand -= self.quantity
        elif self.scan_type == 'AUDIT':
            # Physical count - update variance
            balance.update_variance(self.quantity)
        elif self.scan_type == 'ADJUSTMENT':
            balance.quantity_on_hand = self.quantity
        
        balance.save()
        
        # Mark as processed
        self.is_processed = True
        self.processed_at = timezone.now()
        self.save()