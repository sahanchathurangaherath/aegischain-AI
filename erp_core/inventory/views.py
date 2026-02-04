from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Product, Warehouse, InventoryBalance, InventoryScan
from .serializers import (
    ProductSerializer, ProductListSerializer,
    WarehouseSerializer, InventoryBalanceSerializer,
    InventoryScanSerializer, QRScanCreateSerializer
)


class ProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Products
    
    list: Get all products
    retrieve: Get a specific product
    create: Create a new product
    update: Update a product
    destroy: Delete a product
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'abc_classification', 'is_active']
    search_fields = ['product_code', 'name', 'barcode']
    ordering_fields = ['product_code', 'name', 'unit_price', 'created_at']
    ordering = ['product_code']
    
    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer
    
    @action(detail=True, methods=['get'])
    def inventory(self, request, pk=None):
        """Get inventory balances for this product across all warehouses"""
        product = self.get_object()
        balances = product.inventory_balances.all()
        serializer = InventoryBalanceSerializer(balances, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def low_stock(self, request, pk=None):
        """Check if product is low stock"""
        product = self.get_object()
        low_stock_balances = [
            balance for balance in product.inventory_balances.all()
            if balance.is_below_reorder_point
        ]
        serializer = InventoryBalanceSerializer(low_stock_balances, many=True)
        return Response({
            'is_low_stock': len(low_stock_balances) > 0,
            'warehouses': serializer.data
        })


class WarehouseViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Warehouses
    """
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['warehouse_type', 'is_active', 'city', 'state']
    search_fields = ['warehouse_code', 'name', 'city']
    ordering_fields = ['warehouse_code', 'name', 'city']
    ordering = ['warehouse_code']
    
    @action(detail=True, methods=['get'])
    def inventory(self, request, pk=None):
        """Get all inventory in this warehouse"""
        warehouse = self.get_object()
        balances = warehouse.inventory_balances.all()
        serializer = InventoryBalanceSerializer(balances, many=True)
        return Response(serializer.data)


class InventoryBalanceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Inventory Balances
    """
    queryset = InventoryBalance.objects.select_related('product', 'warehouse').all()
    serializer_class = InventoryBalanceSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product', 'warehouse']
    search_fields = ['product__product_code', 'product__name', 'warehouse__warehouse_code']
    ordering_fields = ['quantity_on_hand', 'quantity_available', 'updated_at']
    ordering = ['-updated_at']
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get all low stock items"""
        low_stock = [
            balance for balance in self.get_queryset()
            if balance.is_below_reorder_point
        ]
        serializer = self.get_serializer(low_stock, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def critical(self, request):
        """Get all critical stock items (below safety stock)"""
        critical = [
            balance for balance in self.get_queryset()
            if balance.is_below_safety_stock
        ]
        serializer = self.get_serializer(critical, many=True)
        return Response(serializer.data)


class InventoryScanViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Inventory Scans (QR Code tracking)
    """
    queryset = InventoryScan.objects.select_related('product', 'warehouse').all()
    serializer_class = InventoryScanSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['scan_type', 'is_processed', 'product', 'warehouse']
    search_fields = ['scan_id', 'product__product_code', 'reference_number', 'scanned_by']
    ordering_fields = ['scanned_at', 'created_at']
    ordering = ['-scanned_at']
    
    @action(detail=False, methods=['post'])
    def scan(self, request):
        """
        Process a QR scan
        
        POST /api/inventory/scans/scan/
        {
            "product_code": "P-001",
            "warehouse_code": "WH-01",
            "scan_type": "IN",
            "quantity": 100,
            "scanned_by": "john.doe",
            "reference_number": "PO-2024-001",
            "bin_location": "A-01-05",
            "notes": "Received from supplier",
            "auto_process": true
        }
        """
        serializer = QRScanCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            scan = serializer.save()
            
            # Get the inventory balance after processing
            balance = InventoryBalance.objects.filter(
                product=scan.product,
                warehouse=scan.warehouse
            ).first()
            
            return Response({
                'success': True,
                'message': 'Scan processed successfully',
                'scan': InventoryScanSerializer(scan).data,
                'inventory_balance': InventoryBalanceSerializer(balance).data if balance else None
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Process a pending scan"""
        scan = self.get_object()
        
        if scan.is_processed:
            return Response({
                'success': False,
                'message': 'Scan already processed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        scan.process_scan()
        
        return Response({
            'success': True,
            'message': 'Scan processed',
            'scan': InventoryScanSerializer(scan).data
        })
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending (unprocessed) scans"""
        pending_scans = self.get_queryset().filter(is_processed=False)
        serializer = self.get_serializer(pending_scans, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def process_all_pending(self, request):
        """Process all pending scans"""
        pending_scans = self.get_queryset().filter(is_processed=False)
        count = 0
        
        for scan in pending_scans:
            scan.process_scan()
            count += 1
        
        return Response({
            'success': True,
            'message': f'Processed {count} scans'
        })