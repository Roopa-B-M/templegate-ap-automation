from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum
from rest_framework import serializers

from vendors.models import Vendor
from .models import GRN, GRNLine, POLine, PurchaseOrder


class VendorBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class POLineSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    received_qty = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = POLine
        fields = ('id', 'line_number', 'item_code', 'description', 'hsn_code', 'quantity',
                  'unit', 'unit_price', 'tax_rate', 'line_total', 'received_qty')
        read_only_fields = ('id', 'line_total', 'received_qty')
        extra_kwargs = {'line_number': {'required': False, 'allow_null': True}}

    def validate_quantity(self, value):
        if value <= 0:
            raise ValidationError('Quantity must be greater than zero.')
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise ValidationError('Unit price cannot be negative.')
        return value

    def validate_tax_rate(self, value):
        if value < 0 or value > 28:
            raise ValidationError('GST rate must be between 0 and 28 percent.')
        return value


class PurchaseOrderSerializer(serializers.ModelSerializer):
    vendor = VendorBriefSerializer(read_only=True)
    vendor_id = serializers.PrimaryKeyRelatedField(queryset=Vendor.objects.all(),
                                                   source='vendor', write_only=True)
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    vendor_code = serializers.CharField(source='vendor.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lines = POLineSerializer(many=True)
    invoice_count = serializers.IntegerField(read_only=True, default=0)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default=None)

    class Meta:
        model = PurchaseOrder
        fields = ('id', 'po_number', 'vendor', 'vendor_id', 'vendor_name', 'vendor_code', 'po_date',
                  'currency', 'subtotal', 'tax_amount', 'total_amount', 'status', 'status_display',
                  'notes', 'lines', 'invoice_count', 'created_by_username', 'created_at')
        read_only_fields = ('id', 'subtotal', 'tax_amount', 'total_amount', 'created_at')

    def validate_po_number(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        lines = attrs.get('lines')
        if self.instance is None and not lines:
            raise ValidationError({'lines': 'At least one line item is required.'})
        return attrs

    @staticmethod
    def _save_lines(po, lines_data):
        subtotal = Decimal('0')
        tax = Decimal('0')
        for idx, line in enumerate(lines_data, start=1):
            qty = line['quantity']
            price = line['unit_price']
            rate = line['tax_rate']
            gross = (qty * price).quantize(Decimal('0.01'))
            subtotal += gross
            tax += (gross * rate / Decimal('100')).quantize(Decimal('0.01'))
            POLine.objects.create(
                po=po,
                line_number=line.get('line_number') or idx,
                item_code=line.get('item_code', ''),
                description=line['description'],
                hsn_code=line.get('hsn_code', ''),
                quantity=qty,
                unit=line.get('unit', 'NOS'),
                unit_price=price,
                tax_rate=rate,
                line_total=gross,
            )
        po.subtotal = subtotal.quantize(Decimal('0.01'))
        po.tax_amount = tax.quantize(Decimal('0.01'))
        po.total_amount = (po.subtotal + po.tax_amount).quantize(Decimal('0.01'))
        po.save(update_fields=['subtotal', 'tax_amount', 'total_amount', 'updated_at'])

    def create(self, validated_data):
        lines_data = validated_data.pop('lines')
        po = PurchaseOrder.objects.create(**validated_data)
        self._save_lines(po, lines_data)
        return po


class GRNLinePoSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    line_number = serializers.IntegerField(read_only=True)
    description = serializers.CharField(read_only=True)


class POBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    po_number = serializers.CharField(read_only=True)


class GRNLineSerializer(serializers.ModelSerializer):
    po_line = GRNLinePoSerializer(read_only=True)
    po_line_id = serializers.PrimaryKeyRelatedField(queryset=POLine.objects.all(),
                                                    source='po_line', write_only=True)
    po_line_detail = POLineSerializer(source='po_line', read_only=True)

    class Meta:
        model = GRNLine
        fields = ('id', 'po_line', 'po_line_id', 'po_line_detail', 'quantity_received')
        read_only_fields = ('id',)


class GRNSerializer(serializers.ModelSerializer):
    po = POBriefSerializer(read_only=True)
    po_id = serializers.PrimaryKeyRelatedField(queryset=PurchaseOrder.objects.all(),
                                               source='po', write_only=True)
    po_number = serializers.CharField(source='po.po_number', read_only=True)
    vendor_name = serializers.CharField(source='po.vendor.name', read_only=True)
    lines = GRNLineSerializer(many=True)
    received_by_username = serializers.CharField(source='received_by.username', read_only=True, default=None)

    class Meta:
        model = GRN
        fields = ('id', 'grn_number', 'po', 'po_id', 'po_number', 'vendor_name', 'receipt_date', 'status',
                  'remarks', 'lines', 'received_by_username', 'created_at')
        read_only_fields = ('id', 'status', 'created_at')

    def validate_grn_number(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        lines = attrs.get('lines') or []
        if not lines:
            raise ValidationError({'lines': 'At least one received line is required.'})
        po = attrs.get('po')
        if po is None:
            raise ValidationError({'po': 'Purchase order is required.'})
        if po.status == PurchaseOrder.Status.CANCELLED:
            raise ValidationError({'po': 'Cannot record receipt against a cancelled PO.'})
        po_lines = {line.id: line for line in po.lines.all()}
        for line in lines:
            po_line = line.get('po_line')
            if po_line is None or po_line.id not in po_lines:
                raise ValidationError({'lines': 'Every GRN line must reference a POLine of the selected PO.'})
            qty = line.get('quantity_received')
            if qty is None or qty <= 0:
                raise ValidationError({'lines': 'quantity_received must be greater than zero.'})
            current = po_lines[po_line.id]
            if current.received_qty + qty > current.quantity:
                raise ValidationError({
                    'lines': f'Cannot receive {qty} of "{current.description}": PO quantity '
                             f'{current.quantity}, already received {current.received_qty}.'
                })
        return attrs

    def create(self, validated_data):
        lines_data = validated_data.pop('lines')
        grn = GRN.objects.create(status='POSTED', **validated_data)
        for line in lines_data:
            GRNLine.objects.create(grn=grn, po_line=line['po_line'],
                                   quantity_received=line['quantity_received'])
            po_line = line['po_line']
            po_line.received_qty = po_line.grn_lines.aggregate(
                total=Sum('quantity_received'))['total'] or Decimal('0')
            po_line.save(update_fields=['received_qty'])
        grn.po.refresh_receipt_status()
        return grn
