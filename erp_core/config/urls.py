from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# API Documentation
schema_view = get_schema_view(
    openapi.Info(
        title="AegisChain API",
        default_version='v1',
        description="AI-powered Supply Chain  API",
        terms_of_service="https://www.aegischain.com/terms/",
        contact=openapi.Contact(email="api@aegischain.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API Endpoints
    path('api/inventory/', include('inventory.urls')),
    path('api/procurement/', include('procurement.urls')),
    path('api/sales/', include('sales.urls')),
    
    # DRF Browsable API authentication
    path('api-auth/', include('rest_framework.urls')),
]