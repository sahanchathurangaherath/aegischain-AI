from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel, ActiveModel


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