"""ERP/accounting integration tests: connectors, posting rules, exports, retry."""
from decimal import Decimal
from unittest import mock
from xml.etree import ElementTree

from django.test import TestCase, override_settings

from accounting.models import ERPSyncLog, GLAccountMapping
from accounting.services import (ERPConnectorError, SimulatedERPConnector, TallyXMLConnector,
                                 build_voucher, export_csv, export_json, get_connector,
                                 post_invoice_to_erp)
from invoices.models import Invoice
from tests.utils import D, make_manual_invoice, make_user, make_vendor


class AccountingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.finance = make_user('erp-finance', 'FINANCE')
        cls.vendor = make_vendor(code='V-ERP', state_code='27')

    def setUp(self):
        self.mapping = GLAccountMapping.objects.create(
            name='Default', vendor=None, expense_account='Purchase Account',
            cgst_account='Input CGST', sgst_account='Input SGST', igst_account='Input IGST',
            payable_account='Accounts Payable')
        self.invoice = make_manual_invoice(self.vendor, invoice_number='INV-ERP1')
        self.invoice.status = Invoice.Status.APPROVED
        self.invoice.save(update_fields=['status'])

    def test_post_invoice_success_syncs_status(self):
        result = post_invoice_to_erp(self.invoice, self.finance)
        self.assertEqual(result['status'], 'SYNCED')
        self.assertTrue(result['erp_reference'])
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.erp_status, Invoice.ErpStatus.SYNCED)
        self.assertEqual(self.invoice.erp_reference, result['erp_reference'])
        log = ERPSyncLog.objects.get(invoice=self.invoice)
        self.assertEqual(log.status, ERPSyncLog.Status.SYNCED)
        self.assertEqual(log.requested_by, self.finance)

    def test_pending_invoice_cannot_be_posted(self):
        self.invoice.status = Invoice.Status.PENDING_APPROVAL
        self.invoice.save(update_fields=['status'])
        with self.assertRaises(ERPConnectorError):
            post_invoice_to_erp(self.invoice, self.finance)
        log = ERPSyncLog.objects.get(invoice=self.invoice)
        self.assertEqual(log.status, ERPSyncLog.Status.FAILED)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.erp_status, Invoice.ErpStatus.FAILED)

    def test_missing_mapping_fails_with_clear_error(self):
        GLAccountMapping.objects.all().delete()
        with self.assertRaises(ERPConnectorError):
            post_invoice_to_erp(self.invoice, self.finance)

    def test_retry_updates_failed_log(self):
        self.invoice.status = Invoice.Status.PENDING_APPROVAL
        self.invoice.save(update_fields=['status'])
        try:
            post_invoice_to_erp(self.invoice, self.finance)
        except ERPConnectorError:
            pass
        log = ERPSyncLog.objects.get(invoice=self.invoice)
        self.assertEqual(log.status, ERPSyncLog.Status.FAILED)
        self.invoice.status = Invoice.Status.APPROVED
        self.invoice.save(update_fields=['status'])
        result = post_invoice_to_erp(self.invoice, self.finance, replace_log=log)
        log.refresh_from_db()
        self.assertEqual(log.status, ERPSyncLog.Status.SYNCED)
        self.assertEqual(result['erp_reference'], log.erp_reference)

    def test_vendor_specific_mapping_used_for_interstate_gst(self):
        ka_vendor = make_vendor(code='V-ERPKA', state_code='29')  # inter-state
        invoice = make_manual_invoice(ka_vendor, invoice_number='INV-ERP2')
        invoice.status = Invoice.Status.APPROVED
        invoice.save(update_fields=['status'])
        voucher = build_voucher(invoice, self.mapping)
        supply_types = [entry['account'] for entry in voucher['ledger_entries']
                        if entry['type'] == 'DEBIT']
        self.assertIn('Input IGST', supply_types)
        self.assertNotIn('Input CGST', supply_types)

    def test_tally_xml_is_wellformed_envelope(self):
        connector = TallyXMLConnector()
        xml = connector.envelope([self.invoice], self.mapping)
        root = ElementTree.fromstring(xml)
        self.assertEqual(root.tag, 'ENVELOPE')
        vouchers = [el for el in root.iter('VOUCHER')]
        self.assertEqual(len(vouchers), 1)
        self.assertEqual(vouchers[0].get('VCHTYPE'), 'Purchase')
        ledgers = [el.text for el in root.iter('LEDGERNAME')]
        self.assertIn('Purchase Account', ledgers)
        self.assertIn('Accounts Payable', ledgers)
        self.assertIn('Input CGST', ledgers)  # intra-state vendor 27

    def test_csv_export_rows(self):
        filename, content_type, payload = export_csv([self.invoice])
        text = payload.decode()
        self.assertTrue(filename.endswith('.csv'))
        self.assertIn('Purchase Account', text)
        self.assertIn(self.vendor.name, text)
        self.assertIn('27AAACS1234F', text)

    def test_json_export_structure(self):
        filename, content_type, payload = export_json([self.invoice])
        import json

        data = json.loads(payload)
        self.assertEqual(data['document_count'], 1)
        document = data['documents'][0]
        self.assertEqual(document['document_type'], 'PURCHASE_VOUCHER')
        self.assertEqual(len(document['lines']), 1)
        self.assertTrue(filename.endswith('.json'))

    def test_connector_factory(self):
        with override_settings(ERP_CONNECTOR='tally_xml'):
            self.assertIsInstance(get_connector(), TallyXMLConnector)
        with override_settings(ERP_CONNECTOR='simulated'):
            self.assertIsInstance(get_connector(), SimulatedERPConnector)

    def test_simulation_is_deterministic_and_local(self):
        connector = get_connector()
        self.assertEqual(connector.name, 'SimulatedERPConnector')
        with mock.patch('urllib.request.urlopen') as fake_open:
            # The simulated connector must never open a network connection.
            post_invoice_to_erp(self.invoice, self.finance)
            fake_open.assert_not_called()

    def test_reference_generated_when_invoice_number_missing(self):
        self.invoice.invoice_number = ''
        self.invoice.save(update_fields=['invoice_number'])
        voucher = build_voucher(self.invoice, self.mapping)
        self.assertEqual(voucher['reference'], f'INV-{self.invoice.pk}')
