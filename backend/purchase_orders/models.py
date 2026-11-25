from decimal import Decimal

from django.conf import settings
from django.db import models


class PurchaseOrder(models.Model):
    """Purchase order raised on a vendor; the reference for invoice matching."""

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        CLOSED = 'CLOSED', 'Closed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    po_number = models.CharField(max_length=30, unique=True)
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.PROTECT, related_name='purchase_orders')
    po_date = models.DateField()
    currency = models.CharField(max_length=3, default='INR')
    subtotal = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='pos_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-po_date', '-id')

    def __str__(self):
        return f'{self.po_number} ({self.vendor.code})'

    def refresh_receipt_status(self):
        """Close the PO automatically once every line is fully received."""
        if self.status == self.Status.CANCELLED:
            return
        lines = self.lines.all()
        if lines and all(l.received_qty >= l.quantity for l in lines):
            self.status = self.Status.CLOSED
            self.save(update_fields=['status', 'updated_at'])


class POLine(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    line_number = models.PositiveIntegerField()
    item_code = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=255)
    hsn_code = models.CharField(max_length=10, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=10, default='NOS')
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    line_total = models.DecimalField(max_digits=16, decimal_places=2)
    received_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    class Meta:
        ordering = ('line_number',)
        unique_together = ('po', 'line_number')

    def __str__(self):
        return f'{self.po.po_number} line {self.line_number}: {self.description[:40]}'

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity * self.unit_price).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)


class GRN(models.Model):
    """Goods Receipt Note - proof of delivery used in 3-way matching."""

    grn_number = models.CharField(max_length=30, unique=True)
    po = models.ForeignKey('purchase_orders.PurchaseOrder', on_delete=models.PROTECT, related_name='grns')
    receipt_date = models.DateField()
    status = models.CharField(max_length=10, default='POSTED')
    remarks = models.TextField(blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='grns_received')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-receipt_date', '-id')

    def __str__(self):
        return f'{self.grn_number} ({self.po.po_number})'


class GRNLine(models.Model):
    grn = models.ForeignKey(GRN, on_delete=models.CASCADE, related_name='lines')
    po_line = models.ForeignKey('purchase_orders.POLine', on_delete=models.PROTECT, related_name='grn_lines')
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        ordering = ('id',)

    def __str__(self):
        return f'{self.grn.grn_number}: {self.po_line.description[:30]} x {self.quantity_received}'
