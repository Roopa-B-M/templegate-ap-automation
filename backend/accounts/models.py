from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Application user with role-based access for the AP workflow."""

    class Roles(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrator'
        AP_CLERK = 'AP_CLERK', 'AP Clerk'
        APPROVER = 'APPROVER', 'Approver'
        FINANCE = 'FINANCE', 'Finance'

    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.AP_CLERK)
    phone = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ('username',)

    @property
    def role_display_short(self):
        return self.get_role_display()

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'


class Notification(models.Model):
    """In-app notification used for approvals, reminders, escalations, payments."""

    class Types(models.TextChoices):
        INFO = 'INFO', 'Info'
        SUCCESS = 'SUCCESS', 'Success'
        WARNING = 'WARNING', 'Warning'
        ERROR = 'ERROR', 'Error'
        APPROVAL = 'APPROVAL', 'Approval'
        PAYMENT = 'PAYMENT', 'Payment'
        ESCALATION = 'ESCALATION', 'Escalation'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=Types.choices, default=Types.INFO)
    is_read = models.BooleanField(default=False, db_index=True)
    link = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=['user', 'is_read'])]

    def __str__(self):
        return f'To {self.user.username}: {self.title}'
