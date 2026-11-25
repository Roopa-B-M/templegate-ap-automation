"""Sample invoice document generators used by the seed command.

They create realistic, machine-readable TAX INVOICE PDFs (with a real text
layer and table so pdfplumber extracts them) and scanned-look PNG images
(for the Tesseract path). This is what the OCR engine consumes in the demo.
"""
import io
import random
from decimal import Decimal

from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_invoice_pdf(path, *, seller_name, seller_gstin, seller_state, invoice_number,
                         invoice_date, due_date, po_number, buyer_name, buyer_gstin,
                         lines, notes=''):
    """lines: [{description, hsn, qty, rate, tax_rate}] (numbers or Decimals)"""
    lines = [{'description': str(l.get('description', '')),
              'hsn': str(l.get('hsn', '')),
              'qty': Decimal(str(l.get('qty', 1))),
              'unit': str(l.get('unit', 'NOS')),
              'rate': Decimal(str(l.get('rate', 0))),
              'tax_rate': Decimal(str(l.get('tax_rate', 0)))}
             for l in lines]
    subtotal = Decimal('0')
    tax = Decimal('0')
    for line in lines:
        gross = line['qty'] * line['rate']
        subtotal += gross
        tax += gross * line['tax_rate'] / 100
    total = subtotal + tax

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            title=f'Tax Invoice {invoice_number}')
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f'<b>{seller_name}</b>', styles['Title']))
    story.append(Paragraph('TAX INVOICE', styles['Heading2']))
    story.append(Paragraph(f'GSTIN: {seller_gstin} | State code: {seller_state}', styles['Normal']))

    header_rows = [
        ['Invoice Number', invoice_number, 'Invoice Date', str(invoice_date)],
        ['Due Date', str(due_date), 'Purchase Order', po_number],
        ['Buyer', buyer_name, 'Buyer GSTIN', buyer_gstin],
    ]
    header_table = Table(header_rows, colWidths=[35 * mm, 55 * mm, 40 * mm, 50 * mm])
    header_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#999999')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 5 * mm))

    data = [['Description', 'HSN', 'Qty', 'Unit', 'Rate', 'GST %', 'Amount']]
    for line in lines:
        gross = line['qty'] * line['rate']
        data.append([line['description'], line['hsn'], str(line['qty']), line['unit'],
                     f"{line['rate']:,.2f}", f"{line['tax_rate']:.2f}%", f'{gross:,.2f}'])
    items_table = Table(data, colWidths=[62 * mm, 20 * mm, 18 * mm, 15 * mm, 25 * mm, 18 * mm, 22 * mm])
    items_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#777777')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D8E2EC')),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 4 * mm))

    totals_rows = [['Taxable Value', f'{subtotal:,.2f}']]
    if seller_state == '27':
        totals_rows.append(['CGST', f'{tax / 2:,.2f}'])
        totals_rows.append(['SGST', f'{tax / 2:,.2f}'])
    else:
        totals_rows.append(['IGST', f'{tax:,.2f}'])
    totals_rows.append(['Grand Total', f'{total:,.2f}'])
    totals_table = Table(totals_rows, colWidths=[80 * mm, 50 * mm], hAlign='RIGHT')
    totals_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#777777')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 4 * mm))
    if notes:
        story.append(Paragraph(f'Notes: {notes}', styles['Normal']))

    doc.build(story)
    with open(path, 'wb') as fh:
        fh.write(buffer.getvalue())
    return {'subtotal': subtotal, 'tax': tax, 'total': total}


