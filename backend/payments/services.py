"""Payment processing: numbering, bank gateway integration and advice PDFs.

The bank gateway is an interface with two selectable implementations
(BANK_GATEWAY setting):

- `simulated` (default): a deterministic in-process simulation of a banking
  host so the full payment lifecycle is demonstrable locally. NO live bank
  connection is made.
- `file`: generates NEFT/RTGS bulk payment instruction CSVs for your bank's
  corporate portal and reconciles returned bank statements (UTR files).

A real NEFT/RTGS host adapter can implement the same `BankGateway` interface
without touching the rest of the system (documented in DEVELOPMENT_CHALLENGES.md).
"""
import csv
import io
import logging
import random
import string
from datetime import date

from django.conf import settings
from django.utils import timezone
from vendors.services import is_valid_ifsc

logger = logging.getLogger('payments')


class BankGatewayError(Exception):
    pass


class BankGateway:
    """Interface for banking integrations (NEFT/RTGS/UPI hosts)."""

    def validate_beneficiary(self, bank_account) -> None:
        raise NotImplementedError

    def execute(self, payment) -> str:
        """Execute the transfer, returns a UTR/bank reference."""
        raise NotImplementedError


class SimulatedBankGateway(BankGateway):
    """Deterministic local simulation of a banking host.

    - Validates beneficiary account + IFSC before executing.
    - Accounts ending in '0000' fail (to demonstrate failure handling).
    - Successful transfers receive a UTR in standard Indian format.
    """

    name = 'SimulatedBankGateway'

    def validate_beneficiary(self, bank_account):
        if bank_account is None:
            raise BankGatewayError('Vendor has no bank account on file.')
        if not is_valid_ifsc(bank_account.ifsc):
            raise BankGatewayError(f'Invalid IFSC code {bank_account.ifsc}.')
        if not (bank_account.account_number or '').isdigit():
            raise BankGatewayError('Invalid beneficiary account number.')

    def execute(self, payment):
        bank_account = payment.invoice.vendor.bank_accounts.filter(is_primary=True).first() \
            or payment.invoice.vendor.bank_accounts.first()
        self.validate_beneficiary(bank_account)
        if bank_account.account_number.endswith('0000'):
            raise BankGatewayError('Beneficiary account validation failed at bank (simulated).')
        stamp = date.today().strftime('%y%m%d')
        random_part = ''.join(random.choices(string.digits, k=10))
        utr = f'{stamp}T{random_part}'
        logger.info('Simulated bank transfer executed for %s -> UTR %s',
                    payment.payment_number, utr)
        return utr


class FileBankGateway(BankGateway):
    """File-based banking integration (no live bank link).

    Produces a NEFT/RTGS bulk payment instruction CSV that a finance user
    uploads to the bank's corporate portal. Money never moves from this
    system; the bank's response statement (UTR, amount, date) is uploaded
    back and reconciled against the payment requests.
    """

    name = 'FileBankGateway'

    def validate_beneficiary(self, bank_account):
        # Same checks as the simulated gateway so bad data is caught early.
        SimulatedBankGateway().validate_beneficiary(bank_account)

    def execute(self, payment):
        raise BankGatewayError(
            'BANK_GATEWAY=file does not execute transfers inline. Generate the bulk payment '
            'file from the Payments page, upload it to your bank portal, then reconcile the '
            'returned statement to mark the payment processed.')

    @staticmethod
    def generate_bulk_file(payments):
        """Render the NEFT/RTGS bulk instruction CSV for scheduled payments.

        Returns (filename, content_type, bytes). Raises BankGatewayError when
        any payment's beneficiary data is invalid.
        """
        beneficiary_checks = SimulatedBankGateway()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['SR_NO', 'PAYMENT_METHOD', 'PAYMENT_DATE', 'BENEFICIARY_NAME',
                         'BENEFICIARY_ACCOUNT_NO', 'BENEFICIARY_IFSC', 'BENEFICIARY_BANK',
                         'AMOUNT', 'CURRENCY', 'DEBIT_REFERENCE', 'REMARKS'])
        rows = 0
        for index, payment in enumerate(payments, start=1):
            vendor = payment.invoice.vendor
            bank_account = None
            if vendor is not None:
                bank_account = vendor.bank_accounts.filter(is_primary=True).first() \
                    or vendor.bank_accounts.first()
            try:
                beneficiary_checks.validate_beneficiary(bank_account)
            except BankGatewayError as exc:
                raise BankGatewayError(f'{payment.payment_number}: {exc}')
            payment_date = payment.scheduled_date or timezone.localdate()
            writer.writerow([
                index, payment.method, payment_date.strftime('%d/%m/%Y'),
                bank_account.account_name, bank_account.account_number, bank_account.ifsc,
                bank_account.bank_name, f'{payment.amount:.2f}', 'INR',
                payment.payment_number,
                f'{payment.invoice.invoice_number or payment.invoice_id} vendor {vendor.code}',
            ])
            rows += 1
        stamp = timezone.localdate().strftime('%Y%m%d')
        filename = f'bank-payment-instructions-{stamp}.csv'
        logger.info('Generated bulk bank payment file with %s instructions', rows)
        return filename, 'text/csv', buffer.getvalue().encode()


