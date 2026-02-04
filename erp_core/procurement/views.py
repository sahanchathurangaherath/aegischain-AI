from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Supplier, PurchaseOrder, PurchaseOrderItem, Shipment
from .serializers import (
    SupplierSerializer, PurchaseOrderSerializer,
    PurchaseOrderItemSerializer, ShipmentSerializer,
    ShipmentListSerializer
)


class SupplierViewSet(viewsets.ModelViewSet):
    """API endpoint for Suppliers"""
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['supplier_type', 'risk_level', 'is_approved', 'is_active']
    search_fields = ['supplier_code', 'name', 'contact_person']
    ordering_fields = ['supplier_code', 'name', 'reliability_score']
    ordering = ['supplier_code']
    
    @action(detail=False, methods=['get'])
    def high_risk(self, request):
        """Get high-risk suppliers"""
        high_risk = self.get_queryset().filter(risk_level__in=['HIGH', 'CRITICAL'])
        serializer = self.get_serializer(high_risk, many=True)
        return Response(serializer.data)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """API endpoint for Purchase Orders"""
    queryset = PurchaseOrder.objects.select_related('supplier', 'warehouse').prefetch_related('items').all()
    serializer_class = PurchaseOrderSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'supplier', 'warehouse']
    search_fields = ['po_number', 'supplier__name']
    ordering_fields = ['order_date', 'expected_delivery_date', 'total_amount']
    ordering = ['-order_date']
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue purchase orders"""
        overdue_pos = [po for po in self.get_queryset() if po.is_overdue]
        serializer = self.get_serializer(overdue_pos, many=True)
        return Response(serializer.data)


class ShipmentViewSet(viewsets.ModelViewSet):
    """API endpoint for Shipments"""
    queryset = Shipment.objects.select_related('purchase_order').all()
    serializer_class = ShipmentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'carrier']
    search_fields = ['shipment_number', 'tracking_number', 'purchase_order__po_number']
    ordering_fields = ['expected_arrival_date', 'delay_days']
    ordering = ['-expected_arrival_date']
    
    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.action == 'list':
            return ShipmentListSerializer
        return ShipmentSerializer
    
    @action(detail=False, methods=['get'])
    def delayed(self, request):
        """Get delayed shipments"""
        delayed = self.get_queryset().filter(delay_days__gt=0)
        serializer = ShipmentListSerializer(delayed, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_all_delays(self, request):
        """Update delay status for all active shipments"""
        active_shipments = self.get_queryset().exclude(status__in=['RECEIVED', 'CANCELLED'])
        count = 0
        
        for shipment in active_shipments:
            shipment.update_delay()
            count += 1
        
        return Response({
            'success': True,
            'message': f'Updated {count} shipments'
        })