from django.contrib import admin

from .models import GRN, GRNLine, POLine, PurchaseOrder


class POLineInline(admin.TabularInline):
    model = POLine
    extra = 0


class GRNLineInline(admin.TabularInline):
    model = GRNLine
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'vendor', 'po_date', 'total_amount', 'status')
    list_filter = ('status',)
    search_fields = ('po_number', 'vendor__name')
    inlines = (POLineInline,)


@admin.register(GRN)
class GRNAdmin(admin.ModelAdmin):
    list_display = ('grn_number', 'po', 'receipt_date', 'status')
    search_fields = ('grn_number',)
    inlines = (GRNLineInline,)
