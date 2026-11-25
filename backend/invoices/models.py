from django.conf import settings
from django.db import models


class Invoice(models.Model):
    """Central AP document: captured file, OCR output, validated data, workflow state."""

    class Status(models.TextChoices):
        UPLOADED = 'UPLOADED', 'Uploaded'
        EXTRACTED = 'EXTRACTED', 'OCR Extracted'
        VALIDATED = 'VALIDATED', 'Validated'
        MATCHED = 'MATCHED', 'Matched'
        MATCH_EXCEPTION = 'MATCH_EXCEPTION', 'Match Exception'
        EXCEPTION = 'EXCEPTION', 'Validation Exception'
        PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        PAYMENT_REQUESTED = 'PAYMENT_REQUESTED', 'Payment Requested'
        SCHEDULED = 'SCHEDULED', 'Payment Scheduled'
        PAID = 'PAID', 'Paid'
        PAYMENT_FAILED = 'PAYMENT_FAILED', 'Payment Failed'
        ON_HOLD = 'ON_HOLD', 'On Hold'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class OcrStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    class Source(models.TextChoices):
        UPLOAD = 'UPLOAD', 'Manual Upload'
        EMAIL = 'EMAIL', 'Email Ingestion'
        MANUAL = 'MANUAL', 'Manual Entry'

    class ErpStatus(models.TextChoices):
        NOT_SYNCED = 'NOT_SYNCED', 'Not Synced'
        SYNCED = 'SYNCED', 'Synced'
        FAILED = 'FAILED', 'Failed'

    invoice_number = models.CharField(max_length=60, blank=True, db_index=True)
    vendor = models.ForeignKey('vendors.Vendor', null=True, blank=True,
                               on_delete=models.PROTECT, related_name='invoices')
    po = models.ForeignKey('purchase_orders.PurchaseOrder', null=True, blank=True,
                           on_delete=models.PROTECT, related_name='invoices')
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default='INR')
    subtotal = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    source = models.CharField(max_length=10, choices=Source.choices, default=Source.UPLOAD)
    file = models.FileField(upload_to='invoices/%Y/%m/', max_length=300)
    file_name = models.CharField(max_length=255, blank=True)
    file_type = models.CharField(max_length=5, blank=True)  # PDF / JPG / PNG / TIFF
    page_count = models.PositiveIntegerField(default=1)

    ocr_status = models.CharField(max_length=12, choices=OcrStatus.choices,
                                  default=OcrStatus.PENDING, db_index=True)
    ocr_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    ocr_error = models.TextField(blank=True)
    raw_ocr_text = models.TextField(blank=True)
    extracted_data = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED, db_index=True)

    erp_status = models.CharField(max_length=12, choices=ErpStatus.choices,
                                  default=ErpStatus.NOT_SYNCED, db_index=True,
                                  help_text='ERP/accounting posting state (see accounting app).')
    erp_reference = models.CharField(max_length=60, blank=True,
                                     help_text='ERP voucher / document reference returned by the connector.')

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='invoices_created')
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=['status', 'created_at'])]

    def __str__(self):
        return f'{self.invoice_number or f"Unprocessed #{self.pk}"} ({self.get_status_display()})'


class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    line_number = models.PositiveIntegerField()
    description = models.CharField(max_length=255)
    hsn_code = models.CharField(max_length=10, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=10, default='NOS')
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=16, decimal_places=2)
    ocr_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ('line_number',)
        unique_together = ('invoice', 'line_number')

    def __str__(self):
        return f'#{self.invoice_id} L{self.line_number}: {self.description[:40]}'

    def save(self, *args, **kwargs):
        from decimal import Decimal
        self.line_total = (self.quantity * self.unit_price).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)


class ValidationResult(models.Model):
    """Outcome of one rule of the invoice validation engine."""

    class CheckCode(models.TextChoices):
        MANDATORY_FIELDS = 'MANDATORY_FIELDS', 'Mandatory fields'
        DUPLICATE_INVOICE = 'DUPLICATE_INVOICE', 'Duplicate invoice'
        GST_VALIDATION = 'GST_VALIDATION', 'GST / tax validation'
        AMOUNT_VALIDATION = 'AMOUNT_VALIDATION', 'Amount validation'
        TAX_CALCULATION = 'TAX_CALCULATION', 'Tax calculation'
        VENDOR_MASTER_VALIDATION = 'VENDOR_MASTER_VALIDATION', 'Vendor master'
        ADMIN_OVERRIDE = 'ADMIN_OVERRIDE', 'Admin override'

    class Status(models.TextChoices):
        PASS = 'PASS', 'Pass'
        WARN = 'WARN', 'Warning'
        FAIL = 'FAIL', 'Fail'

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='validation_results')
    check_code = models.CharField(max_length=30, choices=CheckCode.choices)
    status = models.CharField(max_length=6, choices=Status.choices)
    message = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('id',)

    def __str__(self):
        return f'{self.invoice_id}: {self.check_code} {self.status}'


class MatchResult(models.Model):
    """Outcome of the PO matching engine (2-way / 3-way)."""

    class MatchType(models.TextChoices):
        TWO_WAY = 'TWO_WAY', '2-Way Match (PO vs Invoice)'
        THREE_WAY = 'THREE_WAY', '3-Way Match (PO vs GRN vs Invoice)'
        NOT_APPLICABLE = 'NOT_APPLICABLE', 'Non-PO Invoice'

    class Status(models.TextChoices):
        MATCHED = 'MATCHED', 'Matched'
        MISMATCH = 'MISMATCH', 'Mismatch'
        NOT_APPLICABLE = 'NOT_APPLICABLE', 'Not applicable'

    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='match_result')
    po = models.ForeignKey('purchase_orders.PurchaseOrder', null=True, blank=True, on_delete=models.SET_NULL)
    match_type = models.CharField(max_length=15, choices=MatchType.choices)
    status = models.CharField(max_length=15, choices=Status.choices)
    total_variance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.invoice_id}: {self.match_type} {self.status}'
