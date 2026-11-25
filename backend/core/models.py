from django.db import models


class AuditLog(models.Model):
    """Immutable trail of every create/update/delete and auth event."""

    class Actions(models.TextChoices):
        CREATE = 'CREATE', 'Created'
        UPDATE = 'UPDATE', 'Updated'
        DELETE = 'DELETE', 'Deleted'
        LOGIN = 'LOGIN', 'Login'
        LOGIN_FAILED = 'LOGIN_FAILED', 'Login failed'
        LOGOUT = 'LOGOUT', 'Logout'

    user = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_logs')
    username = models.CharField(max_length=150, blank=True, db_index=True)
    action = models.CharField(max_length=20, choices=Actions.choices, db_index=True)
    entity = models.CharField(max_length=64, db_index=True)
    entity_id = models.CharField(max_length=64, blank=True)
    entity_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Audit log entry'

    def __str__(self):
        return f'{self.action} {self.entity}#{self.entity_id} by {self.username or "system"}'
