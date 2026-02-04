from rest_framework import serializers
from .models import SalesOrder, SalesOrderItem


class SalesOrderItemSerializer(serializers.ModelSerializer):
    """Serializer for SO Items"""
    
    product_code = serializers.CharField(source='product.product_code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    can_fulfill = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = SalesOrderItem
        fields = [
            'id', 'product', 'product_code', 'product_name',
            'quantity_ordered', 'quantity_fulfilled', 'unit_price',
            'discount_percent', 'line_total', 'can_fulfill', 'notes'
        ]
        read_only_fields = ['line_total', 'can_fulfill']


class SalesOrderSerializer(serializers.ModelSerializer):
    """Serializer for Sales Orders"""
    
    warehouse_code = serializers.CharField(source='warehouse.warehouse_code', read_only=True)
    items = SalesOrderItemSerializer(many=True, read_only=True)
    can_fulfill = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = SalesOrder
        fields = [
            'id', 'so_number', 'customer_name', 'customer_email',
            'customer_phone', 'warehouse', 'warehouse_code',
            'shipping_address', 'shipping_city', 'shipping_state',
            'shipping_country', 'shipping_postal_code',
            'order_date', 'required_date', 'promised_date',
            'shipped_date', 'delivered_date', 'status', 'priority',
            'subtotal', 'tax_amount', 'shipping_cost', 'total_amount',
            'can_fulfill', 'notes', 'created_by', 'items',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'subtotal', 'tax_amount', 'total_amount', 'can_fulfill',
            'created_at', 'updated_at'
        ]