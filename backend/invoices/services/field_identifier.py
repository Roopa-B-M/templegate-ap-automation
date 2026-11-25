"""Rule-based field identification engine (deterministic, no external calls).

Turns raw OCR text (+ extracted table structures) into structured invoice
data with a confidence score per field. The scorer is an ensemble of:

1. Label proximity patterns (highest confidence, e.g. "Invoice No: ABC").
2. Regex format matchers (GSTIN, PAN, PO number, Indian amount formats).
3. Cross-field consistency checks (subtotal + tax == total boosts trust).

Line items are detected from PDF table structures first (pdfplumber),
falling back to a columnar layout scan of the OCR text.

An OPTIONAL AI assist for low-confidence/missing-field cases lives in
ai_extract.py; it is disabled by default (AI_EXTRACTION_PROVIDER=none).
"""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

GSTIN_RE = re.compile(r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z])\b')
PAN_RE = re.compile(r'\b([A-Z]{5}[0-9]{4}[A-Z])\b')
PO_RE = re.compile(r'\b(?:P\.?O\.?|PURCHASE\s+ORDER)\s*(?:NUMBER|NO\.?|#)?\s*[:#]?\s*'
                   r'(?=[A-Z0-9\-/_\.]*[0-9])([A-Z0-9][A-Z0-9\-/_\.]{2,20})\b', re.I)
INVOICE_NO_RE = re.compile(r'\b(INV|TAX\s*INV|INVOICE)\s*#?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/_\.]{2,24})\b')
AMOUNT_RE = re.compile(r'(?:Rs\.?|INR|\u20b9)?\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})|[0-9]+\.[0-9]{1,2})')
PERCENT_RE = re.compile(r'([0-9]+(?:\.[0-9]+)?)\s*%')

DATE_FORMATS = ('%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d',
                '%d %b %Y', '%d %B %Y', '%d-%b-%Y', '%d-%B-%Y', '%d %b, %Y')

TOTAL_ROW_RE = re.compile(r'grand\s*total|sub\s*total|subtotal|taxable\s*value|total\s*tax|round\s*off|cgst|sgst|igst|cess', re.I)

DESC_HEADERS = ('description', 'item', 'particulars', 'product', 'service', 'goods')
QTY_HEADERS = ('qty', 'quantity', 'nos', 'units')
HSN_HEADERS = ('hsn', 'sac', 'hsn code', 'hsn/sac')
RATE_HEADERS = ('rate', 'unit price', 'price', 'rate/unit', 'unit rate', 'per unit')
TAX_HEADERS = ('gst%', 'gst %', 'tax%', 'tax %', 'gst rate', 'tax rate', 'gst', 'tax')
AMT_HEADERS = ('amount', 'line total', 'total', 'net amount', 'value', 'line amount')
UNIT_HEADERS = ('unit', 'uom', 'mrp unit')


