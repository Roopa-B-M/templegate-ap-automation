from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from purchase_orders.models import PurchaseOrder
from vendors.models import Vendor
from .models import Invoice, InvoiceLineItem, MatchResult, ValidationResult


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ('id', 'line_number', 'description', 'hsn_code', 'quantity', 'unit',
                  'unit_price', 'tax_rate', 'line_total', 'ocr_confidence')
        read_only_fields = ('id', 'line_total')


class ValidationResultSerializer(serializers.ModelSerializer):
    check_code_display = serializers.CharField(source='get_check_code_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ValidationResult
        fields = ('id', 'check_code', 'check_code_display', 'status', 'status_display',
                  'message', 'details', 'created_at')


class MatchResultSerializer(serializers.ModelSerializer):
    match_type_display = serializers.CharField(source='get_match_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = MatchResult
        fields = ('id', 'match_type', 'match_type_display', 'status', 'status_display',
                  'po', 'total_variance', 'details', 'created_at')


class VendorBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class InvoiceListSerializer(serializers.ModelSerializer):
    vendor = VendorBriefSerializer(read_only=True)
    vendor_name = serializers.CharField(source='vendor.name', read_only=True, default='')
    vendor_code = serializers.CharField(source='vendor.code', read_only=True, default='')
    po_number = serializers.CharField(source='po.po_number', read_only=True, default=None)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default=None)

    class Meta:
        model = Invoice
        fields = ('id', 'invoice_number', 'vendor', 'vendor_name', 'vendor_code', 'po',
                  'po_number', 'invoice_date', 'due_date', 'currency', 'subtotal',
                  'tax_amount', 'total_amount', 'status', 'status_display', 'source',
                  'source_display', 'file_name', 'file_type', 'ocr_status', 'ocr_confidence',
                  'erp_status', 'erp_reference',
                  'created_by_username', 'created_at')


class InvoiceDetailSerializer(InvoiceListSerializer):
    line_items = InvoiceLineItemSerializer(many=True, read_only=True)
    validation_results = ValidationResultSerializer(many=True, read_only=True)
    match_result = MatchResultSerializer(read_only=True)
    raw_ocr_text = serializers.CharField(read_only=True)
    ocr_error = serializers.CharField(read_only=True)
    extracted_data = serializers.JSONField(read_only=True)

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + (
            'page_count', 'raw_ocr_text', 'ocr_error', 'extracted_data',
            'line_items', 'validation_results', 'match_result',
            'approved_at', 'paid_at', 'updated_at',
        )


class InvoiceLineItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = ('description', 'hsn_code', 'quantity', 'unit', 'unit_price', 'tax_rate')

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError('Quantity must be greater than zero.')
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError('Unit price cannot be negative.')
        return value

    def validate_tax_rate(self, value):
        if value < 0 or value > 28:
            raise serializers.ValidationError('GST rate must be between 0 and 28 percent.')
        return value


class InvoiceReviewSerializer(serializers.Serializer):
    """Human review of OCR output: corrects fields and line items, re-links vendor/PO."""

    invoice_number = serializers.CharField(max_length=60)
    vendor_id = serializers.IntegerField()
    po_number = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    invoice_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False, default='INR')
    subtotal = serializers.DecimalField(max_digits=16, decimal_places=2, required=False, allow_null=True)
    tax_amount = serializers.DecimalField(max_digits=16, decimal_places=2, required=False, allow_null=True)
    total_amount = serializers.DecimalField(max_digits=16, decimal_places=2)
    line_items = InvoiceLineItemWriteSerializer(many=True)

    def validate_vendor_id(self, value):
        vendor = Vendor.objects.filter(pk=value).first()
        if not vendor:
            raise serializers.ValidationError('Vendor does not exist.')
        return value

    def validate(self, attrs):
        items = attrs.get('line_items') or []
        if not items:
            raise serializers.ValidationError({'line_items': 'At least one line item is required.'})
        vendor_id = attrs.get('vendor_id')
        number = (attrs.get('invoice_number') or '').strip()
        if vendor_id and number:
            qs = Invoice.objects.filter(vendor_id=vendor_id, invoice_number__iexact=number)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'invoice_number': 'This vendor already has an invoice with the same number.'})
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop('line_items')
        po_number = (validated_data.pop('po_number', '') or '').strip()

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.invoice_number = instance.invoice_number.strip()
        instance.po = None
        if po_number:
            instance.po = PurchaseOrder.objects.filter(po_number__iexact=po_number).first()
        instance.save()

        instance.line_items.all().delete()
        for idx, item in enumerate(items, start=1):
            InvoiceLineItem.objects.create(invoice=instance, line_number=idx, **item)
        instance.refresh_from_db()
        return instance
