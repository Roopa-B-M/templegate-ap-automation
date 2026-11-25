#!/usr/bin/env python
"""Make a single test invoice file (PDF/PNG/TIFF) for exercising the pipeline.

This standalone script wraps the same generators the demo seeder and the
`generate_sample_invoices` command use, so you can craft one-off invoices
without touching the database.

Usage (from anywhere, Python 3.11+ with the backend requirements installed):

    # Single invoice for a vendor (prints the VALID GSTIN to create the vendor with)
    python scripts/make_test_invoice.py --vendor-name "Acme Traders" \
        --vendor-pan AABCA1234A --vendor-state-code 27 --po-number PO-2024-001 \
        --line-items '[{"description":"Widget","hsn":"9403","qty":5,"unit":"NOS",
                        "rate":100,"tax_rate":18}]' \
        --invoice-number INV-TEST-001 --output out/INV-TEST-001.pdf

    # Just print the valid GSTIN for a PAN + state code
    python scripts/make_test_invoice.py --gstin-only --vendor-pan AABCA1234A

    # Scanned-look PNG instead of a text-layer PDF
    python scripts/make_test_invoice.py --format png --output out/scan.png

Requires DJANGO_SETTINGS_MODULE-compatible environment only when importing the
generators: the script adds the backend folder to sys.path automatically.
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
sys.path.insert(0, BACKEND_DIR)

BUYER_NAME = 'Templegate Technologies & Services Pvt. Ltd.'
BUYER_GSTIN = '27AABCT1234A1Z0'


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--invoice-number', default='INV-TEST-001')
    parser.add_argument('--vendor-name', default='Acme Traders Pvt Ltd')
    parser.add_argument('--vendor-pan', default='AABCA1234A', help='10-character PAN.')
    parser.add_argument('--vendor-state-code', default='27')
    parser.add_argument('--po-number', default='NA')
    parser.add_argument('--line-items', default=None,
                        help='JSON list: [{"description":"Widget","hsn":"9403","qty":5,'
                             '"unit":"NOS","rate":100,"tax_rate":18}]')
    parser.add_argument('--format', choices=('pdf', 'png', 'tiff'), default='pdf',
                        help='Output document type (default pdf).')
    parser.add_argument('--pages', type=int, default=1,
                        help='Number of pages (PDF/TIFF only, default 1).')
    parser.add_argument('--gstin-only', action='store_true',
                        help='Print the valid GSTIN for --vendor-pan/--vendor-state-code and exit.')
    parser.add_argument('--output', default=None,
                        help='Output path (default: sample_invoices/make_test_invoice_<n>.<ext>).')
    return parser.parse_args()


def main():
    args = parse_args()

    from vendors.services import gstin_checksum  # noqa: E402 (path set above)

    state_code = args.vendor_state_code or '27'
    pan = (args.vendor_pan or 'AABCA1234A').upper()
    base14 = f'{state_code.zfill(2)}{pan}PZ'
    gstin = base14 + gstin_checksum(base14)

    if args.gstin_only:
        print(gstin)
        return

    line_items = [{'description': 'Consulting Services', 'hsn': '9983', 'qty': 1,
                   'unit': 'NOS', 'rate': 10000, 'tax_rate': 18}]
    if args.line_items:
        line_items = json.loads(args.line_items)

    output = args.output or os.path.join(BASE_DIR, 'sample_invoices',
                                         f'{args.invoice_number.replace("/", "_")}.{args.format}')
    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)

    today = date.today()
    invoice_date = today - timedelta(days=2)
    due_date = today + timedelta(days=28)

    if args.format == 'pdf':
        from seeds.generators import generate_invoice_pdf, generate_multipage_invoice_pdf

        pages = max(1, args.pages)
        if pages == 1:
            totals = generate_invoice_pdf(
                output, seller_name=args.vendor_name, seller_gstin=gstin,
                seller_state=state_code, invoice_number=args.invoice_number,
                invoice_date=invoice_date, due_date=due_date, po_number=args.po_number,
                buyer_name=BUYER_NAME, buyer_gstin=BUYER_GSTIN, lines=line_items)
        else:
            # Spread the items over N pages, totals computed across all pages.
            chunk = max(1, -(-len(line_items) // pages))
            page_lines = [line_items[i:i + chunk] for i in range(0, len(line_items), chunk)] or [[]]
            totals = generate_multipage_invoice_pdf(
                output, [{'lines': lines} for lines in page_lines],
                seller_name=args.vendor_name, seller_gstin=gstin, seller_state=state_code,
                invoice_number=args.invoice_number, invoice_date=invoice_date,
                due_date=due_date, po_number=args.po_number,
                buyer_name=BUYER_NAME, buyer_gstin=BUYER_GSTIN)
        print(f'Written {output}  totals={dict(totals)}')
    elif args.format == 'png':
        from seeds.generators import generate_scanned_invoice_png

        generate_scanned_invoice_png(
            output, seller_name=args.vendor_name, seller_gstin=gstin,
            invoice_number=args.invoice_number, invoice_date=str(invoice_date),
            due_date=str(due_date), po_number=args.po_number,
            lines=[{'description': li['description'], 'hsn': li.get('hsn', ''),
                    'qty': li.get('qty', 1), 'rate': li.get('rate', 0),
                    'tax_rate': li.get('tax_rate', 18)} for li in line_items])
        print(f'Written {output}')
    else:  # tiff
        from seeds.generators import generate_multipage_invoice_tiff

        pages = max(1, args.pages)
        page_lines = [line_items] if pages == 1 else [line_items, [], []][:pages]
        frames = generate_multipage_invoice_tiff(
            output, [{'lines': lines} for lines in page_lines],
            seller_name=args.vendor_name, seller_gstin=gstin,
            invoice_number=args.invoice_number, invoice_date=str(invoice_date),
            due_date=str(due_date), po_number=args.po_number)
        print(f'Written {output} ({frames} frame(s))')

    print(f'Vendor GSTIN to use when creating "{args.vendor_name}": {gstin}')


if __name__ == '__main__':
    main()
