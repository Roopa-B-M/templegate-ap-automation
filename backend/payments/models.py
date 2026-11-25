from django.conf import settings
from django.db import models


class PaymentRequest(models.Model):
    """Payment request / execution for an approved invoice."""

    class Method(models.TextChoices):
        NEFT = 'NEFT', 'NEFT'
        RTGS = 'RTGS', 'RTGS'
        IMPS = 'IMPS', 'IMPS'
        CHEQUE = 'CHEQUE', 'Cheque'
        UPI = 'UPI', 'UPI'

    class Status(models.TextChoices):
        PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        PROCESSED = 'PROCESSED', 'Processed'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    payment_number = models.CharField(max_length=30, unique=True)
    invoice = models.OneToOneField('invoices.Invoice', on_delete=models.PROTECT, related_name='payment')
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.NEFT)
    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.PENDING_APPROVAL, db_index=True)
    scheduled_date = models.DateField(null=True, blank=True)
    processed_date = models.DateField(null=True, blank=True)
    bank_reference = models.CharField(max_length=40, blank=True, help_text='UTR / cheque number')
    failure_reason = models.TextField(blank=True)
    is_reconciled = models.BooleanField(default=False, db_index=True,
                                       help_text='True when a bank statement row matched this payment.')
    reconciled_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='payments_requested')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='payments_approved')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.payment_number} ({self.get_status_display()})'
