from django.contrib import admin

from .models import PaymentRequest


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ('payment_number', 'invoice', 'amount', 'method', 'status',
                    'scheduled_date', 'bank_reference')
    list_filter = ('status', 'method')
    search_fields = ('payment_number', 'invoice__invoice_number')
