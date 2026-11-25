from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('vendors', views.VendorViewSet, basename='vendor')

bank_list = views.VendorBankAccountViewSet.as_view({'get': 'list', 'post': 'create'})
bank_detail = views.VendorBankAccountViewSet.as_view({
    'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy',
})
bank_verify = views.VendorBankAccountViewSet.as_view({'post': 'verify'})

urlpatterns = [
    path('', include(router.urls)),
    path('vendors/<int:vendor_pk>/bank-accounts/', bank_list, name='vendor-bank-list'),
    path('vendors/<int:vendor_pk>/bank-accounts/<int:pk>/', bank_detail, name='vendor-bank-detail'),
    path('vendors/<int:vendor_pk>/bank-accounts/<int:pk>/verify/', bank_verify, name='vendor-bank-verify'),
]
