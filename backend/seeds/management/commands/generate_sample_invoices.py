"""Generate the sample invoice files in the top-level sample_invoices/ folder.

Creates one file per test scenario so the whole capture -> OCR -> validation
-> matching flow can be exercised without any real vendor data:

  3 valid invoices (one per demo vendor, valid mod-36 GSTINs printed)
  1 duplicate (same vendor + invoice number as a valid one)
  1 wrong-GSTIN invoice (fails the mod-36 check digit)
  1 amount mismatch against a PO (PO-2024-001 from the demo seed)
  1 multi-page PDF
  1 scanned-looking PNG (Tesseract path)
  1 multi-page TIFF (multi-frame OCR path)

The command prints the VALID GSTIN for every generated vendor; create the
vendors in the app with those GSTINs so the valid invoices link correctly.

Custom single invoice:
    python manage.py generate_sample_invoices --vendor-name "Acme Traders" \
        --vendor-pan AABCA1234A --vendor-state-code 27 --po-number PO-2024-001 \
        --line-items '[{"description":"Widget","hsn":"9403","qty":5,"unit":"NOS",
                        "rate":100,"tax_rate":18}]' --invoice-number INV-9001
"""
import json
import os
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from seeds.generators import (generate_invoice_pdf, generate_multipage_invoice_pdf,
                              generate_multipage_invoice_tiff, generate_scanned_invoice_png)
from vendors.services import gstin_checksum

BUYER_NAME = 'Templegate Technologies & Services Pvt. Ltd.'
BUYER_GSTIN = '27AABCT1234A1Z0'

# backend/seeds/management/commands/<this file> -> five levels up = project root
DEFAULT_OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', '..', '..', '..', 'sample_invoices')

TODAY = date.today()

DEMO_VENDORS = [
    {'code': 'V-1001', 'name': 'Shakti Industries Pvt Ltd', 'pan': 'AAACS1234F', 'state_code': '27'},
    {'code': 'V-1002', 'name': 'Metro Office Supplies LLP', 'pan': 'AAGFM5678K', 'state_code': '27'},
    {'code': 'V-1003', 'name': 'TechnoBuild Infra Pvt Ltd', 'pan': 'AACCT9012P', 'state_code': '29'},
]


def make_gstin(state_code, pan):
    """State code + PAN + entity 'P' + 'Z' + valid mod-36 check digit."""
    base14 = f'{(state_code or "27").zfill(2)}{pan.upper()}PZ'
    return base14 + gstin_checksum(base14)


def make_gstin_invalid(state_code, pan):
    """Same format but with a deliberately WRONG check digit."""
    valid = make_gstin(state_code, pan)
    last = valid[-1]
    replacement = '0' if last != '0' else '1'
    return valid[:-1] + replacement


