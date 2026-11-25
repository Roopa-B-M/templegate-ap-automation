"""Invoice validation engine tests: mandatory, duplicate, GST, amount, tax, vendor master."""
from decimal import Decimal

from django.test import TestCase

from invoices.models import Invoice, ValidationResult
from invoices.services.validation import run_validation
from tests.utils import D, make_manual_invoice, make_user, make_vendor

Decimal = D


class ValidationEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clerk = make_user('clerk-val', 'AP_CLERK')
        cls.vendor = make_vendor(code='V-VAL', status='APPROVED')

    def test_happy_invoice_passes_all_checks(self):
        invoice = make_manual_invoice(self.vendor, invoice_number='INV-OK1')
        result = run_validation(invoice)
        self.assertTrue(result['passed'], result['failed_checks'])
        codes = set(invoice.validation_results.values_list('check_code', flat=True))
        self.assertIn('MANDATORY_FIELDS', codes)
        self.assertIn('DUPLICATE_INVOICE', codes)
        self.assertIn('GST_VALIDATION', codes)
        self.assertIn('AMOUNT_VALIDATION', codes)
        self.assertIn('TAX_CALCULATION', codes)
        self.assertIn('VENDOR_MASTER_VALIDATION', codes)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.VALIDATED)

    def test_duplicate_invoice_fails(self):
        make_manual_invoice(self.vendor, invoice_number='INV-DUP')
        dup = make_manual_invoice(self.vendor, invoice_number='INV-DUP')
        result = run_validation(dup)
        self.assertFalse(result['passed'])
        check = dup.validation_results.filter(check_code='DUPLICATE_INVOICE').first()
        self.assertEqual(check.status, ValidationResult.Status.FAIL)
        self.assertIn('Duplicate of invoice', check.message)

    def test_mandatory_field_failures(self):
        invoice = make_manual_invoice(self.vendor, invoice_number='')
        invoice.total_amount = None
        invoice.save(update_fields=['total_amount'])
        result = run_validation(invoice)
        self.assertFalse(result['passed'])
        check = invoice.validation_results.filter(check_code='MANDATORY_FIELDS').first()
        self.assertIn('invoice number', check.message)
        self.assertIn('total amount', check.message)

    def test_non_standard_gst_rate_fails(self):
        invoice = make_manual_invoice(self.vendor, invoice_number='INV-RATE', tax_rate=Decimal('14'))
        result = run_validation(invoice)
        self.assertFalse(result['passed'])
        check = invoice.validation_results.filter(check_code='GST_VALIDATION').first()
        self.assertIn('Non-standard GST rate', check.message)

    def test_line_totals_vs_subtotal_mismatch_fails(self):
        invoice = make_manual_invoice(self.vendor, invoice_number='INV-SUM', subtotal=Decimal('99999'))
        result = run_validation(invoice)
        self.assertFalse(result['passed'])
        check = invoice.validation_results.filter(check_code='AMOUNT_VALIDATION').first()
        self.assertIn('does not match invoice subtotal', check.message)

    def test_wrong_vendor_gstin_fails(self):
        from vendors.models import Vendor

        bad_vendor = make_vendor(code='V-BADGST')
        Vendor.objects.filter(pk=bad_vendor.pk).update(gstin='27AAACS1234FPZ0')  # wrong digit
        bad_vendor.refresh_from_db()
        invoice = make_manual_invoice(bad_vendor, invoice_number='INV-GST')
        result = run_validation(invoice)
        self.assertFalse(result['passed'])
        check = invoice.validation_results.filter(check_code='GST_VALIDATION').first()
        self.assertIn('check-digit', check.message)

    def test_blocked_vendor_fails(self):
        from vendors.models import Vendor

        blocked = make_vendor(code='V-BLOCK', status='BLOCKED')
        invoice = make_manual_invoice(blocked, invoice_number='INV-BLK')
        result = run_validation(invoice)
        self.assertFalse(result['passed'])
        check = invoice.validation_results.filter(check_code='VENDOR_MASTER_VALIDATION').first()
        self.assertIn('blocked', check.message)

    def test_unapproved_vendor_without_bank_account_fails(self):
        draft = make_vendor(code='V-DRAFT', status='DRAFT', account_number='76543210987')
        draft.bank_accounts.all().delete()
        invoice = make_manual_invoice(draft, invoice_number='INV-DRAFT2')
        result = run_validation(invoice)
        self.assertFalse(result['passed'])
