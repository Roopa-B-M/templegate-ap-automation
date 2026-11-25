"""Invoice capture pipeline: file -> OCR -> field identification -> validation.

Bulk upload spawns one background thread per invoice (no external task
queue required for a local deployment); a management command
(process_pending_ocr) retries anything left PENDING after a restart.
"""
import logging
import threading
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone

from purchase_orders.models import PurchaseOrder
from vendors.models import Vendor
from vendors.services import is_valid_gstin
from ..models import Invoice, InvoiceLineItem
from .ai_extract import run_ai_assist
from .ocr import run_extraction
from .field_identifier import run_field_identification
from .matching import run_match
from .validation import run_validation

logger = logging.getLogger('invoices')


def _d(value):
    try:
        return Decimal(str(value)) if value is not None else None
    except (InvalidOperation, TypeError):
        return None


def _json_safe(obj):
    """Convert dates/decimals to JSON-serialisable primitives."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return str(obj)


def create_invoice_from_file(django_file, user, vendor_id=None, po_number=None,
                             source=Invoice.Source.UPLOAD):
    """Validates the uploaded file and creates an Invoice row (OCR pending)."""
    import os

    ext = os.path.splitext(django_file.name)[1].lower()
    if ext not in settings.ALLOWED_INVOICE_EXTENSIONS:
        raise ValueError(f'Unsupported file type "{ext}". Allowed: PDF, JPG, PNG, TIFF.')
    if django_file.size > settings.MAX_INVOICE_FILE_MB * 1024 * 1024:
        raise ValueError(f'File exceeds the {settings.MAX_INVOICE_FILE_MB} MB limit.')

    invoice = Invoice.objects.create(
        invoice_number='',
        source=source,
        file=django_file,
        file_name=django_file.name,
        file_type=ext.lstrip('.').upper(),
        vendor_id=vendor_id or None,
        ocr_status=Invoice.OcrStatus.PENDING,
        status=Invoice.Status.UPLOADED,
        created_by=user,
    )
    if po_number:
        po = PurchaseOrder.objects.filter(po_number__iexact=po_number.strip()).first()
        if po:
            invoice.po = po
            invoice.save(update_fields=['po'])
    return invoice


def process_ocr(invoice_id):
    """Runs OCR + field identification + auto validation/matching for one invoice."""
    try:
        invoice = Invoice.objects.get(pk=invoice_id)
    except Invoice.DoesNotExist:
        return
    if invoice.ocr_status == Invoice.OcrStatus.COMPLETED:
        return
    invoice.ocr_status = Invoice.OcrStatus.PROCESSING
    invoice.ocr_error = ''
    invoice.save(update_fields=['ocr_status', 'ocr_error', 'updated_at'])
    try:
        extraction = run_extraction(invoice.file.path, invoice.file_type)
        result = run_field_identification(extraction)
        # Optional AI assist (off by default): only used when the rule engine's
        # confidence is low or mandatory fields are missing. See ai_extract.py.
        fields, assist_used = run_ai_assist(extraction, result['fields'])

        invoice.raw_ocr_text = extraction['text'][:200000]
        invoice.page_count = extraction['page_count']
        invoice.ocr_confidence = Decimal(str(extraction['confidence']))

        # Map identified fields onto the structured columns
        def value_of(key):
            entry = fields.get(key)
            return entry['value'] if entry else None

        invoice.invoice_number = str(value_of('invoice_number') or invoice.invoice_number or '')
        invoice.invoice_date = value_of('invoice_date') or invoice.invoice_date
        invoice.due_date = value_of('due_date') or invoice.due_date
        invoice.subtotal = _d(value_of('subtotal')) or invoice.subtotal
        tax = _d(value_of('tax_amount'))
        if tax:
            invoice.tax_amount = tax
        total = _d(value_of('total_amount'))
        if total:
            invoice.total_amount = total

        # Vendor identification via GSTIN -> vendor master lookup step
        if invoice.vendor_id is None:
            gstin = value_of('seller_gstin')
            if gstin and is_valid_gstin(gstin):
                vendor = Vendor.objects.filter(gstin=gstin).first()
                if vendor:
                    invoice.vendor = vendor
            else:
                seller = value_of('seller_name')
                if seller:
                    vendor = Vendor.objects.filter(name__icontains=seller.split()[0]).first()
                    if vendor:
                        invoice.vendor = vendor

        # PO identification
        po_number = value_of('po_number')
        if po_number and invoice.po_id is None:
            po = PurchaseOrder.objects.filter(po_number__iexact=str(po_number)).first()
            if po:
                invoice.po = po

        # Line items from table extraction
        items = result['line_items']
        if items:
            invoice.line_items.all().delete()
            for idx, item in enumerate(items, start=1):
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    line_number=idx,
                    description=item['description'],
                    hsn_code=item.get('hsn_code', ''),
                    quantity=item['quantity'],
                    unit=item.get('unit', 'NOS'),
                    unit_price=item['unit_price'],
                    tax_rate=item['tax_rate'],
                    ocr_confidence=item.get('ocr_confidence'),
                )

        invoice.extracted_data = {
            'fields': _json_safe(fields),
            'method': extraction['method'],
            'extraction_engine': 'rule-based + AI assist' if assist_used else 'rule-based',
            'ai_assist_used': assist_used,
            'identified_at': timezone.now().isoformat(),
        }
        invoice.ocr_status = Invoice.OcrStatus.COMPLETED
        invoice.status = Invoice.Status.EXTRACTED
        invoice.save()
    except Exception as exc:  # noqa: BLE001 - record and surface the failure
        logger.exception('OCR failed for invoice %s', invoice_id)
        invoice.ocr_status = Invoice.OcrStatus.FAILED
        invoice.ocr_error = str(exc)[:2000]
        invoice.save(update_fields=['ocr_status', 'ocr_error', 'updated_at'])
        return

    # Automatic post-OCR steps
    validation = run_validation(invoice)
    if validation['passed'] and invoice.po_id:
        run_match(invoice)


def process_async(invoice):
    thread = threading.Thread(target=process_ocr, args=(invoice.pk,), daemon=True,
                              name=f'ocr-{invoice.pk}')
    thread.start()
    return thread


def apply_reviewed_fields(invoice, data):
    """Persist human-reviewed/corrected fields, then re-run validation + matching."""
    from ..serializers import InvoiceReviewSerializer

    serializer = InvoiceReviewSerializer(instance=invoice, data=data, partial=True)
    serializer.is_valid(raise_exception=True)
    updated = serializer.save()

    validation = run_validation(updated)
    if validation['passed'] and updated.po_id:
        run_match(updated)
    elif not updated.po_id:
        MatchResult_cleanup(updated)
    return updated


def MatchResult_cleanup(invoice):
    from ..models import MatchResult
    MatchResult.objects.filter(invoice=invoice).delete()
    if invoice.status == Invoice.Status.MATCH_EXCEPTION:
        invoice.status = Invoice.Status.VALIDATED
        invoice.save(update_fields=['status', 'updated_at'])
