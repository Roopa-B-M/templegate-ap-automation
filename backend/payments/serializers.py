from rest_framework import serializers

from .models import PaymentRequest


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True, default='')
    vendor_name = serializers.CharField(source='invoice.vendor.name', read_only=True, default='')
    invoice_total = serializers.DecimalField(source='invoice.total_amount',
                                             max_digits=16, decimal_places=2, read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True, default=None)
    approved_by_username = serializers.CharField(source='approved_by.username', read_only=True, default=None)

    class Meta:
        model = PaymentRequest
        fields = ('id', 'payment_number', 'invoice', 'invoice_number', 'vendor_name',
                  'invoice_total', 'amount', 'method', 'method_display', 'status', 'status_display',
                  'scheduled_date', 'processed_date', 'bank_reference', 'failure_reason',
                  'is_reconciled', 'reconciled_at',
                  'requested_by_username', 'approved_by_username', 'created_at')
        read_only_fields = ('id', 'payment_number', 'amount', 'status', 'bank_reference',
                           'processed_date', 'is_reconciled', 'reconciled_at', 'created_at')
