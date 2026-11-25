"""Payment lifecycle tests: request -> approve -> schedule -> process -> PAID,
plus failure handling, bank file generation and statement reconciliation."""
from io import StringIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from invoices.models import Invoice
from payments.models import PaymentRequest
from payments.services import (BankGatewayError, FileBankGateway, SimulatedBankGateway,
                               create_payment, generate_payment_number, get_bank_gateway,
                               process_payment, reconcile_bank_statement)
from tests.utils import D, make_manual_invoice, make_user, make_vendor


class PaymentLifecycleTests(TestCase):
    def setUp(self):
        self.vendor = make_vendor(code='V-PAY')
        self.finance = make_user('pay-finance', 'FINANCE')
        self.invoice = make_manual_invoice(self.vendor, invoice_number='INV-PAY1')
        self.invoice.status = Invoice.Status.APPROVED
        self.invoice.save(update_fields=['status'])

    def test_create_payment_moves_invoice_to_payment_requested(self):
        payment = create_payment(self.invoice, self.finance, 'NEFT')
        self.assertEqual(payment.status, PaymentRequest.Status.PENDING_APPROVAL)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAYMENT_REQUESTED)

    def test_create_payment_rejects_non_approved_invoice(self):
        self.invoice.status = Invoice.Status.PENDING_APPROVAL
        self.invoice.save(update_fields=['status'])
        with self.assertRaises(ValueError):
            create_payment(self.invoice, self.finance, 'NEFT')

    def test_create_payment_rejects_duplicate_active_request(self):
        create_payment(self.invoice, self.finance, 'NEFT')
        self.invoice.status = Invoice.Status.APPROVED
        self.invoice.save(update_fields=['status'])
        with self.assertRaises(ValueError):
            create_payment(self.invoice, self.finance, 'NEFT')

    def test_full_lifecycle_to_paid(self):
        payment = create_payment(self.invoice, self.finance, 'NEFT')
        payment.status = PaymentRequest.Status.APPROVED
        payment.approved_by = self.finance
        payment.save(update_fields=['status', 'approved_by'])
        payment.status = PaymentRequest.Status.SCHEDULED
        payment.scheduled_date = payment.created_at.date()
        payment.save(update_fields=['status', 'scheduled_date'])

        process_payment(payment)
        payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(payment.status, PaymentRequest.Status.PROCESSED)
        self.assertTrue(payment.bank_reference)  # UTR assigned
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertIsNotNone(self.invoice.paid_at)

    def test_gateway_failure_sets_failed_state(self):
        payment = create_payment(self.invoice, self.finance, 'NEFT')
        payment.status = PaymentRequest.Status.SCHEDULED
        payment.save(update_fields=['status'])
        with mock.patch.object(SimulatedBankGateway, 'execute',
                               side_effect=BankGatewayError('Beneficiary rejected (simulated)')):
            process_payment(payment)
        payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(payment.status, PaymentRequest.Status.FAILED)
        self.assertIn('rejected', payment.failure_reason)
        self.assertEqual(self.invoice.status, Invoice.Status.PAYMENT_FAILED)

    def test_account_ending_0000_fails_validation(self):
        vendor = make_vendor(code='V-PAYBAD', account_number='99990000')
        invoice = make_manual_invoice(vendor, invoice_number='INV-PAYBAD')
        invoice.status = Invoice.Status.APPROVED
        invoice.save(update_fields=['status'])
        payment = create_payment(invoice, self.finance, 'NEFT')
        payment.status = PaymentRequest.Status.SCHEDULED
        payment.save(update_fields=['status'])
        process_payment(payment)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentRequest.Status.FAILED)

    def test_payment_number_sequence(self):
        first = generate_payment_number()
        create_payment(self.invoice, self.finance, 'NEFT')  # a real request occupies a number
        second = generate_payment_number()
        self.assertTrue(first.startswith('PR-'))
        self.assertNotEqual(first, second)
        self.assertTrue(int(first.split('-')[-1]) < int(second.split('-')[-1]))


