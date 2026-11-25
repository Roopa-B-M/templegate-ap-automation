from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('approvals', views.ApprovalTaskViewSet, basename='approval')
router.register('workflow/matrix', views.ApprovalMatrixViewSet, basename='approval-matrix')

urlpatterns = [
    path('', include(router.urls)),
]
