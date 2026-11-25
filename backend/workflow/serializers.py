from rest_framework import serializers

from .models import ApprovalMatrix, ApprovalTask


class ApprovalTaskInvoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    invoice_number = serializers.CharField()
    vendor_name = serializers.SerializerMethodField()
    total_amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    invoice_date = serializers.DateField()

    def get_vendor_name(self, obj):
        return obj.vendor.name if obj.vendor else ''


class ApprovalTaskSerializer(serializers.ModelSerializer):
    invoice = ApprovalTaskInvoiceSerializer(read_only=True)
    approver_username = serializers.CharField(source='approver.username', read_only=True, default=None)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    approver_role_display = serializers.CharField(source='get_approver_role_display', read_only=True)

    class Meta:
        model = ApprovalTask
        fields = ('id', 'invoice', 'level', 'approver', 'approver_username', 'approver_role',
                  'approver_role_display', 'status', 'status_display', 'is_active', 'is_parallel',
                  'escalation_hours', 'due_at', 'escalated', 'reminder_count', 'comments',
                  'approved_at', 'created_at')
        read_only_fields = fields


class ApprovalMatrixSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalMatrix
        fields = ('id', 'name', 'level', 'min_amount', 'max_amount', 'approver_role',
                  'is_parallel', 'escalation_hours', 'active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        min_amount = attrs.get('min_amount', getattr(self.instance, 'min_amount', 0) or 0)
        max_amount = attrs.get('max_amount', getattr(self.instance, 'max_amount', None))
        if max_amount is not None and min_amount > max_amount:
            raise serializers.ValidationError('min_amount cannot exceed max_amount.')
        return attrs
