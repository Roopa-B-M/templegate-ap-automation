"""PO matching engine - 2-way (PO vs Invoice) and 3-way (PO vs GRN vs Invoice)."""
from decimal import Decimal

from django.conf import settings

from ..models import Invoice, MatchResult

TOLERANCE = Decimal(str(settings.TOLERANCE_AMOUNT_PCT))  # percent
QTY_TOLERANCE = Decimal(str(settings.TOLERANCE_QUANTITY_PCT))


def _line_matches(inv_line, po_line):
    """Heuristic line pairing: same description, or same qty+price."""
    desc_a = inv_line.description.strip().lower()
    desc_b = po_line.description.strip().lower()
    if desc_a == desc_b or desc_b.startswith(desc_a) or desc_a.startswith(desc_b):
        return True
    return (inv_line.quantity == po_line.quantity and inv_line.unit_price == po_line.unit_price)


def run_match(invoice, po=None):
    """Runs matching and persists a MatchResult; returns (result, ok)."""
    MatchResult.objects.filter(invoice=invoice).delete()
    po = po or invoice.po
    if po is None:
        result = MatchResult.objects.create(
            invoice=invoice, match_type=MatchResult.MatchType.NOT_APPLICABLE,
            status=MatchResult.Status.NOT_APPLICABLE,
            details={'note': 'Non-PO invoice - matching not applicable.'},
        )
        if invoice.status in (Invoice.Status.MATCH_EXCEPTION,):
            invoice.status = Invoice.Status.VALIDATED
            invoice.save(update_fields=['status', 'updated_at'])
        return result, True

    invoice.po = po
    invoice.save(update_fields=['po', 'updated_at'])

    po_lines = list(po.lines.all())
    inv_lines = list(invoice.line_items.all())
    received_map = {l.id: l.received_qty for l in po_lines}
    has_grn = any(l.received_qty > 0 for l in po_lines)
    match_type = MatchResult.MatchType.THREE_WAY if has_grn else MatchResult.MatchType.TWO_WAY

    line_checks = []
    for inv_line in inv_lines:
        po_line = next((p for p in po_lines if _line_matches(inv_line, p)), None)
        check = {
            'invoice_line': inv_line.line_number,
            'description': inv_line.description,
            'po_line': po_line.line_number if po_line else None,
            'qty_invoice': str(inv_line.quantity),
            'qty_po': str(po_line.quantity) if po_line else None,
            'qty_received': str(received_map.get(po_line.id, '0')) if po_line else None,
            'rate_invoice': str(inv_line.unit_price),
            'rate_po': str(po_line.unit_price) if po_line else None,
        }
        if po_line is None:
            check.update({'on_po': False, 'reason': 'No corresponding PO line found.'})
        else:
            rate_diff_pct = (abs(inv_line.unit_price - po_line.unit_price) / po_line.unit_price * 100
                             if po_line.unit_price else Decimal('0'))
            qty_ok = inv_line.quantity <= po_line.quantity * (Decimal('1') + QTY_TOLERANCE / 100)
            rate_ok = rate_diff_pct <= TOLERANCE
            check.update({'on_po': True, 'qty_ok': qty_ok, 'rate_ok': rate_ok,
                          'rate_diff_pct': str(rate_diff_pct.quantize(Decimal('0.01')))})
            if match_type == MatchResult.MatchType.THREE_WAY:
                received_ok = received_map[po_line.id] >= inv_line.quantity
                check['received_ok'] = received_ok
        line_checks.append(check)

    variance = (invoice.total_amount or Decimal('0')) - po.total_amount
    variance_pct = (variance / po.total_amount * 100) if po.total_amount else Decimal('0')
    header_ok = variance_pct <= TOLERANCE  # invoice may be below PO, not materially above

    unmatched = [c for c in line_checks if not c.get('on_po')]
    bad_qty = [c for c in line_checks if c.get('on_po') and not c.get('qty_ok')]
    bad_rate = [c for c in line_checks if c.get('on_po') and not c.get('rate_ok')]
    bad_grn = [c for c in line_checks if c.get('on_po') and match_type == MatchResult.MatchType.THREE_WAY
               and not c.get('received_ok')]

    ok = header_ok and not unmatched and not bad_qty and not bad_rate and not bad_grn

    details = {
        'po_number': po.po_number,
        'vendor': po.vendor.name,
        'match_type': match_type,
        'header': {
            'po_total': str(po.total_amount),
            'invoice_total': str(invoice.total_amount or '0'),
            'variance': str(variance.quantize(Decimal('0.01'))),
            'variance_pct': str(variance_pct.quantize(Decimal('0.01'))),
            'tolerance_pct': str(TOLERANCE),
            'within_tolerance': header_ok,
        },
        'line_checks': line_checks,
        'problems': {
            'lines_not_on_po': len(unmatched),
            'qty_over_po': len(bad_qty),
            'rate_over_tolerance': len(bad_rate),
            'qty_not_received_3way': len(bad_grn),
        },
    }
    result = MatchResult.objects.create(
        invoice=invoice, po=po, match_type=match_type,
        status=MatchResult.Status.MATCHED if ok else MatchResult.Status.MISMATCH,
        total_variance=variance.quantize(Decimal('0.01')),
        details=details,
    )
    if ok:
        if invoice.status not in (Invoice.Status.EXCEPTION,):
            invoice.status = Invoice.Status.MATCHED
    elif invoice.status not in (Invoice.Status.PENDING_APPROVAL, Invoice.Status.APPROVED,
                                Invoice.Status.REJECTED, Invoice.Status.PAID,
                                Invoice.Status.EXCEPTION):
        invoice.status = Invoice.Status.MATCH_EXCEPTION
    invoice.save(update_fields=['status', 'updated_at'])
    return result, ok
