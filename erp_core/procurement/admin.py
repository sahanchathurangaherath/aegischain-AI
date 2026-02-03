from django.contrib import admin
from django.utils.html import format_html
from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = [
        'supplier_code',
        'name',
        'supplier_type',
        'reliability_score',
        'on_time_delivery_rate',
        'risk_indicator',
        'is_active'
    ]
    list_filter = ['supplier_type', 'risk_level', 'is_active', 'is_approved']
    search_fields = ['supplier_code', 'name', 'contact_person']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('supplier_code', 'name', 'supplier_type')
        }),
        ('Contact', {
            'fields': ('contact_person', 'email', 'phone', 'website')
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code')
        }),
        ('Business Terms', {
            'fields': ('payment_terms', 'lead_time_days', 'minimum_order_value')
        }),
        ('Performance', {
            'fields': ('reliability_score', 'on_time_delivery_rate', 'quality_rating', 'risk_level')
        }),
        ('Approval', {
            'fields': ('is_approved', 'approval_date', 'tax_id')
        }),
        ('Status', {
            'fields': ('is_active', 'notes', 'created_at', 'updated_at')
        }),
    )
    
    def risk_indicator(self, obj):
        """Visual risk level indicator"""
        colors = {
            'LOW': 'green',
            'MEDIUM': 'orange',
            'HIGH': 'red',
            'CRITICAL': 'darkred'
        }
        color = colors.get(obj.risk_level, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_risk_level_display()
        )
    
    risk_indicator.short_description = 'Risk'