def get_bank_gateway():
    """Factory driven by the BANK_GATEWAY setting (simulated|file)."""
    choice = (getattr(settings, 'BANK_GATEWAY', 'simulated') or 'simulated').lower()
    if choice == 'file':
        return FileBankGateway()
    return SimulatedBankGateway()


GATEWAY = SimulatedBankGateway()  # kept for backward compatibility; prefer get_bank_gateway()


def reconcile_bank_statement(file_object, user=None):
    """Reconcile a bank statement CSV (UTR, amount, date) against payments.

    Each row marks the matching payment (by payment reference or, failing
    that, by amount) as PROCESSED + reconciled with the statement's UTR.
    Returns a result dict with matched and unmatched rows.
    """
    from decimal import Decimal, InvalidOperation

    from invoices.models import Invoice

    from .models import PaymentRequest

    text = file_object.read()
    if isinstance(text, bytes):
        text = text.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(io.StringIO(text))
    columns = {((c or '').strip().lower()): c for c in (reader.fieldnames or [])}

    def column(*names):
        for name in names:
            if name in columns:
                return columns[name]
        return None

    utr_col = column('utr', 'utr_number', 'bank_reference', 'reference')
    amount_col = column('amount', 'value', 'paid_amount')
    date_col = column('date', 'value_date', 'payment_date')
    ref_col = column('debit_reference', 'payment_number', 'remarks', 'reference_no')
    if not utr_col or not amount_col:
        raise ValueError('Statement CSV must contain at least "utr" and "amount" columns '
                         '(optionally "date", "debit_reference").')

    matched, unmatched = [], []
    for index, row in enumerate(reader, start=1):
        utr = (row.get(utr_col) or '').strip()
        amount_raw = (row.get(amount_col) or '').replace(',', '').strip()
        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, TypeError):
            amount = None
        if not utr or amount is None:
            unmatched.append({'row': index, 'reason': 'Missing or unparseable UTR/amount.',
                              'raw': {k: row.get(k, '') for k in (row.keys() or [])}})
            continue
        statement_date_raw = (row.get(date_col) or '').strip() if date_col else ''
        statement_date = None
        if statement_date_raw:
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y'):
                try:
                    from datetime import datetime
                    statement_date = datetime.strptime(statement_date_raw, fmt).date()
                    break
                except ValueError:
                    continue

        payment = None
        ref = (row.get(ref_col) or '').strip() if ref_col else ''
        if ref:
            payment = PaymentRequest.objects.filter(payment_number__iexact=ref).first()
        if payment is None:
            # Amount match against actionable payments (most-recent first).
            candidates = PaymentRequest.objects.filter(
                status=PaymentRequest.Status.SCHEDULED, amount=amount) \
                .exclude(is_reconciled=True).order_by('-created_at')
            payment = candidates.first()
        if payment is None:
            unmatched.append({'row': index, 'utr': utr, 'amount': str(amount),
                              'reason': 'No scheduled payment with this reference or amount.'})
            continue

        payment.status = PaymentRequest.Status.PROCESSED
        payment.bank_reference = utr
        payment.processed_date = statement_date or timezone.localdate()
        payment.is_reconciled = True
        payment.reconciled_at = timezone.now()
        payment.save(update_fields=['status', 'bank_reference', 'processed_date',
                                    'is_reconciled', 'reconciled_at', 'updated_at'])
        invoice = payment.invoice
        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=['status', 'paid_at', 'updated_at'])
        if invoice.created_by:
            Notification.objects.create(
                user=invoice.created_by,
                title='Payment reconciled',
                message=f'Payment {payment.payment_number} reconciled from bank statement. UTR: {utr}',
                type=Notification.Types.PAYMENT, link=f'/invoices/{invoice.pk}')
        matched.append({'row': index, 'payment_number': payment.payment_number,
                        'payment_id': payment.pk, 'utr': utr, 'amount': str(amount)})
    logger.info('Bank statement reconciliation: %s matched, %s unmatched', len(matched), len(unmatched))
    return {'matched': matched, 'unmatched': unmatched}


def generate_payment_number():
    from .models import PaymentRequest

    year = timezone.now().year
    prefix = f'PR-{year}-'
    last = (PaymentRequest.objects.filter(payment_number__startswith=prefix)
            .order_by('-payment_number').values_list('payment_number', flat=True).first())
    seq = int(last.split('-')[-1]) + 1 if last else 1
    return f'{prefix}{seq:05d}'


