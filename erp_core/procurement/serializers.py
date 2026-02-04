from rest_framework import serializers
from .models import Supplier, PurchaseOrder, PurchaseOrderItem, Shipment


class SupplierSerializer(serializers.ModelSerializer):
    """Serializer for Supplier model"""
    
    risk_indicator = serializers.SerializerMethodField()
    
    class Meta:
        model = Supplier
        fields = [
            'id', 'supplier_code', 'name', 'supplier_type',
            'contact_person', 'email', 'phone', 'website',
            'address', 'city', 'state', 'country', 'postal_code',
            'payment_terms', 'lead_time_days', 'minimum_order_value',
            'reliability_score', 'on_time_delivery_rate', 'quality_rating',
            'risk_level', 'risk_indicator', 'is_approved', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_risk_indicator(self, obj):
        """Get risk indicator"""
        return {
            'level': obj.risk_level,
            'reliability': obj.reliability_score,
            'on_time_rate': obj.on_time_delivery_rate
        }


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    """Serializer for PO Items"""
    
    product_code = serializers.CharField(source='product.product_code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id', 'product', 'product_code', 'product_name',
            'quantity_ordered', 'quantity_received', 'unit_price',
            'line_total', 'expected_delivery_date', 'notes'
        ]
        read_only_fields = ['line_total']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """Serializer for Purchase Orders"""
    
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.warehouse_code', read_only=True)
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'po_number', 'supplier', 'supplier_name',
            'warehouse', 'warehouse_code', 'order_date',
            'expected_delivery_date', 'actual_delivery_date',
            'status', 'subtotal', 'tax_amount', 'total_amount',
            'payment_terms', 'notes', 'created_by', 'items',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['subtotal', 'tax_amount', 'total_amount', 'created_at', 'updated_at']


class ShipmentSerializer(serializers.ModelSerializer):
    """Serializer for Shipments"""
    
    po_number = serializers.CharField(source='purchase_order.po_number', read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'shipment_number', 'purchase_order', 'po_number',
            'shipped_date', 'expected_arrival_date', 'actual_arrival_date',
            'status', 'carrier', 'tracking_number', 'delay_days',
            'delay_reason', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['delay_days', 'created_at', 'updated_at']


class ShipmentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for shipment lists"""
    
    po_number = serializers.CharField(source='purchase_order.po_number', read_only=True)
    is_delayed = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Shipment
        fields = [
            'id', 'shipment_number', 'po_number', 'status',
            'expected_arrival_date', 'delay_days', 'is_delayed', 'carrier'
        ]