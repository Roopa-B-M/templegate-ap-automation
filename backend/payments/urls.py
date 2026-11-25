from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .views import PaymentAdviceView, PaymentStatementReconcileView

router = DefaultRouter()
router.register('payments', views.PaymentViewSet, basename='payment')

urlpatterns = [
    path('', include(router.urls)),
    path('payments/<int:payment_id>/advice/', PaymentAdviceView.as_view(), name='payment-advice'),
    path('payments/reconcile-statement/', PaymentStatementReconcileView.as_view(),
         name='payment-reconcile-statement'),
]
