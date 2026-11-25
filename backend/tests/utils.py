"""Shared fixtures/helpers for the test suite."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from invoices.models import Invoice
from invoices.services.pipeline import create_invoice_from_file
from purchase_orders.models import GRN, GRNLine, PurchaseOrder
from vendors.models import Vendor, VendorBankAccount
from vendors.services import gstin_checksum

User = get_user_model()

D = Decimal


def make_gstin(state_code='27', pan='AAACS1234F'):
    base14 = f'{state_code}{pan}PZ'
    return base14 + gstin_checksum(base14)


def make_user(username, role, **kwargs):
    defaults = {'email': f'{username}@test.example.com', 'role': role}
    defaults.update(kwargs)
    user = User.objects.create_user(username, password='Test@123', **defaults)
    return user


def make_vendor(code='V-T1', name='Test Vendor Pvt Ltd', state_code='27', status='APPROVED',
                account_number='12345678901'):
    vendor = Vendor.objects.create(
        code=code, name=name, legal_name=name, gstin=make_gstin(state_code),
        pan='AAACS1234F', email=f'{code.lower()}@vendors.example.com',
        phone='9876543210', address_line1='Plot 1', city='Pune', state='Maharashtra',
        state_code=state_code, pincode='411026', status=status,
    )
    VendorBankAccount.objects.create(
        vendor=vendor, account_name=name, account_number=account_number,
        ifsc='HDFC0001234', bank_name='HDFC Bank', branch='Pune', is_primary=True,
        is_verified=status == 'APPROVED',
    )
    return vendor


def make_po(vendor, po_number='PO-T1', lines=None):
    lines = lines or [
        {'description': 'Industrial Valve 2 inch', 'hsn_code': '8481', 'quantity': D('10'),
         'unit': 'NOS', 'unit_price': D('1450'), 'tax_rate': D('18')},
    ]
    po = PurchaseOrder.objects.create(
        po_number=po_number, vendor=vendor, po_date=timezone.localdate(), currency='INR')
    subtotal, tax = D('0'), D('0')
    for idx, line in enumerate(lines, start=1):
        gross = line['quantity'] * line['unit_price']
        subtotal += gross
        tax += gross * line['tax_rate'] / D('100')
        po.lines.create(line_number=idx, description=line['description'],
                        hsn_code=line['hsn_code'], quantity=line['quantity'],
                        unit=line.get('unit', 'NOS'), unit_price=line['unit_price'],
                        tax_rate=line['tax_rate'], line_total=gross)
    po.subtotal = subtotal
    po.tax_amount = tax.quantize(D('0.01'))
    po.total_amount = (subtotal + tax).quantize(D('0.01'))
    po.save()
    return po


def make_grn(po, quantities=None, grn_number='GRN-T1'):
    """quantities: {po_line_id: qty}; default = full receipt of every line."""
    grn = GRN.objects.create(grn_number=grn_number, po=po, receipt_date=timezone.localdate())
    for line in po.lines.all():
        qty = quantities.get(line.pk, line.quantity) if quantities else line.quantity
        GRNLine.objects.create(grn=grn, po_line=line, quantity_received=qty)
        line.received_qty = qty
        line.save(update_fields=['received_qty'])
    po.refresh_receipt_status()
    return grn


def make_invoice_pdf_bytes(vendor_name, vendor_gstin, invoice_number='INV-T9000',
                           po_number='PO-T1'):
    """Minimal valid tax-invoice PDF bytes with a text layer."""
    import io

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(f'{vendor_name}', styles['Title']),
             Paragraph('TAX INVOICE', styles['Heading2']),
             Paragraph(f'GSTIN: {vendor_gstin}', styles['Normal'])]
    rows = [['Invoice Number', invoice_number, 'Invoice Date', '2026-01-10'],
            ['Due Date', '2026-02-10', 'PO Number', po_number]]
    t = Table(rows, colWidths=[40 * mm, 50 * mm, 40 * mm, 50 * mm])
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.grey)]))
    story += [t, Spacer(1, 5 * mm)]
    data = [['Description', 'HSN', 'Qty', 'Unit', 'Rate', 'GST %', 'Amount'],
            ['Industrial Valve 2 inch', '8481', '10', 'NOS', '1,450.00', '18.00%', '14,500.00']]
    t2 = Table(data, colWidths=[62 * mm, 20 * mm, 18 * mm, 15 * mm, 25 * mm, 18 * mm, 22 * mm])
    t2.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.grey)]))
    story += [t2, Spacer(1, 4 * mm)]
    tt = Table([['Taxable Value', '14,500.00'], ['CGST', '1,305.00'], ['SGST', '1,305.00'],
                ['Grand Total', '17,110.00']], colWidths=[80 * mm, 50 * mm], hAlign='RIGHT')
    tt.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.4, colors.grey)]))
    story.append(tt)
    doc.build(story)
    return buffer.getvalue()


def create_uploaded_invoice(vendor, user, invoice_number='INV-T9000', po_number='PO-T1',
                            source=Invoice.Source.UPLOAD):
    """Creates + OCRs a real invoice through the pipeline (synchronous)."""
    pdf_bytes = make_invoice_pdf_bytes(vendor.name, vendor.gstin,
                                       invoice_number=invoice_number, po_number=po_number)
    invoice = create_invoice_from_file(
        ContentFile(pdf_bytes, name=f'{invoice_number}.pdf'), user, source=source)
    from invoices.services.pipeline import process_ocr
    process_ocr(invoice.pk)
    invoice.refresh_from_db()
    return invoice


def make_manual_invoice(vendor, invoice_number='INV-T9000', total=None, po=None,
                        quantity=D('10'), unit_price=D('1450'), tax_rate=D('18'),
                        tax_amount=None, subtotal=None):
    """Creates an invoice + line item directly (bypasses OCR)."""
    from invoices.models import Invoice, InvoiceLineItem

    line_total = quantity * unit_price
    if subtotal is None:
        subtotal = line_total
    if tax_amount is None:
        tax_amount = (line_total * tax_rate / D('100')).quantize(D('0.01'))
    if total is None:
        total = subtotal + tax_amount
    invoice = Invoice.objects.create(
        invoice_number=invoice_number, vendor=vendor, po=po, invoice_date=timezone.localdate(),
        due_date=timezone.localdate(), currency='INR', subtotal=subtotal,
        tax_amount=tax_amount, total_amount=total, ocr_status=Invoice.OcrStatus.COMPLETED,
        status=Invoice.Status.VALIDATED, source=Invoice.Source.MANUAL,
    )
    InvoiceLineItem.objects.create(
        invoice=invoice, line_number=1, description='Industrial Valve 2 inch',
        hsn_code='8481', quantity=quantity, unit='NOS', unit_price=unit_price,
        tax_rate=tax_rate, line_total=line_total,
    )
    return invoice
