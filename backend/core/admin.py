from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'username', 'action', 'entity', 'entity_id', 'entity_repr', 'ip_address')
    list_filter = ('action', 'entity')
    search_fields = ('username', 'entity_repr', 'entity_id')
    readonly_fields = [f.name for f in AuditLog._meta.fields]