def generate_scanned_invoice_png(path, *, seller_name, seller_gstin, invoice_number,
                                 invoice_date, due_date, po_number, lines, seed=1):
    """Renders a slightly noisy invoice image to exercise the Tesseract path."""
    rng = random.Random(seed)
    width, height = 1240, 1600
    img = Image.new('L', (width, height), 245)
    draw = ImageDraw.Draw(img)

    def txt(x, y, text, size=28):
        try:
            from PIL import ImageFont
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size)
        except Exception:
            font = None
        jitter_x = x + rng.randint(-1, 1)
        draw.text((jitter_x, y), text, fill=25, font=font)

    txt(60, 50, seller_name, 40)
    txt(60, 105, f'GSTIN: {seller_gstin}', 26)
    txt(760, 50, 'TAX INVOICE', 44)
    txt(60, 190, f'Invoice No: {invoice_number}')
    txt(60, 235, f'Invoice Date: {invoice_date}')
    txt(60, 280, f'Due Date: {due_date}')
    txt(60, 325, f'PO Number: {po_number}')

    y = 420
    txt(60, y, 'Description')
    txt(600, y, 'HSN')
    txt(700, y, 'Qty')
    txt(830, y, 'Rate')
    txt(990, y, 'GST%')
    txt(1090, y, 'Amount')
    y += 50
    for line in lines:
        gross = Decimal(str(line['qty'])) * Decimal(str(line['rate']))
        txt(60, y, str(line['description'])[:36], 24)
        txt(600, y, str(line['hsn']), 24)
        txt(700, y, str(line['qty']), 24)
        txt(830, y, f"{line['rate']:,.2f}", 24)
        txt(990, y, f"{line['tax_rate']:.0f}%", 24)
        txt(1090, y, f'{gross:,.2f}', 24)
        y += 45

    y += 20
    subtotal = sum(Decimal(str(line['qty'])) * Decimal(str(line['rate'])) for line in lines)
    tax = subtotal * Decimal('18') / 100
    txt(830, y, 'Subtotal:', 26)
    txt(1090, y, f'{subtotal:,.2f}', 26)
    y += 45
    txt(830, y, 'CGST 9%:', 26)
    txt(1090, y, f'{tax / 2:,.2f}', 26)
    y += 45
    txt(830, y, 'SGST 9%:', 26)
    txt(1090, y, f'{tax / 2:,.2f}', 26)
    y += 45
    txt(830, y, 'Grand Total:', 28)
    txt(1090, y, f'{subtotal + tax:,.2f}', 28)

    # light noise so the image genuinely looks scanned
    for _ in range(1800):
        x, yy = rng.randint(0, width - 1), rng.randint(0, height - 1)
        draw.point((x, yy), fill=rng.randint(180, 225))
    img.save(path, 'PNG')


def generate_scanned_invoice_pages(pages, *, seller_name, seller_gstin, invoice_number,
                                   invoice_date, due_date, po_number, seed=1):
    """Render N scanned-look invoice pages (PIL images, not yet saved).

    pages: list of dicts [{lines: [...], totals: {subtotal, tax, total} | None}]
    """
    images = []
    for page_no, page in enumerate(pages, start=1):
        rng = random.Random(seed + page_no)
        width, height = 1240, 1600
        img = Image.new('L', (width, height), 245)
        draw = ImageDraw.Draw(img)

        def txt(x, y, text, size=28):
            try:
                from PIL import ImageFont
                font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size)
            except Exception:
                font = None
            jitter_x = x + rng.randint(-1, 1)
            draw.text((jitter_x, y), text, fill=25, font=font)

        page_label = f' - Page {page_no} of {len(pages)}' if len(pages) > 1 else ''
        txt(60, 50, seller_name, 40)
        txt(60, 105, f'GSTIN: {seller_gstin}', 26)
        txt(760, 50, 'TAX INVOICE', 44)
        txt(60, 190, f'Invoice No: {invoice_number}')
        txt(60, 235, f'Invoice Date: {invoice_date}')
        txt(60, 280, f'Due Date: {due_date}')
        txt(60, 325, f'PO Number: {po_number}')

        y = 420
        if page.get('lines'):
            txt(60, y, 'Description')
            txt(600, y, 'HSN')
            txt(700, y, 'Qty')
            txt(830, y, 'Rate')
            txt(990, y, 'GST%')
            txt(1090, y, 'Amount')
            y += 50
            for line in page['lines']:
                gross = Decimal(str(line['qty'])) * Decimal(str(line['rate']))
                txt(60, y, str(line['description'])[:36], 24)
                txt(600, y, str(line['hsn']), 24)
                txt(700, y, str(line['qty']), 24)
                txt(830, y, f"{line['rate']:,.2f}", 24)
                txt(990, y, f"{line['tax_rate']:.0f}%", 24)
                txt(1090, y, f'{gross:,.2f}', 24)
                y += 45
        if page.get('totals'):
            totals = page['totals']
            y += 20
            txt(830, y, 'Subtotal:', 26)
            txt(1090, y, f"{Decimal(str(totals['subtotal'])):,.2f}", 26)
            y += 45
            txt(830, y, 'CGST 9%:', 26)
            txt(1090, y, f"{Decimal(str(totals['tax'])) / 2:,.2f}", 26)
            y += 45
            txt(830, y, 'SGST 9%:', 26)
            txt(1090, y, f"{Decimal(str(totals['tax'])) / 2:,.2f}", 26)
            y += 45
            txt(830, y, 'Grand Total:', 28)
            txt(1090, y, f"{Decimal(str(totals['total'])):,.2f}", 28)
        else:
            txt(60, y + 60, f'Continued on next page{page_label}', 24)

        # light noise so the image genuinely looks scanned
        for _ in range(1400):
            x, yy = rng.randint(0, width - 1), rng.randint(0, height - 1)
            draw.point((x, yy), fill=rng.randint(180, 225))
        images.append(img.convert('RGB'))
    return images


