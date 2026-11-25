"""ERP / accounting integration models.

GLAccountMapping keeps the ledger-side configuration (which expense, GST and
payable accounts a purchase voucher posts to) and can be overridden per
vendor. ERPSyncLog records every attempt to post an invoice voucher to the
configured ERP connector, success or failure.
"""
from django.conf import settings
from django.db import models


class GLAccountMapping(models.Model):
    """Ledger account mapping used when a purchase voucher is posted to the ERP.

    One row may be marked as the default (vendor is empty); a vendor-specific
    row overrides the default for that vendor only.
    """

    name = models.CharField(max_length=100)
    vendor = models.OneToOneField('vendors.Vendor', null=True, blank=True,
                                  on_delete=models.CASCADE, related_name='gl_account_mapping',
                                  help_text='Leave empty to make this the default mapping.')
    expense_account = models.CharField(max_length=60, help_text='Purchase / expense ledger (e.g. "Purchase Account").')
    cgst_account = models.CharField(max_length=60, blank=True, help_text='Input CGST ledger (intra-state supply).')
    sgst_account = models.CharField(max_length=60, blank=True, help_text='Input SGST ledger (intra-state supply).')
    igst_account = models.CharField(max_length=60, blank=True, help_text='Input IGST ledger (inter-state supply).')
    payable_account = models.CharField(max_length=60, default='Accounts Payable',
                                       help_text='Creditor / payable ledger for the vendor.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint(fields=('name',), name='uniq_gl_mapping_name'),
            models.CheckConstraint(
                check=(models.Q(vendor__isnull=True) | models.Q(vendor__isnull=False)),
                name='gl_mapping_vendor_optional',
            ),
        ]

    def __str__(self):
        target = self.vendor.name if self.vendor else 'Default'
        return f'{self.name} ({target})'


class ERPSyncLog(models.Model):
    """One attempt to post an approved/paid invoice into the ERP."""

    class Status(models.TextChoices):
        NOT_SYNCED = 'NOT_SYNCED', 'Not Synced'
        SYNCED = 'SYNCED', 'Synced'
        FAILED = 'FAILED', 'Failed'

    class Format(models.TextChoices):
        TALLY_XML = 'TALLY_XML', 'Tally XML voucher'
        CSV = 'CSV', 'Generic CSV'
        JSON = 'JSON', 'Generic JSON'
        SINGLE_POST = 'SINGLE_POST', 'Single voucher post'

    invoice = models.ForeignKey('invoices.Invoice', on_delete=models.CASCADE, related_name='erp_sync_logs')
    connector = models.CharField(max_length=40, help_text='ERPConnector implementation name.')
    format = models.CharField(max_length=15, choices=Format.choices, default=Format.SINGLE_POST)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NOT_SYNCED, db_index=True)
    erp_reference = models.CharField(max_length=60, blank=True, help_text='Voucher number / ERP document reference.')
    error = models.TextField(blank=True)
    payload_preview = models.JSONField(default=dict, blank=True,
                                       help_text='Small summary of what was sent (no full document).')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='erp_sync_logs')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=['status', 'created_at'])]

    def __str__(self):
        return f'{self.invoice_id}: {self.connector} {self.status} {self.erp_reference or self.error[:40]}'
