"""Seed the database with realistic demo data through the REAL pipeline.

Everything the seed creates goes through the same services the API uses
(create_invoice_from_file -> OCR -> field identification -> validation ->
matching -> approval workflow -> payments), so the demo is a genuine
end-to-end exercise of the system, not static fixtures.

Usage:
    python manage.py seed_demo            # first run (fails if data exists)
    python manage.py seed_demo --reset    # wipe demo data and reseed
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Notification
from invoices.models import Invoice
from invoices.services import pipeline
from payments.models import PaymentRequest
from payments.services import process_payment
from purchase_orders.models import GRN, GRNLine, PurchaseOrder
from vendors.models import Vendor, VendorBankAccount
from vendors.services import gstin_checksum
from workflow.models import ApprovalMatrix
from workflow.services import act_on_task, start_approval

from seeds.generators import generate_invoice_pdf, generate_scanned_invoice_png

User = get_user_model()
BUYER_GSTIN = '27AABCT1234A1Z0'  # Templegate Maharashtra
BUYER_NAME = 'Templegate Technologies & Services Pvt. Ltd.'

D = Decimal


class Command(BaseCommand):
    help = 'Create demo users, vendors, POs, GRNs and run sample invoices through the real pipeline.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing data first.')

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        if options['reset']:
            self._reset()
        elif Vendor.objects.exists() or User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING(
                'Demo data already present. Use --reset to wipe and reseed.'))
            return

        self._create_users()
        self._create_matrix()
        vendors = self._create_vendors()
        pos = self._create_purchase_orders(vendors)
        self._create_grns(pos)

        self._invoice_8801(pos)   # happy path -> paid
        self._invoice_8802(pos)   # happy path -> paid
        self._invoice_8803(pos)   # 3-way mismatch exception
        self._invoice_8804(pos)   # duplicate exception
        self._invoice_8805(pos)   # scanned PNG -> parallel finance approval pending
        self._invoice_8806(vendors)  # non-PO validated
        self._invoice_8807(pos)   # scanned PNG -> matched (within GRN)
        self._invoice_8808(pos)   # tax inconsistency exception

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))
        self._print_credentials()

    # ------------------------------------------------------------------
    def _reset(self):
        from core.models import AuditLog
        self.stdout.write('Resetting data...')
        PaymentRequest.objects.all().delete()
        Invoice.objects.all().delete()
        GRN.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        Vendor.objects.all().delete()
        ApprovalMatrix.objects.all().delete()
        Notification.objects.all().delete()
        AuditLog.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    def _create_users(self):
        self.stdout.write('Creating users...')
        self.users = {}
        specs = [
            ('admin', 'Admin@123', User.Roles.ADMIN, 'Anita', 'Desai', True),
            ('ap.clerk', 'Clerk@123', User.Roles.AP_CLERK, 'Rahul', 'Verma', False),
            ('approver1', 'Approve@123', User.Roles.APPROVER, 'Sanjay', 'Kulkarni', False),
            ('approver2', 'Approve@123', User.Roles.APPROVER, 'Meera', 'Iyer', False),
            ('finance', 'Finance@123', User.Roles.FINANCE, 'Pooja', 'Nair', False),
            ('finance2', 'Finance@123', User.Roles.FINANCE, 'Arjun', 'Rao', False),
        ]
        for username, password, role, first, last, is_super in specs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username}@templegate.example.com', 'first_name': first,
                          'last_name': last, 'role': role, 'is_staff': is_super, 'is_superuser': is_super},
            )
            user.set_password(password)
            user.role = role
            user.save()
            self.users[username] = user

    def _create_matrix(self):
        self.stdout.write('Creating approval matrix...')
        ApprovalMatrix.objects.create(
            name='Supervisor Approval', level=1, min_amount=D('0'), max_amount=D('50000'),
            approver_role='APPROVER', is_parallel=False, escalation_hours=48)
        ApprovalMatrix.objects.create(
            name='Manager Approval', level=2, min_amount=D('50000.01'), max_amount=D('250000'),
            approver_role='APPROVER', is_parallel=False, escalation_hours=48)
        ApprovalMatrix.objects.create(
            name='Finance Controller (Parallel)', level=3, min_amount=D('250000.01'), max_amount=None,
            approver_role='FINANCE', is_parallel=True, escalation_hours=36)

    def _create_vendors(self):
        self.stdout.write('Creating vendors...')
        specs = [
            ('V-1001', 'Shakti Industries Pvt Ltd', 'AAACS1234F', '27',
             'Plot 14, MIDC Phase 2, Bhosari', 'Pune', 'Maharashtra', '411026', 'APPROVED',
             'accounts@shaktiind.example.com', 'HDFC0001234', 'HDFC Bank', 'Bhosari Branch'),
            ('V-1002', 'Metro Office Supplies LLP', 'AAGFM5678K', '27',
             'Shop 8, Lakshmi Complex, FC Road', 'Pune', 'Maharashtra', '411005', 'APPROVED',
             'sales@metrooffice.example.com', 'ICIC0000456', 'ICICI Bank', 'FC Road Branch'),
            ('V-1003', 'TechnoBuild Infra Pvt Ltd', 'AACCT9012P', '29',
             'Tower B, Prestige Trade Tower, Palace Rd', 'Bengaluru', 'Karnataka', '560001',
             'APPROVED', 'ap@technobuild.example.com', 'KKBK0007788', 'Kotak Mahindra Bank',
             'St. Marks Road Branch'),
            ('V-1004', 'Sunrise Logistics', 'AAXFS3456R', '7',
             'Warehouse 3, Okhla Industrial Area', 'New Delhi', 'Delhi', '110020', 'PENDING_APPROVAL',
             'ops@sunriselog.example.com', 'SBIN0009911', 'State Bank of India', 'Okhla Branch'),
            ('V-1005', 'Nimbus Traders', 'AABCN7890Q', '33',
             '12 Anna Salai, Teynampet', 'Chennai', 'Tamil Nadu', '600018', 'APPROVED',
             'billing@nimbustraders.example.com', 'AXIS0001234', 'Axis Bank', 'Anna Salai Branch'),
        ]
        self.vendors = {}
        admin = self.users['admin']
        for code, name, pan, state_code, addr1, city, state, pin, status, email, ifsc, bank, branch in specs:
            gstin = self._make_gstin(state_code, pan)
            vendor = Vendor.objects.create(
                code=code, name=name, legal_name=name, gstin=gstin, pan=pan, email=email,
                phone='9876543210', address_line1=addr1, city=city, state=state,
                state_code=state_code, pincode=pin, status=status,
                onboarding_notes='Created by demo seed.', created_by=admin,
                approved_by=admin if status == 'APPROVED' else None,
                approved_at=timezone.now() if status == 'APPROVED' else None,
            )
            VendorBankAccount.objects.create(
                vendor=vendor, account_name=name, account_number='12345678901',
                ifsc=ifsc, bank_name=bank, branch=branch, is_primary=True,
                is_verified=status == 'APPROVED')
            self.vendors[code] = vendor
        return self.vendors

    @staticmethod
    def _make_gstin(state_code, pan):
        base14 = f'{state_code}{pan}PZ'  # state + PAN + entity 'P' + 'Z'
        return base14 + gstin_checksum(base14)

    def _create_purchase_orders(self, vendors):
        self.stdout.write('Creating purchase orders...')
        admin = self.users['admin']
        today = timezone.localdate()
        specs = [
            ('PO-2024-001', 'V-1001', today - timedelta(days=45), [
                ('Industrial Valve 2 inch', '8481', D('40'), 'NOS', D('1450'), D('18')),
                ('Gasket Set (Rubber)', '4016', D('100'), 'SET', D('220'), D('18')),
                ('Hydraulic Pump HX-2', '8413', D('2'), 'NOS', D('9800'), D('18')),
            ]),
            ('PO-2024-002', 'V-1002', today - timedelta(days=30), [
                ('A4 Paper Ream 500 sheets', '4802', D('500'), 'BOX', D('210'), D('12')),
                ('Ink Cartridge Black', '3215', D('60'), 'NOS', D('1650'), D('18')),
            ]),
            ('PO-2024-003', 'V-1003', today - timedelta(days=110), [
                ('Cement OPC 53 Grade', '2523', D('600'), 'BAG', D('385'), D('28')),
                ('TMT Steel Bar Fe500 12mm', '7214', D('4'), 'MT', D('52500'), D('18')),
                ('Vitrified Floor Tiles', '6907', D('800'), 'SQM', D('480'), D('18')),
                ('Safety Helmet (ISI)', '6506', D('150'), 'NOS', D('340'), D('12')),
            ]),
            ('PO-2024-004', 'V-1005', today - timedelta(days=25), [
                ('IT AMC Services (Annual)', '9987', D('1'), 'YR', D('240000'), D('18')),
            ]),
        ]
        self.pos = {}
        for po_number, vendor_code, po_date, lines in specs:
            po = PurchaseOrder.objects.create(
                po_number=po_number, vendor=vendors[vendor_code], po_date=po_date,
                currency='INR', notes='Demo purchase order', created_by=admin)
            subtotal, tax = D('0'), D('0')
            for idx, (desc, hsn, qty, unit, rate, tax_rate) in enumerate(lines, start=1):
                gross = qty * rate
                subtotal += gross
                tax += gross * tax_rate / D('100')
                po.lines.create(
                    line_number=idx, description=desc, hsn_code=hsn, quantity=qty, unit=unit,
                    unit_price=rate, tax_rate=tax_rate, line_total=gross)
            po.subtotal = subtotal
            po.tax_amount = tax.quantize(D('0.01'))
            po.total_amount = (subtotal + tax).quantize(D('0.01'))
            po.save()
            self.pos[po_number] = po
        return self.pos

    def _create_grns(self, pos):
        self.stdout.write('Creating GRNs...')
        clerk = self.users['ap.clerk']
        today = timezone.localdate()

        grn = GRN.objects.create(grn_number='GRN-2024-001', po=pos['PO-2024-001'],
                                 receipt_date=today - timedelta(days=40),
                                 remarks='Full receipt against PO-2024-001', received_by=clerk)
        for line in pos['PO-2024-001'].lines.all():
            GRNLine.objects.create(grn=grn, po_line=line, quantity_received=line.quantity)
            line.received_qty = line.quantity
            line.save(update_fields=['received_qty'])
        pos['PO-2024-001'].refresh_receipt_status()

        grn = GRN.objects.create(grn_number='GRN-2024-002', po=pos['PO-2024-003'],
                                 receipt_date=today - timedelta(days=95),
                                 remarks='Partial receipt - balance in transit', received_by=clerk)
        partial = {'Cement OPC 53 Grade': D('400'), 'TMT Steel Bar Fe500 12mm': D('4'),
                   'Vitrified Floor Tiles': D('300'), 'Safety Helmet (ISI)': D('0')}
        for line in pos['PO-2024-003'].lines.all():
            qty = partial.get(line.description, D('0'))
            if qty > 0:
                GRNLine.objects.create(grn=grn, po_line=line, quantity_received=qty)
            line.received_qty = qty
            line.save(update_fields=['received_qty'])

    # ------------------------------------------------------------------
    def _run_capture(self, filename, build_bytes, source=Invoice.Source.UPLOAD):
        content = ContentFile(build_bytes, name=filename)
        invoice = pipeline.create_invoice_from_file(
            content, self.users['ap.clerk'], source=source)
        pipeline.process_ocr(invoice.pk)
        invoice.refresh_from_db()
        return invoice

    def _set_dates(self, invoice, invoice_date, due_date, created_days_ago=None):
        invoice.invoice_date = invoice_date
        invoice.due_date = due_date
        invoice.save(update_fields=['invoice_date', 'due_date'])
        if created_days_ago is not None:
            Invoice.objects.filter(pk=invoice.pk).update(
                created_at=timezone.now() - timedelta(days=created_days_ago))

    def _print_status(self, invoice, label):
        self.stdout.write(f'  {label}: {invoice.invoice_number or "#"+str(invoice.pk)} -> '
                          f'{invoice.get_status_display()} (OCR conf {invoice.ocr_confidence})')

    # ------------------------------------------------------------------
    def _invoice_8801(self, pos):
        today = timezone.localdate()
        lines = [
            {'description': 'Industrial Valve 2 inch', 'hsn': '8481', 'qty': D('40'), 'unit': 'NOS',
             'rate': D('1450'), 'tax_rate': D('18')},
            {'description': 'Gasket Set (Rubber)', 'hsn': '4016', 'qty': D('100'), 'unit': 'SET',
             'rate': D('220'), 'tax_rate': D('18')},
            {'description': 'Hydraulic Pump HX-2', 'hsn': '8413', 'qty': D('2'), 'unit': 'NOS',
             'rate': D('9800'), 'tax_rate': D('18')},
        ]
        totals = self._build_pdf('INV-8801', 'V-1001', 'PO-2024-001', lines, today - timedelta(days=41), today - timedelta(days=11))
        invoice = self._run_capture('INV-8801.pdf', totals['bytes'])
        self._set_dates(invoice, today - timedelta(days=41), today - timedelta(days=11), created_days_ago=12)
        self._approve_and_pay(invoice, 'NEFT')
        self._print_status(invoice, '8801 happy path')

    def _invoice_8802(self, pos):
        today = timezone.localdate()
        lines = [
            {'description': 'A4 Paper Ream 500 sheets', 'hsn': '4802', 'qty': D('500'), 'unit': 'BOX',
             'rate': D('210'), 'tax_rate': D('12')},
            {'description': 'Ink Cartridge Black', 'hsn': '3215', 'qty': D('60'), 'unit': 'NOS',
             'rate': D('1650'), 'tax_rate': D('18')},
        ]
        totals = self._build_pdf('INV-8802', 'V-1002', 'PO-2024-002', lines, today - timedelta(days=29), today + timedelta(days=1))
        invoice = self._run_capture('INV-8802.pdf', totals['bytes'])
        self._set_dates(invoice, today - timedelta(days=29), today + timedelta(days=1), created_days_ago=6)
        self._approve_and_pay(invoice, 'RTGS')
        self._print_status(invoice, '8802 happy path')

    def _invoice_8803(self, pos):
        """Invoices more tiles than were received -> 3-way mismatch exception."""
        today = timezone.localdate()
        lines = [
            {'description': 'Cement OPC 53 Grade', 'hsn': '2523', 'qty': D('400'), 'unit': 'BAG',
             'rate': D('385'), 'tax_rate': D('28')},
            {'description': 'Vitrified Floor Tiles', 'hsn': '6907', 'qty': D('800'), 'unit': 'SQM',
             'rate': D('480'), 'tax_rate': D('18')},
        ]
        totals = self._build_pdf('INV-8803', 'V-1003', 'PO-2024-003', lines, today - timedelta(days=98), today - timedelta(days=98))
        invoice = self._run_capture('INV-8803.pdf', totals['bytes'])
        self._set_dates(invoice, today - timedelta(days=98), today - timedelta(days=98), created_days_ago=90)
        self._print_status(invoice, '8803 3-way exception')

    def _invoice_8804(self, pos):
        """Duplicate of INV-8801 -> duplicate validation exception."""
        today = timezone.localdate()
        lines = [
            {'description': 'Industrial Valve 2 inch', 'hsn': '8481', 'qty': D('40'), 'unit': 'NOS',
             'rate': D('1450'), 'tax_rate': D('18')},
        ]
        totals = self._build_pdf('INV-8801', 'V-1001', 'PO-2024-001', lines, today - timedelta(days=40), today - timedelta(days=10))
        invoice = self._run_capture('INV-8804.pdf', totals['bytes'])
        self._set_dates(invoice, today - timedelta(days=40), today - timedelta(days=10), created_days_ago=3)
        self._print_status(invoice, '8804 duplicate exception')

    def _invoice_8805(self, pos):
        """Scanned PNG invoice -> clerk review -> parallel finance approval (pending)."""
        today = timezone.localdate()
        vendor = self.vendors['V-1005']
        lines = [
            {'description': 'IT AMC Services (Annual)', 'hsn': '9987', 'qty': D('1'), 'unit': 'YR',
             'rate': D('240000'), 'tax_rate': D('18')},
        ]
        png_bytes = self._build_png('INV-8805', vendor, 'PO-2024-004', lines,
                                    today - timedelta(days=70), today - timedelta(days=10))
        invoice = self._run_capture('INV-8805.png', png_bytes)
        self._review(invoice, vendor, 'PO-2024-004', lines,
                     today - timedelta(days=70), today - timedelta(days=10))
        self._set_dates(invoice, today - timedelta(days=70), today - timedelta(days=10), created_days_ago=60)
        tasks = start_approval(invoice, self.users['ap.clerk'])
        self.stdout.write(f'  8805 parallel approval tasks: {len(tasks)}')
        self._print_status(invoice, '8805 parallel approval pending')

    def _invoice_8806(self, vendors):
        """Non-PO expense invoice -> validated, awaiting submission."""
        today = timezone.localdate()
        lines = [
            {'description': 'A4 Paper Ream 500 sheets', 'hsn': '4802', 'qty': D('100'), 'unit': 'BOX',
             'rate': D('210'), 'tax_rate': D('12')},
            {'description': 'Heavy Duty Stapler', 'hsn': '8472', 'qty': D('5'), 'unit': 'NOS',
             'rate': D('450'), 'tax_rate': D('18')},
        ]
        totals = self._build_pdf('INV-77301', 'V-1002', None, lines, today - timedelta(days=5), today + timedelta(days=25))
        invoice = self._run_capture('INV-77301.pdf', totals['bytes'])
        self._set_dates(invoice, today - timedelta(days=5), today + timedelta(days=25), created_days_ago=4)
        self._print_status(invoice, '8806 non-PO validated')

    def _invoice_8807(self, pos):
        """Scanned PNG invoice within received quantities -> matched."""
        today = timezone.localdate()
        vendor = self.vendors['V-1003']
        lines = [
            {'description': 'Cement OPC 53 Grade', 'hsn': '2523', 'qty': D('400'), 'unit': 'BAG',
             'rate': D('385'), 'tax_rate': D('28')},
            {'description': 'Vitrified Floor Tiles', 'hsn': '6907', 'qty': D('300'), 'unit': 'SQM',
             'rate': D('480'), 'tax_rate': D('18')},
        ]
        png_bytes = self._build_png('INV-8807', vendor, 'PO-2024-003', lines,
                                    today - timedelta(days=90), today - timedelta(days=30))
        invoice = self._run_capture('INV-8807.png', png_bytes)
        self._review(invoice, vendor, 'PO-2024-003', lines,
                     today - timedelta(days=90), today - timedelta(days=30))
        self._set_dates(invoice, today - timedelta(days=90), today - timedelta(days=30), created_days_ago=80)
        self._print_status(invoice, '8807 matched (3-way)')

    def _invoice_8808(self, pos):
        """OCR misread of tax -> amount validation exception (clerk must correct)."""
        today = timezone.localdate()
        lines = [
            {'description': 'Gasket Set (Rubber)', 'hsn': '4016', 'qty': D('60'), 'unit': 'SET',
             'rate': D('220'), 'tax_rate': D('18')},
        ]
        totals = self._build_pdf('INV-8808', 'V-1001', 'PO-2024-001', lines, today - timedelta(days=45), today - timedelta(days=15))
        invoice = self._run_capture('INV-8808.pdf', totals['bytes'])
        # Simulate an OCR misread of the tax figure
        if invoice.tax_amount:
            invoice.tax_amount = invoice.tax_amount + D('1500.00')
            invoice.save(update_fields=['tax_amount'])
            from invoices.services.validation import run_validation
            run_validation(invoice)
        self._set_dates(invoice, today - timedelta(days=45), today - timedelta(days=15), created_days_ago=20)
        self._print_status(invoice, '8808 tax exception')

    # ------------------------------------------------------------------
    def _build_pdf(self, invoice_number, vendor_code, po_number, lines, invoice_date, due_date):
        vendor = self.vendors[vendor_code]
        import io

        buffer = io.BytesIO()
        po_str = po_number or ''
        # generate into the buffer-backed path via a temp file
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'invoice.pdf')
            totals = generate_invoice_pdf(
                path,
                seller_name=vendor.name, seller_gstin=vendor.gstin, seller_state=vendor.state_code,
                invoice_number=invoice_number, invoice_date=invoice_date, due_date=due_date,
                po_number=po_str, buyer_name=BUYER_NAME, buyer_gstin=BUYER_GSTIN, lines=lines)
            with open(path, 'rb') as fh:
                buffer.write(fh.read())
        totals['bytes'] = buffer.getvalue()
        return totals

    def _build_png(self, invoice_number, vendor, po_number, lines, invoice_date, due_date):
        import io
        import os
        import tempfile

        buffer = io.BytesIO()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'invoice.png')
            generate_scanned_invoice_png(
                path, seller_name=vendor.name, seller_gstin=vendor.gstin,
                invoice_number=invoice_number, invoice_date=str(invoice_date),
                due_date=str(due_date), po_number=po_number or 'NA',
                lines=[{**line, 'rate': float(line['rate'])} for line in lines])
            with open(path, 'rb') as fh:
                buffer.write(fh.read())
        return buffer.getvalue()

    def _review(self, invoice, vendor, po_number, lines, invoice_date, due_date):
        subtotal = sum(line['qty'] * line['rate'] for line in lines)
        tax = sum(line['qty'] * line['rate'] * line['tax_rate'] / D('100') for line in lines)
        from invoices.services.pipeline import apply_reviewed_fields
        apply_reviewed_fields(invoice, {
            'invoice_number': invoice.invoice_number or 'UNKNOWN',
            'vendor_id': vendor.pk,
            'po_number': po_number or '',
            'invoice_date': str(invoice_date),
            'due_date': str(due_date),
            'subtotal': str(subtotal),
            'tax_amount': str(tax.quantize(D('0.01'))),
            'total_amount': str((subtotal + tax).quantize(D('0.01'))),
            'line_items': [
                {'description': line['description'], 'hsn_code': line['hsn'],
                 'quantity': str(line['qty']), 'unit': line['unit'],
                 'unit_price': str(line['rate']), 'tax_rate': str(line['tax_rate'])}
                for line in lines
            ],
        })
        invoice.refresh_from_db()

    def _approve_and_pay(self, invoice, method):
        today = timezone.localdate()
        tasks = start_approval(invoice, self.users['ap.clerk'])
        for task in tasks:
            approver = task.approver or self.users['approver1']
            act_on_task(task, approver, 'approve', comments='Verified against PO and GRN (seed demo).')
        invoice.refresh_from_db()
        from payments.services import create_payment
        payment = create_payment(invoice, self.users['finance'], method)
        payment.status = PaymentRequest.Status.APPROVED
        payment.approved_by = self.users['finance']
        payment.save(update_fields=['status', 'approved_by'])
        payment.scheduled_date = today
        payment.status = PaymentRequest.Status.SCHEDULED
        payment.save(update_fields=['scheduled_date', 'status'])
        invoice.status = Invoice.Status.SCHEDULED
        invoice.save(update_fields=['status'])
        process_payment(payment)
        invoice.refresh_from_db()

    def _print_credentials(self):
        self.stdout.write('')
        self.stdout.write('Demo accounts (password shown after each):')
        for username, password in [('admin', 'Admin@123'), ('ap.clerk', 'Clerk@123'),
                                   ('approver1', 'Approve@123'), ('approver2', 'Approve@123'),
                                   ('finance', 'Finance@123'), ('finance2', 'Finance@123')]:
            self.stdout.write(f'  {username} / {password}')
        self.stdout.write('')
        self.stdout.write('Status mix: 2 PAID, 1 PENDING_APPROVAL (parallel), 1 VALIDATED (non-PO),')
        self.stdout.write('            1 MATCHED, 1 MATCH_EXCEPTION, 1 duplicate EXCEPTION, 1 tax EXCEPTION')
