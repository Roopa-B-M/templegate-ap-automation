from django.conf import settings
from django.db import models

from core.models import AuditLog  # noqa: F401  (ensures core app models are loaded first)


class Vendor(models.Model):
    """Vendor master record with an onboarding approval workflow."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        BLOCKED = 'BLOCKED', 'Blocked'

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=200, blank=True)
    gstin = models.CharField(max_length=15, db_index=True)
    pan = models.CharField(max_length=10, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    state_code = models.CharField(max_length=2, blank=True)
    pincode = models.CharField(max_length=6, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    onboarding_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='vendors_created')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='vendors_approved')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        indexes = [models.Index(fields=['status', 'name'])]

    def __str__(self):
        return f'{self.code} - {self.name}'

    @property
    def is_interstate_default(self):
        return self.state_code != settings.COMPANY_STATE_CODE


class VendorBankAccount(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='bank_accounts')
    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=20)
    ifsc = models.CharField(max_length=11)
    bank_name = models.CharField(max_length=200)
    branch = models.CharField(max_length=150, blank=True)
    upi_id = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-is_primary', 'id')
        constraints = [
            models.UniqueConstraint(fields=('vendor', 'account_number'), name='uniq_vendor_account_number'),
        ]

    def __str__(self):
        return f'{self.vendor.code} - {self.bank_name} ****{self.account_number[-4:]}'
