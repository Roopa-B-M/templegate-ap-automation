"""Retry OCR for any invoice left PENDING/PROCESSING (e.g. after a restart)."""
from django.core.management.base import BaseCommand

from invoices.models import Invoice
from invoices.services.pipeline import process_ocr


class Command(BaseCommand):
    help = 'Process all invoices whose OCR is still pending (background-safe).'

    def handle(self, *args, **options):
        pending = Invoice.objects.filter(ocr_status__in=[Invoice.OcrStatus.PENDING,
                                                         Invoice.OcrStatus.PROCESSING])
        count = pending.count()
        for invoice in pending.iterator():
            process_ocr(invoice.pk)
        self.stdout.write(self.style.SUCCESS(f'Processed {count} pending invoice(s)'))
