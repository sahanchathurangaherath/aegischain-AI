from django.contrib import admin
from django.utils.html import format_html
from .models import SalesOrder, SalesOrderItem


class SalesOrderItemInline(admin.TabularInline):
    """Inline for SO items"""
    model = SalesOrderItem
    extra = 1
    fields = ['product', 'quantity_ordered', 'quantity_fulfilled', 'unit_price', 'discount_percent', 'line_total']
    readonly_fields = ['line_total']


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = [
        'so_number',
        'customer_name',
        'warehouse',
        'order_date',
        'required_date',
        'status',
        'priority',
        'total_amount',
        'status_indicator',
        'fulfillment_indicator'
    ]
    list_filter = ['status', 'priority', 'order_date', 'warehouse']
    search_fields = ['so_number', 'customer_name', 'customer_email']
    readonly_fields = ['subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at']
    inlines = [SalesOrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('so_number', 'warehouse', 'status', 'priority')
        }),
        ('Customer', {
            'fields': ('customer_name', 'customer_email', 'customer_phone')
        }),
        ('Shipping Address', {
            'fields': ('shipping_address', 'shipping_city', 'shipping_state', 'shipping_country', 'shipping_postal_code')
        }),
        ('Dates', {
            'fields': ('order_date', 'required_date', 'promised_date', 'shipped_date', 'delivered_date')
        }),
        ('Financial', {
            'fields': ('subtotal', 'tax_amount', 'shipping_cost', 'total_amount')
        }),
        ('Additional', {
            'fields': ('notes', 'created_by', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['mark_as_confirmed', 'mark_as_shipped']
    
    def status_indicator(self, obj):
        """Visual status indicator"""
        colors = {
            'DRAFT': 'gray',
            'CONFIRMED': 'blue',
            'PROCESSING': 'orange',
            'PACKED': 'purple',
            'SHIPPED': 'green',
            'DELIVERED': 'darkgreen',
            'CANCELLED': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_indicator.short_description = 'Status'
    
    def fulfillment_indicator(self, obj):
      if obj.can_fulfill:
        return format_html(
            '<span style="color: {};">{}</span>',
            'green',
            '✓ Can Fulfill'
        )
      return format_html(
        '<span style="color: {};">{}</span>',
        'red',
        '⚠️ Insufficient Stock'
    )
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='CONFIRMED')
        self.message_user(request, f'{updated} order(s) confirmed.')
    mark_as_confirmed.short_description = 'Confirm Orders'
    
    def mark_as_shipped(self, request, queryset):
        from django.utils import timezone
        for order in queryset:
            order.status = 'SHIPPED'
            order.shipped_date = timezone.now().date()
            order.save()
        self.message_user(request, f'{queryset.count()} order(s) marked as shipped.')
    mark_as_shipped.short_description = 'Mark as Shipped'


@admin.register(SalesOrderItem)
class SalesOrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'sales_order',
        'product',
        'quantity_ordered',
        'quantity_fulfilled',
        'quantity_pending',
        'unit_price',
        'discount_percent',
        'line_total',
        'stock_check'
    ]
    list_filter = ['sales_order__status', 'product__category']
    search_fields = ['sales_order__so_number', 'product__product_code', 'product__name']
    readonly_fields = ['line_total']
    
    def stock_check(self, obj):
      if obj.can_fulfill:
        return format_html(
            '<span style="color: {};">{}</span>',
            'green',
            '✓ Available'
        )
      return format_html(
        '<span style="color: {};">{}</span>',
        'red',
        '⚠️ Low Stock'
    )