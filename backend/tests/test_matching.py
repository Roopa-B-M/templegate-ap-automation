"""PO matching engine tests: 2-way, 3-way, tolerance and exceptions."""
from decimal import Decimal

from django.test import TestCase

from invoices.models import Invoice, MatchResult
from invoices.services.matching import run_match
from tests.utils import D, make_grn, make_manual_invoice, make_po, make_user, make_vendor

Decimal = D


class MatchingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vendor = make_vendor(code='V-MATCH')

    def test_two_way_match_ok(self):
        po = make_po(self.vendor)
        invoice = make_manual_invoice(self.vendor, invoice_number='INV-2W', po=po)
        result, ok = run_match(invoice)
        self.assertTrue(ok)
        self.assertEqual(result.match_type, MatchResult.MatchType.TWO_WAY)
        self.assertEqual(result.status, MatchResult.Status.MATCHED)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.MATCHED)

    def test_three_way_match_ok_after_grn(self):
        po = make_po(self.vendor)
        make_grn(po)
        invoice = make_manual_invoice(self.vendor, invoice_number='INV-3W', po=po)
        result, ok = run_match(invoice)
        self.assertTrue(ok)
        self.assertEqual(result.match_type, MatchResult.MatchType.THREE_WAY)
        self.assertEqual(result.status, MatchResult.Status.MATCHED)

    def test_three_way_quantity_not_received_fails(self):
        po = make_po(self.vendor)
        po_line = po.lines.first()
        make_grn(po, quantities={po_line.pk: Decimal('4')})  # only 4 of 10 received
        invoice = make_manual_invoice(self.vendor, invoice_number='INV-3WBAD', po=po)
        result, ok = run_match(invoice)
        self.assertFalse(ok)
        self.assertEqual(result.status, MatchResult.Status.MISMATCH)
        self.assertEqual(result.details['problems']['qty_not_received_3way'], 1)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.MATCH_EXCEPTION)

    def test_rate_above_tolerance_fails(self):
        # 0.5% tolerance; 2600 vs 1450 is far above it
        po = make_po(self.vendor)
        invoice = make_manual_invoice(self.vendor, invoice_number='INV-RATEBAD', po=po,
                                      unit_price=Decimal('2600'))
        result, ok = run_match(invoice)
        self.assertFalse(ok)
        self.assertEqual(result.details['problems']['rate_over_tolerance'], 1)

    def test_line_not_on_po_fails(self):
        po = make_po(self.vendor)
        invoice = make_manual_invoice(self.vendor, invoice_number='INV-LINEBAD', po=po)
        from invoices.models import InvoiceLineItem

        InvoiceLineItem.objects.create(
            invoice=invoice, line_number=2, description='Mystery Item', hsn_code='9999',
            quantity=Decimal('1'), unit='NOS', unit_price=Decimal('500'), tax_rate=Decimal('18'),
            line_total=Decimal('500'))
        result, ok = run_match(invoice)
        self.assertFalse(ok)
        self.assertEqual(result.details['problems']['lines_not_on_po'], 1)

    def test_non_po_invoice_not_applicable(self):
        invoice = make_manual_invoice(self.vendor, invoice_number='INV-NOPO', po=None)
        result, ok = run_match(invoice)
        self.assertTrue(ok)
        self.assertEqual(result.match_type, MatchResult.MatchType.NOT_APPLICABLE)
