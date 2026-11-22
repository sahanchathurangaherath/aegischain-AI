from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


def health_check(request):
    """Health check endpoint verifying database connectivity."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "healthy", "database": "connected"}, status=200)
    except Exception as exc:
        return JsonResponse({"status": "unhealthy", "error": str(exc)}, status=503)


urlpatterns = [
    # Healthcheck
    path('health/', health_check, name='health-check'),

    # Admin
    path('admin/', admin.site.urls),

    # OpenAPI 3 Schema & Documentation (drf-spectacular)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='schema-swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='schema-redoc'),

    # API Endpoints
    path('api/inventory/', include('inventory.urls')),
    path('api/procurement/', include('procurement.urls')),
    path('api/sales/', include('sales.urls')),

    # DRF Browsable API authentication
    path('api-auth/', include('rest_framework.urls')),
]