from django.core.exceptions import ValidationError
from rest_framework import serializers

from .models import Vendor, VendorBankAccount
from .services import is_valid_gstin, is_valid_ifsc, is_valid_pan


class VendorBankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorBankAccount
        fields = ('id', 'account_name', 'account_number', 'ifsc', 'bank_name',
                  'branch', 'upi_id', 'is_primary', 'is_verified', 'created_at')
        read_only_fields = ('id', 'is_verified', 'created_at')

    def validate_ifsc(self, value):
        if not is_valid_ifsc(value):
            raise ValidationError('Invalid IFSC code (expected e.g. HDFC0001234).')
        return value.upper()

    def validate_account_number(self, value):
        clean = value.strip()
        if not clean.isdigit() or not (6 <= len(clean) <= 20):
            raise ValidationError('Account number must be 6-20 digits.')
        return clean


class VendorSerializer(serializers.ModelSerializer):
    bank_accounts = VendorBankAccountSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default=None)
    approved_by_username = serializers.CharField(source='approved_by.username', read_only=True, default=None)
    invoice_count = serializers.IntegerField(read_only=True, default=0)
    total_billed = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True, default=0)

    class Meta:
        model = Vendor
        fields = ('id', 'code', 'name', 'legal_name', 'gstin', 'pan', 'email', 'phone',
                  'address_line1', 'address_line2', 'city', 'state', 'state_code', 'pincode',
                  'status', 'status_display', 'onboarding_notes', 'created_by_username',
                  'approved_by_username', 'approved_at', 'created_at', 'updated_at',
                  'bank_accounts', 'invoice_count', 'total_billed')
        read_only_fields = ('id', 'status', 'approved_at', 'created_at', 'updated_at')

    def validate_gstin(self, value):
        if not is_valid_gstin(value):
            raise ValidationError('Invalid GSTIN: format or check digit failed.')
        return value.strip().upper()

    def validate_pan(self, value):
        if value and not is_valid_pan(value):
            raise ValidationError('Invalid PAN format (expected ABCDE1234F).')
        return value.strip().upper()

    def validate_state_code(self, value):
        if value and not value.strip().isdigit():
            raise ValidationError('State code must be numeric (e.g. 27 for Maharashtra).')
        return value.strip()
