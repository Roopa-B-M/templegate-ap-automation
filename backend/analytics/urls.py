from django.urls import path

from . import views

urlpatterns = [
    path('analytics/dashboard/', views.dashboard, name='analytics-dashboard'),
    path('analytics/vendors/', views.vendor_analytics, name='analytics-vendors'),
    path('reports/ap-aging/', views.ap_aging_report, name='report-ap-aging'),
    path('reports/invoice-status/', views.invoice_status_report, name='report-invoice-status'),
    path('reports/exceptions/', views.exception_report, name='report-exceptions'),
    path('reports/gst/', views.gst_report, name='report-gst'),
    path('reports/audit-logs/', views.audit_log_report, name='report-audit-logs'),
]
