from django.contrib import admin

from .models import ApprovalMatrix, ApprovalTask


@admin.register(ApprovalMatrix)
class ApprovalMatrixAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'min_amount', 'max_amount', 'approver_role', 'is_parallel', 'active')
    list_filter = ('approver_role', 'active', 'is_parallel')
    ordering = ('level',)


@admin.register(ApprovalTask)
class ApprovalTaskAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'level', 'approver', 'approver_role', 'status', 'escalated', 'due_at')
    list_filter = ('status', 'approver_role', 'escalated')
