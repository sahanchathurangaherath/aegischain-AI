from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import SalesOrder, SalesOrderItem
from .serializers import SalesOrderSerializer, SalesOrderItemSerializer


class SalesOrderViewSet(viewsets.ModelViewSet):
    """API endpoint for Sales Orders"""
    queryset = SalesOrder.objects.select_related('warehouse').prefetch_related('items').all()
    serializer_class = SalesOrderSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'warehouse']
    search_fields = ['so_number', 'customer_name', 'customer_email']
    ordering_fields = ['order_date', 'required_date', 'total_amount']
    ordering = ['-order_date']
    
    @action(detail=False, methods=['get'])
    def urgent(self, request):
        """Get urgent orders"""
        urgent = self.get_queryset().filter(priority='URGENT')
        serializer = self.get_serializer(urgent, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def unfulfillable(self, request):
        """Get orders that cannot be fulfilled due to stock"""
        unfulfillable = [so for so in self.get_queryset() if not so.can_fulfill]
        serializer = self.get_serializer(unfulfillable, many=True)
        return Response(serializer.data)