from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'sales-orders', views.SalesOrderViewSet, basename='salesorder')

urlpatterns = [
    path('', include(router.urls)),
]