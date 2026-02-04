from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'warehouses', views.WarehouseViewSet, basename='warehouse')
router.register(r'balances', views.InventoryBalanceViewSet, basename='inventorybalance')
router.register(r'scans', views.InventoryScanViewSet, basename='inventoryscan')

urlpatterns = [
    path('', include(router.urls)),
]