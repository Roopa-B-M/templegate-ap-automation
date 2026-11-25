from rest_framework import serializers

from .models import ERPSyncLog, GLAccountMapping


class GLAccountMappingSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True, default=None)

    class Meta:
        model = GLAccountMapping
        fields = ('id', 'name', 'vendor', 'vendor_name', 'expense_account', 'cgst_account',
                  'sgst_account', 'igst_account', 'payable_account', 'is_active',
                  'created_at', 'updated_at')

    def validate(self, attrs):
        if self.instance is None and GLAccountMapping.objects.filter(
                vendor=attrs.get('vendor')).exists():
            raise serializers.ValidationError(
                'This vendor already has a GL account mapping (one per vendor).')
        return attrs


class ERPSyncLogSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True, default='')
    vendor_name = serializers.CharField(source='invoice.vendor.name', read_only=True, default='')
    invoice_total = serializers.DecimalField(source='invoice.total_amount', max_digits=16,
                                             decimal_places=2, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    format_display = serializers.CharField(source='get_format_display', read_only=True)
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True, default=None)

    class Meta:
        model = ERPSyncLog
        fields = ('id', 'invoice', 'invoice_number', 'vendor_name', 'invoice_total',
                  'connector', 'format', 'format_display', 'status', 'status_display',
                  'erp_reference', 'error', 'payload_preview', 'requested_by_username',
                  'created_at', 'posted_at')
        read_only_fields = fields
