from rest_framework import serializers
from .models import Product, Warehouse, InventoryBalance, InventoryScan


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model"""
    
    stock_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'product_code', 'name', 'description', 'category',
            'unit_of_measure', 'unit_price', 'reorder_point', 'safety_stock',
            'lead_time_days', 'abc_classification', 'barcode', 'is_active',
            'stock_status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_stock_status(self, obj):
        """Get stock status across all warehouses"""
        total_stock = sum(
            balance.quantity_on_hand 
            for balance in obj.inventory_balances.all()
        )
        
        if total_stock <= obj.safety_stock:
            return 'critical'
        elif total_stock <= obj.reorder_point:
            return 'low'
        return 'ok'


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for product lists"""
    
    class Meta:
        model = Product
        fields = ['id', 'product_code', 'name', 'category', 'unit_price', 'is_active']


class WarehouseSerializer(serializers.ModelSerializer):
    """Serializer for Warehouse model"""
    
    class Meta:
        model = Warehouse
        fields = [
            'id', 'warehouse_code', 'name', 'warehouse_type',
            'address', 'city', 'state', 'country', 'postal_code',
            'manager_name', 'phone', 'email', 'total_capacity',
            'current_utilization', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class InventoryBalanceSerializer(serializers.ModelSerializer):
    """Serializer for Inventory Balance"""
    
    product_code = serializers.CharField(source='product.product_code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.warehouse_code', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    stock_health = serializers.SerializerMethodField()
    
    class Meta:
        model = InventoryBalance
        fields = [
            'id', 'product', 'product_code', 'product_name',
            'warehouse', 'warehouse_code', 'warehouse_name',
            'quantity_on_hand', 'quantity_reserved', 'quantity_in_transit',
            'quantity_available', 'last_physical_count', 'last_count_date',
            'variance', 'stock_health', 'created_at', 'updated_at'
        ]
        read_only_fields = ['quantity_available', 'created_at', 'updated_at']
    
    def get_stock_health(self, obj):
        """Get stock health status"""
        if obj.is_below_safety_stock:
            return 'critical'
        elif obj.is_below_reorder_point:
            return 'low'
        return 'ok'


class InventoryScanSerializer(serializers.ModelSerializer):
    """Serializer for QR Scan records"""
    
    product_code = serializers.CharField(source='product.product_code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.warehouse_code', read_only=True)
    
    class Meta:
        model = InventoryScan
        fields = [
            'id', 'scan_id', 'product', 'product_code', 'product_name',
            'warehouse', 'warehouse_code', 'scan_type', 'quantity',
            'scanned_by', 'scanned_at', 'reference_number', 'bin_location',
            'notes', 'is_processed', 'processed_at', 'created_at'
        ]
        read_only_fields = ['scan_id', 'scanned_at', 'is_processed', 'processed_at', 'created_at']


class QRScanCreateSerializer(serializers.Serializer):
    """Serializer for creating QR scans (simplified input)"""
    
    product_code = serializers.CharField(max_length=50)
    warehouse_code = serializers.CharField(max_length=50)
    scan_type = serializers.ChoiceField(choices=['IN', 'OUT', 'TRANSFER', 'AUDIT', 'ADJUSTMENT'])
    quantity = serializers.IntegerField(min_value=1)
    scanned_by = serializers.CharField(max_length=100)
    reference_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    bin_location = serializers.CharField(max_length=50, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    auto_process = serializers.BooleanField(default=True)
    
    def validate_product_code(self, value):
        """Validate product exists"""
        try:
            Product.objects.get(product_code=value, is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError(f"Product with code '{value}' not found or inactive")
        return value
    
    def validate_warehouse_code(self, value):
        """Validate warehouse exists"""
        try:
            Warehouse.objects.get(warehouse_code=value, is_active=True)
        except Warehouse.DoesNotExist:
            raise serializers.ValidationError(f"Warehouse with code '{value}' not found or inactive")
        return value
    
    def create(self, validated_data):
        """Create scan record and optionally process it"""
        product = Product.objects.get(product_code=validated_data['product_code'])
        warehouse = Warehouse.objects.get(warehouse_code=validated_data['warehouse_code'])
        auto_process = validated_data.pop('auto_process', True)
        
        # Remove codes from validated_data
        validated_data.pop('product_code')
        validated_data.pop('warehouse_code')
        
        scan = InventoryScan.objects.create(
            product=product,
            warehouse=warehouse,
            **validated_data
        )
        
        # Auto-process if requested
        if auto_process:
            scan.process_scan()
        
        return scan