class FileBankGatewayTests(TestCase):
    def setUp(self):
        self.vendor = make_vendor(code='V-BANK')
        self.finance = make_user('bank-finance', 'FINANCE')
        self.invoice = make_manual_invoice(self.vendor, invoice_number='INV-BANK1')
        self.invoice.status = Invoice.Status.APPROVED
        self.invoice.save(update_fields=['status'])
        self.payment = create_payment(self.invoice, self.finance, 'NEFT')
        self.payment.status = PaymentRequest.Status.SCHEDULED
        self.payment.scheduled_date = self.payment.created_at.date()
        self.payment.save(update_fields=['status', 'scheduled_date'])

    def test_file_gateway_refuses_inline_execution(self):
        with self.assertRaises(BankGatewayError):
            FileBankGateway().execute(self.payment)

    def test_bulk_file_contains_beneficiary_rows(self):
        filename, content_type, payload = FileBankGateway.generate_bulk_file([self.payment])
        text = payload.decode()
        self.assertIn('BENEFICIARY_ACCOUNT_NO', text)
        self.assertIn('12345678901', text)
        self.assertIn('HDFC0001234', text)
        self.assertIn(self.payment.payment_number, text)
        self.assertEqual(content_type, 'text/csv')

    def test_get_bank_gateway_honours_setting(self):
        from django.test import override_settings

        with override_settings(BANK_GATEWAY='file'):
            self.assertIsInstance(get_bank_gateway(), FileBankGateway)
        with override_settings(BANK_GATEWAY='simulated'):
            self.assertIsInstance(get_bank_gateway(), SimulatedBankGateway)


class StatementReconciliationTests(TestCase):
    def setUp(self):
        self.vendor = make_vendor(code='V-RECON')
        self.finance = make_user('recon-finance', 'FINANCE')
        self.invoice = make_manual_invoice(self.vendor, invoice_number='INV-RECON1',
                                           total=D('5000.00'))
        self.invoice.status = Invoice.Status.APPROVED
        self.invoice.save(update_fields=['status'])
        self.payment = create_payment(self.invoice, self.finance, 'NEFT')
        self.payment.status = PaymentRequest.Status.SCHEDULED
        self.payment.save(update_fields=['status'])

    def _statement(self, rows):
        content = 'utr,amount,date\n' + '\n'.join(rows)
        return SimpleUploadedFile('statement.csv', content.encode(), content_type='text/csv')

    def test_reference_match_reconciles(self):
        upload = self._statement([f'UTR123456789,{self.payment.amount},2026-11-01'])
        result = reconcile_bank_statement(upload)
        self.assertEqual(len(result['matched']), 1)
        self.assertEqual(len(result['unmatched']), 0)
        self.payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentRequest.Status.PROCESSED)
        self.assertEqual(self.payment.bank_reference, 'UTR123456789')
        self.assertTrue(self.payment.is_reconciled)
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

    def test_amount_only_match_reconciles(self):
        upload = self._statement([f'UTR987654321,{self.payment.amount},2026-11-02'])
        result = reconcile_bank_statement(upload)
        self.assertEqual(len(result['matched']), 1)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.bank_reference, 'UTR987654321')

    def test_unmatched_rows_reported(self):
        upload = self._statement(['UTR111111111,999999.00,2026-11-02',
                                  ',5000.00,2026-11-02'])
        result = reconcile_bank_statement(upload)
        self.assertEqual(len(result['matched']), 0)
        self.assertEqual(len(result['unmatched']), 2)
        reasons = ' '.join(row['reason'] for row in result['unmatched'])
        self.assertIn('No scheduled payment', reasons)
        self.assertIn('Missing or unparseable', reasons)

    def test_missing_columns_rejected(self):
        upload = SimpleUploadedFile('bad.csv', b'foo,bar\n1,2\n', content_type='text/csv')
        with self.assertRaises(ValueError):
            reconcile_bank_statement(upload)
