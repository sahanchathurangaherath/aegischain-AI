from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Warehouse, InventoryBalance, InventoryScan


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'product_code', 
        'name', 
        'category', 
        'unit_price',
        'reorder_point',
        'safety_stock',
        'is_active',
        'stock_status'
    ]
    list_filter = ['category', 'abc_classification', 'is_active']
    search_fields = ['product_code', 'name', 'barcode']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('product_code', 'name', 'description', 'category')
        }),
        ('Specifications', {
            'fields': ('unit_of_measure', 'unit_price', 'barcode', 'hs_code')
        }),
        ('Inventory Parameters', {
            'fields': ('reorder_point', 'safety_stock', 'lead_time_days', 'abc_classification')
        }),
        ('Status', {
            'fields': ('is_active', 'notes', 'created_at', 'updated_at')
        }),
    )
    
    def stock_status(self, obj):
        """Display stock status with color coding"""
        if obj.is_below_reorder_point:
            return format_html(
                '<span style="color: red;">{}</span>',
                '⚠️ Below Reorder Point'
            )
        return format_html(
            '<span style="color: green;">{}</span>',
            '✓ OK'
        )
    
    stock_status.short_description = 'Stock Status'


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = [
        'warehouse_code',
        'name',
        'warehouse_type',
        'city',
        'manager_name',
        'is_active'
    ]
    list_filter = ['warehouse_type', 'is_active', 'country']
    search_fields = ['warehouse_code', 'name', 'city']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('warehouse_code', 'name', 'warehouse_type')
        }),
        ('Location', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code')
        }),
        ('Contact', {
            'fields': ('manager_name', 'phone', 'email')
        }),
        ('Capacity', {
            'fields': ('total_capacity', 'current_utilization')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )


@admin.register(InventoryBalance)
class InventoryBalanceAdmin(admin.ModelAdmin):
    list_display = [
        'product',
        'warehouse',
        'quantity_on_hand',
        'quantity_reserved',
        'quantity_available',
        'variance',
        'stock_health'
    ]
    list_filter = ['warehouse', 'product__category']
    search_fields = ['product__product_code', 'product__name', 'warehouse__warehouse_code']
    readonly_fields = ['quantity_available', 'created_at', 'updated_at']
    
    def stock_health(self, obj):
        """Visual indicator of stock health"""
        if obj.is_below_safety_stock:
            return format_html(
                '<span style="background-color: red; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
                '🔴 CRITICAL'
            )
        elif obj.is_below_reorder_point:
            return format_html(
                '<span style="background-color: orange; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
                '🟠 LOW'
            )
        return format_html(
            '<span style="background-color: green; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            '🟢 OK'
        )
    
    stock_health.short_description = 'Health'


@admin.register(InventoryScan)
class InventoryScanAdmin(admin.ModelAdmin):
    list_display = [
        'scan_id',
        'product',
        'warehouse',
        'scan_type',
        'quantity',
        'scanned_by',
        'scanned_at',
        'is_processed',
        'process_status'
    ]
    list_filter = ['scan_type', 'is_processed', 'scanned_at']
    search_fields = ['scan_id', 'product__product_code', 'reference_number']
    readonly_fields = ['scan_id', 'scanned_at', 'processed_at', 'created_at']
    
    actions = ['process_selected_scans']
    
    def process_status(self, obj):
        """Visual indicator of processing status"""
        if obj.is_processed:
            return format_html(
                '<span style="color: green;">{}</span>',
                '✓ Processed'
            )
        return format_html(
            '<span style="color: orange;">{}</span>',
            '⏳ Pending'
        )
    
    process_status.short_description = 'Status'
    
    def process_selected_scans(self, request, queryset):
        """Admin action to process multiple scans"""
        count = 0
        for scan in queryset.filter(is_processed=False):
            scan.process_scan()
            count += 1
        
        self.message_user(request, f'{count} scans processed successfully.')
    
    process_selected_scans.short_description = 'Process selected scans'