def parse_amount(value):
    """Parse an Indian-formatted amount string into Decimal."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).replace('\u20b9', '').replace('Rs.', '').replace('Rs', '')
    text = text.replace('INR', '').replace(' ', '').strip()
    text = re.sub(r'[^0-9,.\-]', '', text)
    if not text:
        return None
    # Indian grouping: remove commas only if they are separators
    text = text.replace(',', '')
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_date_value(value):
    if not value:
        return None
    text = re.sub(r'\s+', ' ', str(value)).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _extract_date(value):
    """Parse a date out of a possibly noisy label value."""
    if not value:
        return None
    parsed = parse_date_value(value)
    if parsed:
        return parsed
    m = re.search(r'(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+\w{3,9}\s+\d{2,4})', str(value))
    return parse_date_value(m.group(1)) if m else None


def _clean_lines(text):
    return [re.sub(r'\s+', ' ', ln).strip() for ln in text.splitlines() if ln.strip()]


def _label_match(line, labels):
    for label in labels:
        pattern = re.compile(label.replace(' ', r'\s*') + r'\s*[:#\-]?\s*(.*)$', re.I)
        m = pattern.search(line)
        if m:
            return m.group(1)
    return None


def _find_labeled(lines, labels):
    """Return (raw_value, confidence) from the first line matching a label."""
    for line in lines:
        rest = _label_match(line, labels)
        if rest is not None and rest.strip():
            return rest.strip(), 0.95
    return None, 0.0


def identify_fields(text):
    """Locate header fields. Returns {field: {'value': v, 'confidence': c}}."""
    lines = _clean_lines(text)
    fields = {}

    def put(key, value, confidence):
        if key not in fields and value not in (None, '', 0):
            fields[key] = {'value': value, 'confidence': round(confidence, 2)}

    # --- GSTINs: first occurrence = seller, second = buyer -------------
    gstins = GSTIN_RE.findall(text.upper())
    if gstins:
        put('seller_gstin', gstins[0], 0.98)
        if len(gstins) > 1:
            put('buyer_gstin', gstins[-1], 0.9)
    pans = PAN_RE.findall(text.upper())
    if pans:
        put('seller_pan', pans[0], 0.85)

    # --- Invoice number -------------------------------------------------
    value, conf = _find_labeled(lines, [r'invoice\s*no\.?', r'invoice\s*number', r'invoice\s*#',
                                        r'bill\s*no\.?', r'bill\s*number', r'tax\s*invoice\s*no'])
    if value:
        value = re.sub(r'^[^A-Za-z0-9]+|[^A-Za-z0-9]+$', '', value.split()[0])
        if 3 <= len(value) <= 30:
            put('invoice_number', value, conf)
    if 'invoice_number' not in fields:
        m = INVOICE_NO_RE.search(text.upper())
        if m:
            put('invoice_number', m.group(2), 0.7)

    # --- Dates ----------------------------------------------------------
    value, conf = _find_labeled(lines, [r'invoice\s*date', r'bill\s*date', r'^date\s*[:]'])
    parsed = _extract_date(value)
    if parsed:
        put('invoice_date', parsed, conf)
    value, conf = _find_labeled(lines, [r'due\s*date', r'payment\s*due\s*date', r'pay\s*by'])
    parsed = _extract_date(value)
    if parsed:
        put('due_date', parsed, conf)

    # --- PO number --------------------------------------------------------
    m = PO_RE.search(text.upper())
    if m:
        put('po_number', m.group(1).strip(' .:-'), 0.9)
    else:
        value, conf = _find_labeled(lines, [r'p\.?o\.?\s*(number|no)', r'po\s*number',
                                            r'purchase\s*order\s*(no|number|#)?'])
        if value:
            cleaned = re.sub(r'[^A-Z0-9\-/_]', '', value.upper())[:20]
            if any(ch.isdigit() for ch in cleaned):
                put('po_number', cleaned, 0.8)

    # --- Amounts ----------------------------------------------------------
    all_amounts = []
    for line in lines:
        for m in AMOUNT_RE.finditer(line):
            amt = parse_amount(m.group(1))
            if amt is not None and amt > 0:
                all_amounts.append((line.lower(), amt))

    value, conf = _find_labeled(lines, [r'grand\s*total', r'total\s*amount', r'invoice\s*(?:amount|total)',
                                        r'total\s*payable', r'net\s*payable', r'^total\b'])
    amt = parse_amount(value) if value else None
    if amt is None and all_amounts:
        amt = max((a for _, a in all_amounts), default=None)
        conf = 0.6
    if amt is not None:
        put('total_amount', amt, conf)

    value, conf = _find_labeled(lines, [r'sub\s*total', r'subtotal', r'taxable\s*value', r'taxable\s*amount'])
    amt = parse_amount(value) if value else None
    if amt is not None:
        put('subtotal', amt, conf)

    # Tax: sum CGST/SGST/IGST labels, else generic tax label
    tax_sum = Decimal('0')
    found_tax_component = False
    for line in lines:
        lowered = line.lower()
        if any(k in lowered for k in ('cgst', 'sgst', 'igst', 'integrated tax', 'state tax', 'central tax')):
            m = AMOUNT_RE.search(line)
            if m:
                amt = parse_amount(m.group(1))
                if amt is not None:
                    tax_sum += amt
                    found_tax_component = True
    if found_tax_component:
        put('tax_amount', tax_sum.quantize(Decimal('0.01')), 0.9)
    else:
        value, conf = _find_labeled(lines, [r'total\s*tax', r'tax\s*amount', r'gst\s*amount'])
        amt = parse_amount(value) if value else None
        if amt is not None:
            put('tax_amount', amt, conf)

    rates = sorted({float(m.group(1)) for m in PERCENT_RE.finditer(text)
                    if 0 < float(m.group(1)) <= 28})
    if rates:
        put('tax_rates', rates, 0.75)

    # --- Seller name: company-like line near the top -----------------------
    for line in lines[:12]:
        if len(line) > 3 and not GSTIN_RE.search(line.upper()) and not AMOUNT_RE.search(line):
            if any(k in line.lower() for k in ('pvt', 'ltd', 'llp', 'industries', 'enterprises',
                                               'traders', 'supplies', 'solutions', 'services', 'infra')):
                put('seller_name', line[:120], 0.65)
                break

    # --- Cross-field consistency ------------------------------------------
    sub = fields.get('subtotal', {}).get('value')
    tax = fields.get('tax_amount', {}).get('value')
    total = fields.get('total_amount', {}).get('value')
    if sub and tax and total:
        if abs((sub + tax) - total) <= Decimal('0.05'):
            for key in ('subtotal', 'tax_amount', 'total_amount'):
                fields[key]['confidence'] = min(1.0, round(fields[key]['confidence'] + 0.1, 2))
    return fields


def _header_index(row):
    lowered = [str(c or '').lower().strip() for c in row]
    joined = ' | '.join(lowered)
    has_desc = any(h in joined for h in DESC_HEADERS)
    has_qty = any(h in joined for h in QTY_HEADERS)
    has_amt = any(h in joined for h in AMT_HEADERS)
    if has_desc and (has_qty or has_amt):
        return lowered
    return None


def _map_columns(header):
    mapping = {}
    for idx, cell in enumerate(header):
        if not cell:
            continue
        if 'description_col' not in mapping and any(h in cell for h in DESC_HEADERS):
            mapping['description_col'] = idx
        elif 'quantity_col' not in mapping and any(h == cell for h in QTY_HEADERS) or (
                'quantity_col' not in mapping and cell in ('qty', 'quantity')):
            mapping['quantity_col'] = idx
        elif 'hsn_col' not in mapping and any(cell.startswith(h) for h in ('hsn', 'sac')):
            mapping['hsn_col'] = idx
        elif 'unit_price_col' not in mapping and any(h in cell for h in RATE_HEADERS):
            mapping['unit_price_col'] = idx
        elif 'tax_rate_col' not in mapping and any(h in cell for h in TAX_HEADERS):
            mapping['tax_rate_col'] = idx
        elif 'line_total_col' not in mapping and any(h in cell for h in AMT_HEADERS):
            mapping['line_total_col'] = idx
        elif 'unit_col' not in mapping and any(h == cell for h in UNIT_HEADERS):
            mapping['unit_col'] = idx
    return mapping


def _parse_cell(cell):
    return str(cell or '').strip()


def extract_line_items(tables, confidence_base=0.9):
    """Detect line-item tables and map them into structured items.

    All detected line-item tables are merged (multi-page invoices carry one
    table per page); totals/tax summary rows are excluded by TOTAL_ROW_RE.
    """
    items = []
    seen = set()
    for table in tables or []:
        if not table or len(table) < 2:
            continue
        header = None
        header_idx = None
        for idx, row in enumerate(table[:6]):
            header = _header_index(row)
            if header:
                header_idx = idx
                break
        if header is None:
            continue
        cols = _map_columns(header)
        if 'description_col' not in cols:
            continue
        for row in table[header_idx + 1:]:
            cells = [str(c or '').strip() for c in row]
            desc = cells[cols['description_col']] if cols['description_col'] < len(cells) else ''
            if not desc or TOTAL_ROW_RE.search(desc):
                # totals / tax summary rows are not line items
                if not desc:
                    continue
                continue
            row_key = '|'.join(cells)
            if row_key in seen:
                continue
            seen.add(row_key)

            def num(key, default=None):
                idx = cols.get(key)
                if idx is None or idx >= len(cells):
                    return default
                return parse_amount(cells[idx])

            qty = num('quantity_col') or Decimal('1')
            price = num('unit_price_col') or Decimal('0')
            amount = num('line_total_col')
            if amount is None:
                amount = qty * price
            rate = num('tax_rate_col') or Decimal('0')
            if isinstance(rate, Decimal) and rate > 1:  # 18 vs 18%
                rate = rate
            items.append({
                'description': desc[:255],
                'hsn_code': (cells[cols['hsn_col']] if cols.get('hsn_col') is not None
                             and cols['hsn_col'] < len(cells) else '')[:10],
                'quantity': qty,
                'unit': (cells[cols['unit_col']] if cols.get('unit_col') is not None
                         and cols['unit_col'] < len(cells) else 'NOS')[:10] or 'NOS',
                'unit_price': price,
                'tax_rate': rate,
                'line_total': amount,
                'ocr_confidence': confidence_base,
            })
    return items[:200]


def run_field_identification(extraction):
    """Full identification pass over an OCR extraction result."""
    fields = identify_fields(extraction['text'])
    items = extract_line_items(extraction.get('tables'), confidence_base=0.9)
    return {'fields': fields, 'line_items': items}
