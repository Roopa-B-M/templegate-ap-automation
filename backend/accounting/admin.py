from django.contrib import admin

from .models import ERPSyncLog, GLAccountMapping


@admin.register(GLAccountMapping)
class GLAccountMappingAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'expense_account', 'payable_account', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'vendor__name')


@admin.register(ERPSyncLog)
class ERPSyncLogAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'connector', 'format', 'status', 'erp_reference', 'created_at')
    list_filter = ('status', 'format', 'connector')
    search_fields = ('erp_reference', 'invoice__invoice_number')
    readonly_fields = ('payload_preview',)
