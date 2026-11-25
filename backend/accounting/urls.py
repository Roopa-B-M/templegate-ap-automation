from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('mappings', views.GLAccountMappingViewSet, basename='gl-mapping')
router.register('sync-logs', views.ERPSyncLogViewSet, basename='erp-sync-log')
router.register('', views.AccountingOperationsViewSet, basename='accounting')

urlpatterns = [
    path('retry/<int:log_id>/', views.AccountingRetryView.as_view(), name='erp-retry'),
    path('', include(router.urls)),
]