def generate_multipage_invoice_tiff(path, pages, *, seller_name, seller_gstin,
                                    invoice_number, invoice_date, due_date, po_number, seed=1):
    """Render a multi-page (multi-frame) TIFF from scanned-look pages."""
    images = generate_scanned_invoice_pages(
        pages, seller_name=seller_name, seller_gstin=seller_gstin,
        invoice_number=invoice_number, invoice_date=invoice_date, due_date=due_date,
        po_number=po_number, seed=seed)
    images[0].save(path, format='TIFF', save_all=True, append_images=images[1:],
                   compression='tiff_lzw')
    return len(images)


def generate_multipage_invoice_pdf(path, pages, *, seller_name, seller_gstin, seller_state,
                                   invoice_number, invoice_date, due_date, po_number,
                                   buyer_name, buyer_gstin):
    """Render a multi-page PDF invoice: each page dict carries its own lines.

    pages: [{lines: [...]}] - totals are computed across ALL pages and printed
    on the final page. A PageBreak separates the pages.
    """
    from reportlab.platypus import PageBreak

    pages = [{'lines': [{'description': str(l.get('description', '')),
                         'hsn': str(l.get('hsn', '')),
                         'qty': Decimal(str(l.get('qty', 1))),
                         'unit': str(l.get('unit', 'NOS')),
                         'rate': Decimal(str(l.get('rate', 0))),
                         'tax_rate': Decimal(str(l.get('tax_rate', 0)))}
                        for l in page.get('lines', [])]}
             for page in pages]
    subtotal = Decimal('0')
    tax = Decimal('0')
    for page in pages:
        for line in page['lines']:
            gross = line['qty'] * line['rate']
            subtotal += gross
            tax += gross * line['tax_rate'] / 100
    total = subtotal + tax

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            title=f'Tax Invoice {invoice_number}')
    styles = getSampleStyleSheet()
    story = []
    for page_no, page in enumerate(pages, start=1):
        story.append(Paragraph(f'<b>{seller_name}</b>', styles['Title']))
        story.append(Paragraph('TAX INVOICE', styles['Heading2']))
        story.append(Paragraph(f'GSTIN: {seller_gstin} | State code: {seller_state}', styles['Normal']))
        if len(pages) > 1:
            story.append(Paragraph(f'Page {page_no} of {len(pages)}', styles['Normal']))
        header_rows = [
            ['Invoice Number', invoice_number, 'Invoice Date', str(invoice_date)],
            ['Due Date', str(due_date), 'Purchase Order', po_number],
            ['Buyer', buyer_name, 'Buyer GSTIN', buyer_gstin],
        ]
        header_table = Table(header_rows, colWidths=[35 * mm, 55 * mm, 40 * mm, 50 * mm])
        header_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#999999')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 5 * mm))
        data = [['Description', 'HSN', 'Qty', 'Unit', 'Rate', 'GST %', 'Amount']]
        for line in page['lines']:
            gross = line['qty'] * line['rate']
            data.append([line['description'], line['hsn'], str(line['qty']), line['unit'],
                         f"{line['rate']:,.2f}", f"{line['tax_rate']:.2f}%", f'{gross:,.2f}'])
        items_table = Table(data, colWidths=[62 * mm, 20 * mm, 18 * mm, 15 * mm, 25 * mm, 18 * mm, 22 * mm])
        items_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#777777')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D8E2EC')),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ]))
        story.append(items_table)
        if page_no == len(pages):
            story.append(Spacer(1, 4 * mm))
            totals_rows = [['Taxable Value', f'{subtotal:,.2f}']]
            if seller_state == '27':
                totals_rows.append(['CGST', f'{tax / 2:,.2f}'])
                totals_rows.append(['SGST', f'{tax / 2:,.2f}'])
            else:
                totals_rows.append(['IGST', f'{tax:,.2f}'])
            totals_rows.append(['Grand Total', f'{total:,.2f}'])
            totals_table = Table(totals_rows, colWidths=[80 * mm, 50 * mm], hAlign='RIGHT')
            totals_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#777777')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))
            story.append(totals_table)
        if page_no < len(pages):
            story.append(PageBreak())

    doc.build(story)
    with open(path, 'wb') as fh:
        fh.write(buffer.getvalue())
    return {'subtotal': subtotal, 'tax': tax, 'total': total}
