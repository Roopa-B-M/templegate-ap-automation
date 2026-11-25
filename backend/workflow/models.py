from django.conf import settings
from django.db import models


class ApprovalMatrix(models.Model):
    """Configurable approval matrix: who approves which amount band, in which order."""

    class ApproverRole(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrator'
        AP_CLERK = 'AP_CLERK', 'AP Clerk'
        APPROVER = 'APPROVER', 'Approver'
        FINANCE = 'FINANCE', 'Finance'

    APPROVER_ROLES = ApproverRole.choices  # module-level reuse for ApprovalTask

    name = models.CharField(max_length=100)
    level = models.PositiveIntegerField()
    min_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True,
                                     help_text='Leave empty for "no upper limit".')
    approver_role = models.CharField(max_length=20, choices=ApproverRole.choices)
    is_parallel = models.BooleanField(default=False,
                                      help_text='All users with the role must approve (parallel approval).')
    escalation_hours = models.PositiveIntegerField(default=48)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('level',)
        constraints = [models.UniqueConstraint(fields=('level', 'name'), name='uniq_matrix_level_name')]

    def __str__(self):
        return f'L{self.level} {self.name} ({self.approver_role})'


class ApprovalTask(models.Model):
    """One approval assignment for an invoice at a matrix level."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        SKIPPED = 'SKIPPED', 'Skipped'

    invoice = models.ForeignKey('invoices.Invoice', on_delete=models.CASCADE, related_name='approval_tasks')
    matrix = models.ForeignKey(ApprovalMatrix, null=True, blank=True, on_delete=models.SET_NULL)
    level = models.PositiveIntegerField()
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='approval_tasks')
    approver_role = models.CharField(max_length=20, choices=ApprovalMatrix.ApproverRole.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    is_active = models.BooleanField(default=False, help_text='Previous levels must approve first.')
    is_parallel = models.BooleanField(default=False)
    escalation_hours = models.PositiveIntegerField(default=48)
    due_at = models.DateTimeField(null=True, blank=True)
    escalated = models.BooleanField(default=False)
    reminder_count = models.PositiveIntegerField(default=0)
    comments = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('level', 'id')

    def __str__(self):
        return f'{self.invoice_id} L{self.level} {self.approver_role} {self.status}'
