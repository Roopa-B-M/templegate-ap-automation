"""Root URL configuration for the TempleGate AP Automation API."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls_auth')),
    path('api/', include('accounts.urls')),
    path('api/', include('vendors.urls')),
    path('api/', include('purchase_orders.urls')),
    path('api/', include('invoices.urls')),
    path('api/', include('workflow.urls')),
    path('api/', include('payments.urls')),
    path('api/accounting/', include('accounting.urls')),
    path('api/', include('analytics.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
