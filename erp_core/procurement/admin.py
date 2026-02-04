from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import Supplier, PurchaseOrder, PurchaseOrderItem, Shipment



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

class PurchaseOrderItemInline(admin.TabularInline):
    """Inline for PO items"""
    model = PurchaseOrderItem
    extra = 1
    fields = ['product', 'quantity_ordered', 'quantity_received', 'unit_price', 'line_total']
    readonly_fields = ['line_total']


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        'po_number',
        'supplier',
        'warehouse',
        'order_date',
        'expected_delivery_date',
        'status',
        'total_amount',
        'status_indicator',
        'overdue_indicator'
    ]
    list_filter = ['status', 'order_date', 'supplier', 'warehouse']
    search_fields = ['po_number', 'supplier__name', 'supplier__supplier_code']
    readonly_fields = ['subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at']
    inlines = [PurchaseOrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('po_number', 'supplier', 'warehouse', 'status')
        }),
        ('Dates', {
            'fields': ('order_date', 'expected_delivery_date', 'actual_delivery_date')
        }),
        ('Financial', {
            'fields': ('subtotal', 'tax_amount', 'total_amount', 'payment_terms')
        }),
        ('Additional Info', {
            'fields': ('notes', 'created_by', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['mark_as_confirmed', 'mark_as_received']
    
    def status_indicator(self, obj):
        """Visual status indicator"""
        colors = {
            'DRAFT': 'gray',
            'SUBMITTED': 'blue',
            'CONFIRMED': 'green',
            'SHIPPED': 'orange',
            'RECEIVED': 'darkgreen',
            'CANCELLED': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_indicator.short_description = 'Status'
    
    def overdue_indicator(self, obj):
        """Show if PO is overdue"""
        if obj.is_overdue:
            return format_html(
                '<span style="color: {}; font-weight: bold;">⚠️ OVERDUE</span>',
                'red'
            )
        return format_html('<span style="color: {};">✓</span>', 'green')
    overdue_indicator.short_description = 'Delivery Status'
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='CONFIRMED')
        self.message_user(request, f'{updated} PO(s) marked as confirmed.')
    mark_as_confirmed.short_description = 'Mark as Confirmed'
    
    def mark_as_received(self, request, queryset):
        updated = queryset.update(status='RECEIVED')
        self.message_user(request, f'{updated} PO(s) marked as received.')
    mark_as_received.short_description = 'Mark as Received'


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'purchase_order',
        'product',
        'quantity_ordered',
        'quantity_received',
        'quantity_pending',
        'unit_price',
        'line_total',
        'fulfillment_status'
    ]
    list_filter = ['purchase_order__status', 'product__category']
    search_fields = ['purchase_order__po_number', 'product__product_code', 'product__name']
    readonly_fields = ['line_total']
    
    def fulfillment_status(self, obj):
        """Visual fulfillment status"""
        if obj.is_fully_received:
         return format_html('<span style="color: {};">✓ Complete</span>', 'green')
        elif obj.quantity_received > 0:
         return format_html('<span style="color: {};">⏳ Partial</span>', 'orange')
        else:
         return format_html('<span style="color: {};">⏳ Pending</span>', 'gray')
    fulfillment_status.short_description = 'Fulfillment'


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = [
        'shipment_number',
        'purchase_order',
        'shipped_date',
        'expected_arrival_date',
        'actual_arrival_date',
        'status',
        'delay_days',
        'delay_indicator',
        'carrier'
    ]
    list_filter = ['status', 'carrier', 'shipped_date']
    search_fields = ['shipment_number', 'tracking_number', 'purchase_order__po_number']
    readonly_fields = ['delay_days', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Shipment Information', {
            'fields': ('shipment_number', 'purchase_order', 'status')
        }),
        ('Dates', {
            'fields': ('shipped_date', 'expected_arrival_date', 'actual_arrival_date')
        }),
        ('Carrier', {
            'fields': ('carrier', 'tracking_number')
        }),
        ('Delay Tracking', {
            'fields': ('delay_days', 'delay_reason')
        }),
        ('Additional', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['update_delays', 'mark_as_received']
    
    def delay_indicator(self, obj):
        """Visual delay indicator"""
        if obj.delay_days > 5:
            return format_html(
                '<span style="background-color: red; color: white; padding: 3px 8px; border-radius: 3px;">🔴 {} days</span>',
                obj.delay_days
            )
        elif obj.delay_days > 0:
            return format_html(
                '<span style="background-color: orange; color: white; padding: 3px 8px; border-radius: 3px;">🟠 {} days</span>',
                obj.delay_days
            )
        return format_html('<span style="color: green;">{}</span>', '✓ On Time')
    delay_indicator.short_description = 'Delay Status'
    
    def update_delays(self, request, queryset):
        count = 0
        for shipment in queryset:
            shipment.update_delay()
            count += 1
        self.message_user(request, f'Updated {count} shipment(s).')
    update_delays.short_description = 'Update delay status'
    
    def mark_as_received(self, request, queryset):
        updated = queryset.update(status='RECEIVED')
        self.message_user(request, f'{updated} shipment(s) marked as received.')
    mark_as_received.short_description = 'Mark as Received'