def create_payment(invoice, user, method, scheduled_date=None):
    from .models import PaymentRequest

    from invoices.models import Invoice

    if invoice.status not in (Invoice.Status.APPROVED, Invoice.Status.PAYMENT_FAILED):
        raise ValueError(f'Invoice is in status {invoice.get_status_display()}; '
                         'only approved invoices can be paid.')
    if PaymentRequest.objects.filter(invoice=invoice).exclude(
            status__in=(PaymentRequest.Status.CANCELLED, PaymentRequest.Status.FAILED)).exists():
        raise ValueError('An active payment request already exists for this invoice.')
    if invoice.vendor and not invoice.vendor.bank_accounts.exists():
        raise ValueError('Vendor has no bank account on file.')

    payment = PaymentRequest.objects.create(
        payment_number=generate_payment_number(),
        invoice=invoice,
        amount=invoice.total_amount,
        method=method,
        scheduled_date=scheduled_date,
        status=PaymentRequest.Status.PENDING_APPROVAL,
        requested_by=user,
    )
    invoice.status = Invoice.Status.PAYMENT_REQUESTED
    invoice.save(update_fields=['status', 'updated_at'])
    return payment


def process_payment(payment):
    """Runs the bank gateway; transitions payment + invoice to final states."""
    from accounts.models import Notification

    from invoices.models import Invoice

    from .models import PaymentRequest

    if payment.status not in (PaymentRequest.Status.SCHEDULED, PaymentRequest.Status.FAILED):
        raise ValueError(f'Payment in status {payment.get_status_display()} cannot be processed.')
    payment.status = PaymentRequest.Status.PROCESSED
    payment.failure_reason = ''
    payment.save(update_fields=['status', 'failure_reason'])
    try:
        utr = get_bank_gateway().execute(payment)
        payment.status = PaymentRequest.Status.PROCESSED
        payment.bank_reference = utr
        payment.processed_date = timezone.now().date()
        payment.save(update_fields=['status', 'bank_reference', 'processed_date'])
        payment.invoice.status = Invoice.Status.PAID
        payment.invoice.paid_at = timezone.now()
        payment.invoice.save(update_fields=['status', 'paid_at', 'updated_at'])
        if payment.invoice.created_by:
            Notification.objects.create(
                user=payment.invoice.created_by,
                title='Payment processed',
                message=f'Payment {payment.payment_number} for invoice '
                        f'{payment.invoice.invoice_number or payment.invoice.pk} processed. UTR: {utr}',
                type=Notification.Types.PAYMENT, link=f'/invoices/{payment.invoice_id}')
        return payment
    except BankGatewayError as exc:
        payment.status = PaymentRequest.Status.FAILED
        payment.failure_reason = str(exc)
        payment.save(update_fields=['status', 'failure_reason'])
        payment.invoice.status = Invoice.Status.PAYMENT_FAILED
        payment.invoice.save(update_fields=['status', 'updated_at'])
        logger.warning('Payment %s failed: %s', payment.payment_number, exc)
        return payment


def generate_payment_advice_pdf(payment):
    """Renders the payment advice / remittance advice as a PDF."""
    import io

    from django.conf import settings as s
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from .models import PaymentRequest

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            title=f'Payment Advice {payment.payment_number}')
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(s.COMPANY_NAME, styles['Title']))
    story.append(Paragraph(s.COMPANY_ADDRESS, styles['Normal']))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph('PAYMENT ADVICE / REMITTANCE ADVICE', styles['Heading2']))
    story.append(Spacer(1, 4 * mm))

    invoice = payment.invoice
    vendor = invoice.vendor
    bank = vendor.bank_accounts.filter(is_primary=True).first() or \
        vendor.bank_accounts.first() if vendor else None

    rows = [
        ['Advice number', payment.payment_number],
        ['Payment method', payment.get_method_display()],
        ['Payment status', payment.get_status_display()],
        ['Vendor', f'{vendor.code} - {vendor.name}' if vendor else '-'],
        ['Vendor GSTIN', vendor.gstin if vendor else '-'],
        ['Beneficiary bank', bank.bank_name if bank else '-'],
        ['Account name', bank.account_name if bank else '-'],
        ['Account number', f'XXXX{bank.account_number[-4:]}' if bank else '-'],
        ['IFSC', bank.ifsc if bank else '-'],
        ['Invoice number', invoice.invoice_number or f'#{invoice.pk}'],
        ['Invoice date', str(invoice.invoice_date or '-')],
        ['Invoice amount', f'{invoice.currency} {invoice.total_amount}'],
        ['Scheduled date', str(payment.scheduled_date or '-')],
        ['Processed date', str(payment.processed_date or '-')],
        ['Bank reference (UTR)', payment.bank_reference or '-'],
    ]
    table = Table(rows, colWidths=[60 * mm, 100 * mm])
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#B9C2CC')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8EDF3')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 12 * mm))
    story.append(Paragraph('Authorised signatory: ______________________', styles['Normal']))
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
