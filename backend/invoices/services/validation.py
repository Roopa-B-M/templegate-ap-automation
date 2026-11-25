"""Invoice validation engine.

Runs every rule from the scope document and persists a ValidationResult
row per check. An invoice is VALIDATED only when no check FAILs.
"""
from decimal import Decimal

from django.conf import settings
from django.db.models import Q

from vendors.services import is_valid_gstin
from ..models import Invoice, ValidationResult

AMOUNT_TOLERANCE = Decimal('0.05')


def _save(invoice, code, status, message, details=None):
    ValidationResult.objects.create(
        invoice=invoice, check_code=code, status=status,
        message=message[:255], details=details or {},
    )
    return status == ValidationResult.Status.FAIL


def run_validation(invoice):
    """Execute all checks; returns {'passed': bool, 'failed': [codes]}."""
    invoice.validation_results.all().delete()
    failed = []

    # ------------------------------------------------------------------
    # 1. Mandatory fields
    # ------------------------------------------------------------------
    missing = []
    if not invoice.invoice_number:
        missing.append('invoice number')
    if invoice.vendor_id is None:
        missing.append('vendor')
    if invoice.invoice_date is None:
        missing.append('invoice date')
    if not invoice.total_amount or invoice.total_amount <= 0:
        missing.append('total amount > 0')
    if not invoice.line_items.exists():
        missing.append('at least one line item')
    if missing:
        failed.append(_save(invoice, ValidationResult.CheckCode.MANDATORY_FIELDS,
                            ValidationResult.Status.FAIL,
                            'Missing mandatory fields: ' + ', '.join(missing),
                            {'missing': missing}))
    else:
        _save(invoice, ValidationResult.CheckCode.MANDATORY_FIELDS,
              ValidationResult.Status.PASS, 'All mandatory fields present')

    # ------------------------------------------------------------------
    # 2. Duplicate invoice (same vendor + invoice number)
    # ------------------------------------------------------------------
    if invoice.invoice_number and invoice.vendor_id:
        dup = Invoice.objects.filter(
            vendor_id=invoice.vendor_id,
            invoice_number__iexact=invoice.invoice_number,
        ).exclude(pk=invoice.pk).first()
        if dup:
            failed.append(_save(invoice, ValidationResult.CheckCode.DUPLICATE_INVOICE,
                                ValidationResult.Status.FAIL,
                                f'Duplicate of invoice #{dup.pk} ({dup.invoice_number}) '
                                f'status {dup.get_status_display()}',
                                {'duplicate_invoice_id': dup.pk, 'duplicate_status': dup.status}))
        else:
            _save(invoice, ValidationResult.CheckCode.DUPLICATE_INVOICE,
                  ValidationResult.Status.PASS, 'No duplicate found for this vendor')
    else:
        _save(invoice, ValidationResult.CheckCode.DUPLICATE_INVOICE,
              ValidationResult.Status.WARN, 'Skipped - vendor or invoice number missing')

    # ------------------------------------------------------------------
    # 3. GST / tax validation
    # ------------------------------------------------------------------
    gst_details = {}
    gst_ok = True
    gst_msg = ''
    if invoice.vendor_id is None:
        gst_ok = False
        gst_msg = 'Vendor not linked - GST validation skipped.'
    else:
        vendor = invoice.vendor
        gst_details['vendor_gstin'] = vendor.gstin
        if not is_valid_gstin(vendor.gstin):
            gst_ok = False
            gst_msg = 'Vendor GSTIN fails format/check-digit validation.'
        extracted = (invoice.extracted_data or {}).get('fields', {}).get('seller_gstin', {}).get('value')
        if extracted and extracted != vendor.gstin:
            gst_ok = False
            gst_msg = f'Invoice GSTIN {extracted} does not match vendor master {vendor.gstin}.'
            gst_details['invoice_gstin'] = extracted
        if vendor.state_code == settings.COMPANY_STATE_CODE:
            gst_details['supply_type'] = 'INTRA_STATE (CGST + SGST expected)'
        else:
            gst_details['supply_type'] = 'INTER_STATE (IGST expected)'
        rates = set()
        for line in invoice.line_items.all():
            rates.add(float(line.tax_rate))
        invalid = [r for r in rates if r not in settings.VALID_GST_RATES and r != 0]
        if invalid:
            gst_ok = False
            gst_msg = f'Non-standard GST rate(s) used: {invalid}.'
        gst_details['rates'] = sorted(rates)
    if not gst_ok:
        failed.append(_save(invoice, ValidationResult.CheckCode.GST_VALIDATION,
                            ValidationResult.Status.FAIL, gst_msg, gst_details))
    else:
        _save(invoice, ValidationResult.CheckCode.GST_VALIDATION,
              ValidationResult.Status.PASS, gst_msg or 'GSTIN and tax rates valid', gst_details)

    # ------------------------------------------------------------------
    # 4. Amount validation (line totals vs header)
    # ------------------------------------------------------------------
    lines_sum = Decimal('0')
    for line in invoice.line_items.all():
        lines_sum += line.line_total
    amount_ok = True
    amount_msg = 'Line items reconcile with header amounts.'
    amount_details = {'line_items_total': str(lines_sum.quantize(Decimal('0.01'))),
                      'subtotal': str(invoice.subtotal or ''), 'total': str(invoice.total_amount or '')}
    if invoice.subtotal is not None and abs(lines_sum - invoice.subtotal) > AMOUNT_TOLERANCE:
        amount_ok = False
        amount_msg = (f'Sum of line items ({lines_sum}) does not match invoice subtotal '
                      f'({invoice.subtotal}).')
    if invoice.subtotal is not None and invoice.total_amount is not None:
        expected_total = invoice.subtotal + (invoice.tax_amount or Decimal('0'))
        if abs(expected_total - invoice.total_amount) > AMOUNT_TOLERANCE:
            amount_ok = False
            amount_msg += f' Subtotal + tax ({expected_total}) != total ({invoice.total_amount}).'
    if not invoice.line_items.exists():
        amount_ok = False
        amount_msg = 'No line items to validate.'
    if not amount_ok:
        failed.append(_save(invoice, ValidationResult.CheckCode.AMOUNT_VALIDATION,
                            ValidationResult.Status.FAIL, amount_msg.strip(), amount_details))
    else:
        _save(invoice, ValidationResult.CheckCode.AMOUNT_VALIDATION,
              ValidationResult.Status.PASS, amount_msg, amount_details)

    # ------------------------------------------------------------------
    # 5. Tax calculation check (line tax = qty x price x rate)
    # ------------------------------------------------------------------
    tax_ok = True
    expected_tax = Decimal('0')
    for line in invoice.line_items.all():
        expected_tax += (line.line_total * line.tax_rate / Decimal('100'))
    expected_tax = expected_tax.quantize(Decimal('0.01'))
    if invoice.tax_amount is None:
        tax_ok = False
        tax_msg = 'Tax amount missing on invoice header.'
    elif abs(expected_tax - invoice.tax_amount) > Decimal('1.00'):
        tax_ok = False
        tax_msg = (f'Expected tax {expected_tax} (from line items and rates) differs from '
                   f'invoiced tax {invoice.tax_amount}.')
    else:
        tax_msg = f'Tax amount {invoice.tax_amount} consistent with line-level rates.'
    if not tax_ok:
        failed.append(_save(invoice, ValidationResult.CheckCode.TAX_CALCULATION,
                            ValidationResult.Status.FAIL, tax_msg,
                            {'expected_tax': str(expected_tax), 'invoiced_tax': str(invoice.tax_amount or '')}))
    else:
        _save(invoice, ValidationResult.CheckCode.TAX_CALCULATION,
              ValidationResult.Status.PASS, tax_msg)

    # ------------------------------------------------------------------
    # 6. Vendor master validation
    # ------------------------------------------------------------------
    if invoice.vendor_id is None:
        failed.append(_save(invoice, ValidationResult.CheckCode.VENDOR_MASTER_VALIDATION,
                            ValidationResult.Status.FAIL,
                            'Invoice is not linked to any vendor in the master.'))
    else:
        vendor = invoice.vendor
        if vendor.status == 'BLOCKED':
            vendor_ok, vendor_msg = False, f'Vendor {vendor.name} is blocked.'
        elif vendor.status != 'APPROVED':
            vendor_ok, vendor_msg = False, f'Vendor {vendor.name} is not approved (onboarding {vendor.get_status_display()}).'
        elif not vendor.bank_accounts.exists():
            vendor_ok, vendor_msg = False, f'Vendor {vendor.name} has no bank account on file.'
        else:
            vendor_ok, vendor_msg = True, f'Vendor {vendor.name} is approved with bank details on file.'
        if not vendor_ok:
            failed.append(_save(invoice, ValidationResult.CheckCode.VENDOR_MASTER_VALIDATION,
                                ValidationResult.Status.FAIL, vendor_msg))
        else:
            _save(invoice, ValidationResult.CheckCode.VENDOR_MASTER_VALIDATION,
                  ValidationResult.Status.PASS, vendor_msg)

    failed_rows = invoice.validation_results.filter(status=ValidationResult.Status.FAIL)
    passed = not failed_rows.exists()
    if passed and invoice.status not in (
        Invoice.Status.PENDING_APPROVAL, Invoice.Status.APPROVED, Invoice.Status.REJECTED,
        Invoice.Status.PAYMENT_REQUESTED, Invoice.Status.SCHEDULED, Invoice.Status.PAID,
    ):
        invoice.status = Invoice.Status.VALIDATED
    elif not passed and invoice.status in (
        Invoice.Status.UPLOADED, Invoice.Status.EXTRACTED, Invoice.Status.VALIDATED,
        Invoice.Status.MATCHED, Invoice.Status.MATCH_EXCEPTION,
    ):
        invoice.status = Invoice.Status.EXCEPTION
    invoice.save(update_fields=['status', 'updated_at'])
    return {'passed': passed, 'failed_checks': [r.message for r in failed_rows]}