class Command(BaseCommand):
    help = ('Generate sample invoice files (valid, duplicate, wrong GSTIN, PO mismatch, '
            'multi-page PDF, scanned PNG, multi-page TIFF) into sample_invoices/.')

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', default=DEFAULT_OUTPUT,
                            help=f'Target folder (default: {DEFAULT_OUTPUT}).')
        parser.add_argument('--invoice-number', default=None,
                            help='Invoice number for a custom single invoice.')
        parser.add_argument('--vendor-name', default=None,
                            help='Vendor name for a custom single invoice.')
        parser.add_argument('--vendor-pan', default=None,
                            help='PAN of the custom vendor (10 chars).')
        parser.add_argument('--vendor-state-code', default='27',
                            help='GST state code of the custom vendor (default 27).')
        parser.add_argument('--po-number', default='NA',
                            help='PO number printed on the custom invoice.')
        parser.add_argument('--line-items', default=None,
                            help='JSON list of line items: '
                                 '[{"description":"Widget","hsn":"9403","qty":5,'
                                 '"unit":"NOS","rate":100,"tax_rate":18}]')
        parser.add_argument('--gstin-only', action='store_true',
                            help='Only print the valid GSTIN for the given PAN + state code.')

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        pan = (options.get('vendor_pan') or '').upper()
        state_code = options.get('vendor_state_code') or '27'

        if options.get('gstin_only'):
            if not pan or len(pan) != 10:
                raise CommandError('--gstin-only requires --vendor-pan with exactly 10 chars.')
            self.stdout.write(self.style.SUCCESS(make_gstin(state_code, pan)))
            return

        # ---- Custom single invoice --------------------------------------
        if options.get('vendor_name'):
            vendor_name = options['vendor_name']
            pan = pan or 'AABCA1234A'
            gstin = make_gstin(state_code, pan)
            line_items = self._parse_line_items(options.get('line_items'))
            invoice_number = options.get('invoice_number') or 'INV-CUSTOM-001'
            po_number = options.get('po_number') or 'NA'
            output_dir = options['output_dir']
            os.makedirs(output_dir, exist_ok=True)
            path = os.path.join(output_dir, f'{invoice_number.replace("/", "_")}.pdf')
            totals = generate_invoice_pdf(
                path, seller_name=vendor_name, seller_gstin=gstin, seller_state=state_code,
                invoice_number=invoice_number, invoice_date=TODAY - timedelta(days=2),
                due_date=TODAY + timedelta(days=28), po_number=po_number,
                buyer_name=BUYER_NAME, buyer_gstin=BUYER_GSTIN, lines=line_items)
            self._print_vendor_info(vendor_name, state_code, pan, gstin)
            self.stdout.write(self.style.SUCCESS(f'Written: {path} ({totals})'))
            return

        # ---- Full scenario set ------------------------------------------
        output_dir = options['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        vendors = {}
        for vendor in DEMO_VENDORS:
            vendors[vendor['code']] = {**vendor, 'gstin': make_gstin(vendor['state_code'], vendor['pan'])}
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Vendor GSTINs (create vendors with these EXACT values):'))
        for vendor in vendors.values():
            self._print_vendor_info(vendor['name'], vendor['state_code'], vendor['pan'], vendor['gstin'])
        self.stdout.write('')

        today = TODAY
        generated = []

        # 1-3) One VALID invoice per vendor
        valid_sets = [
            ('V-1001', 'INV-S1001', 'PO-2024-001', [
                {'description': 'Industrial Valve 2 inch', 'hsn': '8481', 'qty': 10, 'unit': 'NOS',
                 'rate': 1450, 'tax_rate': 18},
            ]),
            ('V-1002', 'INV-S1002', 'NA', [
                {'description': 'A4 Paper Ream 500 sheets', 'hsn': '4802', 'qty': 50, 'unit': 'BOX',
                 'rate': 210, 'tax_rate': 12},
            ]),
            ('V-1003', 'INV-S1003', 'NA', [
                {'description': 'Vitrified Floor Tiles', 'hsn': '6907', 'qty': 100, 'unit': 'SQM',
                 'rate': 480, 'tax_rate': 18},
            ]),
        ]
        for vendor_code, inv_no, po_no, lines in valid_sets:
            vendor = vendors[vendor_code]
            path = os.path.join(output_dir, f'{inv_no}_{vendor["name"].replace(" ", "_")}.pdf')
            generate_invoice_pdf(path, seller_name=vendor['name'], seller_gstin=vendor['gstin'],
                                 seller_state=vendor['state_code'], invoice_number=inv_no,
                                 invoice_date=today - timedelta(days=5), due_date=today + timedelta(days=25),
                                 po_number=po_no, buyer_name=BUYER_NAME, buyer_gstin=BUYER_GSTIN,
                                 lines=lines)
            scenario = ('valid invoice linked to ' + po_no if po_no != 'NA'
                        else 'valid non-PO invoice')
            generated.append((os.path.basename(path), scenario))

        # 4) Duplicate: same vendor V-1001 + SAME invoice number as INV-S1001
        vendor = vendors['V-1001']
        path = os.path.join(output_dir, 'INV-S1001_DUPLICATE.pdf')
        generate_invoice_pdf(path, seller_name=vendor['name'], seller_gstin=vendor['gstin'],
                             seller_state=vendor['state_code'], invoice_number='INV-S1001',
                             invoice_date=today - timedelta(days=3), due_date=today + timedelta(days=27),
                             po_number='PO-2024-001', buyer_name=BUYER_NAME, buyer_gstin=BUYER_GSTIN,
                             lines=[{'description': 'Industrial Valve 2 inch', 'hsn': '8481',
                                     'qty': 10, 'unit': 'NOS', 'rate': 1450, 'tax_rate': 18}])
        generated.append((os.path.basename(path), 'DUPLICATE of INV-S1001 (fails duplicate check)'))

        # 5) Wrong GSTIN (check digit deliberately invalid)
        wrong_gstin = make_gstin_invalid('27', 'AAAWS9999K')
        path = os.path.join(output_dir, 'INV-S2001_WrongGSTIN.pdf')
        generate_invoice_pdf(path, seller_name='Wavelength Supplies Pvt Ltd', seller_gstin=wrong_gstin,
                             seller_state='27', invoice_number='INV-S2001',
                             invoice_date=today - timedelta(days=4), due_date=today + timedelta(days=26),
                             po_number='NA', buyer_name=BUYER_NAME, buyer_gstin=BUYER_GSTIN,
                             lines=[{'description': 'Whiteboard Markers (Box of 10)', 'hsn': '3215',
                                     'qty': 20, 'unit': 'BOX', 'rate': 350, 'tax_rate': 18}])
        generated.append((os.path.basename(path), 'WRONG GSTIN (fails mod-36 check digit)'))

        # 6) Amount mismatch against PO-2024-001 (demo seed): valid GSTIN, but the
        #    invoiced rate is far above the PO rate -> matching exception.
        vendor = vendors['V-1001']
        path = os.path.join(output_dir, 'INV-S3001_PO_AMOUNT_MISMATCH.pdf')
        generate_invoice_pdf(path, seller_name=vendor['name'], seller_gstin=vendor['gstin'],
                             seller_state=vendor['state_code'], invoice_number='INV-S3001',
                             invoice_date=today - timedelta(days=6), due_date=today + timedelta(days=24),
                             po_number='PO-2024-001', buyer_name=BUYER_NAME, buyer_gstin=BUYER_GSTIN,
                             lines=[{'description': 'Industrial Valve 2 inch', 'hsn': '8481',
                                     'qty': 10, 'unit': 'NOS', 'rate': 2600, 'tax_rate': 18}])
        generated.append((os.path.basename(path), 'AMOUNT MISMATCH against PO-2024-001 (rate inflated)'))

        # 7) Multi-page PDF (2 pages)
        vendor = vendors['V-1003']
        pages = [
            {'lines': [{'description': 'Cement OPC 53 Grade', 'hsn': '2523', 'qty': 200,
                        'unit': 'BAG', 'rate': 385, 'tax_rate': 28}]},
            {'lines': [{'description': 'Vitrified Floor Tiles', 'hsn': '6907', 'qty': 150,
                        'unit': 'SQM', 'rate': 480, 'tax_rate': 18}]},
        ]
        path = os.path.join(output_dir, 'INV-S4001_Multipage.pdf')
        generate_multipage_invoice_pdf(path, pages, seller_name=vendor['name'],
                                       seller_gstin=vendor['gstin'], seller_state=vendor['state_code'],
                                       invoice_number='INV-S4001', invoice_date=today - timedelta(days=7),
                                       due_date=today + timedelta(days=23), po_number='PO-2024-003',
                                       buyer_name=BUYER_NAME, buyer_gstin=BUYER_GSTIN)
        generated.append((os.path.basename(path), 'MULTI-PAGE PDF (2 pages, totals on page 2)'))

        # 8) Scanned-looking PNG
        vendor = vendors['V-1002']
        path = os.path.join(output_dir, 'INV-S5001_Scanned.png')
        generate_scanned_invoice_png(path, seller_name=vendor['name'], seller_gstin=vendor['gstin'],
                                     invoice_number='INV-S5001', invoice_date=str(today - timedelta(days=8)),
                                     due_date=str(today + timedelta(days=22)), po_number='PO-2024-002',
                                     lines=[{'description': 'Ink Cartridge Black', 'hsn': '3215',
                                             'qty': 10, 'rate': 1650, 'tax_rate': 18}], seed=7)
        generated.append((os.path.basename(path), 'SCANNED-LOOK PNG (Tesseract OCR path)'))

        # 9) Multi-page TIFF (3 frames)
        vendor = vendors['V-1001']
        tiff_pages = [
            {'lines': [{'description': 'Hydraulic Pump HX-2', 'hsn': '8413', 'qty': 2,
                        'unit': 'NOS', 'rate': 9800, 'tax_rate': 18}]},
            {'lines': [{'description': 'Gasket Set (Rubber)', 'hsn': '4016', 'qty': 40,
                        'unit': 'SET', 'rate': 220, 'tax_rate': 18}]},
            {'lines': [], 'totals': {'subtotal': 28400, 'tax': 5112, 'total': 33512}},
        ]
        path = os.path.join(output_dir, 'INV-S6001_Multipage.tif')
        frame_count = generate_multipage_invoice_tiff(
            path, tiff_pages, seller_name=vendor['name'], seller_gstin=vendor['gstin'],
            invoice_number='INV-S6001', invoice_date=str(today - timedelta(days=9)),
            due_date=str(today + timedelta(days=21)), po_number='PO-2024-001', seed=11)
        generated.append((os.path.basename(path), f'MULTI-PAGE TIFF ({frame_count} frames)'))

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'Generated {len(generated)} sample file(s) in {output_dir}:'))
        for name, scenario in generated:
            self.stdout.write(f'  {name:42s} {scenario}')
        self.stdout.write('')
        self.stdout.write('Upload them via the UI (drag & drop or "Simulate email"), or run:')
        self.stdout.write(f'  python manage.py ingest_folder "{output_dir}"')

    # ------------------------------------------------------------------
    def _parse_line_items(self, raw):
        if not raw:
            return [{'description': 'Consulting Services', 'hsn': '9983', 'qty': 1,
                     'unit': 'NOS', 'rate': 10000, 'tax_rate': 18}]
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommandError(f'--line-items is not valid JSON: {exc}')
        if not isinstance(items, list) or not items:
            raise CommandError('--line-items must be a non-empty JSON list.')
        cleaned = []
        for item in items:
            cleaned.append({
                'description': str(item.get('description', 'Item'))[:255],
                'hsn': str(item.get('hsn', item.get('hsn_code', '')))[:10],
                'qty': item.get('qty', item.get('quantity', 1)),
                'unit': str(item.get('unit', 'NOS'))[:10],
                'rate': item.get('rate', item.get('unit_price', 0)),
                'tax_rate': item.get('tax_rate', item.get('gst_rate', 18)),
            })
        return cleaned

    def _print_vendor_info(self, name, state_code, pan, gstin):
        self.stdout.write(f'  Vendor "{name}" state {state_code}:')
        self.stdout.write(self.style.SUCCESS(f'    PAN: {pan}   VALID GSTIN: {gstin}'))
