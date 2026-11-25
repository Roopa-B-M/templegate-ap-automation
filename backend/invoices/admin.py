from django.contrib import admin

from .models import Invoice, InvoiceLineItem, MatchResult, ValidationResult


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'vendor', 'total_amount', 'status', 'ocr_status', 'created_at')
    list_filter = ('status', 'ocr_status', 'source')
    search_fields = ('invoice_number', 'vendor__name')
    inlines = (InvoiceLineItemInline,)
    readonly_fields = ('raw_ocr_text', 'extracted_data')


@admin.register(ValidationResult)
class ValidationResultAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'check_code', 'status', 'message')
    list_filter = ('check_code', 'status')


@admin.register(MatchResult)
class MatchResultAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'match_type', 'status', 'total_variance')
    list_filter = ('match_type', 'status')
