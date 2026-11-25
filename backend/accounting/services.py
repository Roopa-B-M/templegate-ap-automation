"""ERP / accounting connector layer (same pattern as payments BankGateway).

`ERPConnector` is the interface every ERP integration implements:

- `post_voucher(invoice, mapping)` posts ONE purchase voucher and returns an
  ERP reference (voucher/document number).
- `export_documents(invoices, mapping)` renders a batch export in the
  connector's native format and returns (filename, content_type, bytes).

Shipped implementations:

- `TallyXMLConnector`  - Tally-compatible XML purchase voucher export.
- `SimulatedERPConnector` - posts a voucher locally and returns a reference.
- Generic `export_csv` / `export_json` helpers for any accounting system that
  accepts flat files.

No live ERP is contacted anywhere; the default connector is clearly labelled
as a simulation (see SCOPE_COVERAGE.md). A real Tally/ERP host adapter only
needs to implement the same interface.
"""
import csv
import io
import json
import logging
import random
import string
from datetime import date
from decimal import Decimal

from django.utils import timezone

from invoices.models import Invoice
from vendors.services import is_valid_gstin

logger = logging.getLogger('accounting')


class ERPConnectorError(Exception):
    pass


def _interstate(invoice):
    """Inter-state supply when the vendor state differs from the company state."""
    vendor_state = getattr(invoice.vendor, 'state_code', '') or ''
    from django.conf import settings
    return vendor_state != settings.COMPANY_STATE_CODE


def _require_postable(invoice):
    """Business rule: only APPROVED or PAID invoices may be posted to the ERP."""
    if invoice.status not in (Invoice.Status.APPROVED, Invoice.Status.PAID):
        raise ERPConnectorError(
            f'Invoice is in status {invoice.get_status_display()}; only APPROVED or PAID '
            'invoices can be posted to the ERP.')
    if invoice.vendor is None:
        raise ERPConnectorError('Invoice has no vendor linked.')
    if invoice.total_amount is None:
        raise ERPConnectorError('Invoice has no total amount.')


def build_voucher(invoice, mapping):
    """Normalised purchase voucher shared by every connector/export format."""
    _require_postable(invoice)
    vendor = invoice.vendor
    interstate = _interstate(invoice)
    tax = invoice.tax_amount or Decimal('0')
    return {
        'voucher_type': 'Purchase',
        'reference': invoice.invoice_number or f'INV-{invoice.pk}',
        'date': invoice.invoice_date or timezone.localdate(),
        'party': {'name': vendor.name, 'gstin': vendor.gstin, 'state_code': vendor.state_code,
                  'supply_type': 'INTER_STATE' if interstate else 'INTRA_STATE'},
        'lines': [
            {
                'account': mapping.expense_account,
                'description': line.description,
                'hsn_code': line.hsn_code,
                'quantity': str(line.quantity),
                'unit': line.unit,
                'rate': str(line.unit_price),
                'amount': str(line.line_total),
                'tax_rate': str(line.tax_rate),
            }
            for line in invoice.line_items.all()
        ],
        'ledger_entries': [
            {'account': mapping.expense_account, 'amount': str(invoice.subtotal or ''), 'type': 'DEBIT'},
            *([{'account': mapping.cgst_account, 'amount': str((tax / 2).quantize(Decimal('0.01'))), 'type': 'DEBIT'},
               {'account': mapping.sgst_account, 'amount': str((tax / 2).quantize(Decimal('0.01'))), 'type': 'DEBIT'}]
              if not interstate else
              [{'account': mapping.igst_account, 'amount': str(tax.quantize(Decimal('0.01'))), 'type': 'DEBIT'}]),
            {'account': mapping.payable_account, 'amount': str(invoice.total_amount), 'type': 'CREDIT'},
        ],
        'total': str(invoice.total_amount),
    }


class ERPConnector:
    """Interface for ERP / accounting system integrations."""

    name = 'base'
    export_format = 'json'

    def post_voucher(self, invoice, mapping) -> str:
        """Post one purchase voucher; returns the ERP voucher reference."""
        raise NotImplementedError

    def export_documents(self, invoices, mapping):
        """Render a batch export. Returns (filename, content_type, bytes)."""
        raise NotImplementedError


class SimulatedERPConnector(ERPConnector):
    """Deterministic local simulation of an ERP posting endpoint.

    Validates the invoice and mapping the same way a live connector would,
    then returns a generated ERP voucher reference. Vendors whose account
    mapping is missing the payable ledger fail, to exercise error handling.
    """

    name = 'SimulatedERPConnector'
    export_format = 'json'

    def _validate_mapping(self, mapping):
        if mapping is None:
            raise ERPConnectorError('No GL account mapping configured. Add one under Accounting > Mappings.')
        if not mapping.expense_account:
            raise ERPConnectorError('GL account mapping is missing the expense account.')
        if not mapping.payable_account:
            raise ERPConnectorError('GL account mapping is missing the payable account.')
        if not is_valid_gstin(getattr(mapping.vendor, 'gstin', '') or '') and mapping.vendor is not None:
            # A vendor-specific mapping for a vendor with an invalid GSTIN is suspicious.
            raise ERPConnectorError(f'Vendor GSTIN {mapping.vendor.gstin} fails validation.')

    def post_voucher(self, invoice, mapping):
        self._validate_mapping(mapping)
        voucher = build_voucher(invoice, mapping)
        if not voucher['lines']:
            raise ERPConnectorError('Invoice has no line items; nothing to post.')
        stamp = date.today().strftime('%Y')
        seq = ''.join(random.choices(string.digits, k=6))
        reference = f'ERP-{stamp}-{seq}'
        logger.info('Simulated ERP voucher posted for %s -> %s', invoice.invoice_number or invoice.pk, reference)
        return reference

    def export_documents(self, invoices, mapping):
        payload = []
        for invoice in invoices:
            voucher = build_voucher(invoice, mapping)
            payload.append(voucher)
        body = {
            'connector': self.name,
            'mode': 'simulated',
            'generated_at': timezone.now().isoformat(),
            'voucher_count': len(payload),
            'vouchers': payload,
        }
        return 'erp-export.json', 'application/json', json.dumps(body, indent=2).encode()


class TallyXMLConnector(SimulatedERPConnector):
    """Tally-compatible purchase voucher export (XML envelope).

    Produces the `Import Data` envelope Tally ERP 9 / Prime accepts on its
    XML import interface. Posting is simulated: the voucher XML is built and
    validated, and an ERP reference is returned, but nothing is sent over
    the network. Point `post_voucher` at a real Tally HTTP endpoint to go live.
    """

    name = 'TallyXMLConnector'
    export_format = 'tally_xml'

    @staticmethod
    def _esc(value):
        return (str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

    @staticmethod
    def _tally_date(value):
        return value.strftime('%Y%m%d') if value else ''

    def voucher_xml(self, invoice, mapping):
        voucher = build_voucher(invoice, mapping)
        entries = []
        for entry in voucher['ledger_entries']:
            sign = -1 if entry['type'] == 'DEBIT' else 1
            entries.append(
                '      <ALLLEDGERENTRIES.LIST>\n'
                f'        <LEDGERNAME>{self._esc(entry["account"])}</LEDGERNAME>\n'
                f'        <ISDEEMEDPOSITIVE>{"Yes" if sign < 0 else "No"}</ISDEEMEDPOSITIVE>\n'
                f'        <AMOUNT>{sign * float(entry["amount"]):.2f}</AMOUNT>\n'
                '      </ALLLEDGERENTRIES.LIST>'
            )
        remote_id = f'TG-INV-{invoice.pk}'
        return (
            '  <TALLYMESSAGE xmlns:UDF="TallyUDF">\n'
            f'    <VOUCHER REMOTEID="{remote_id}" VCHTYPE="Purchase" ACTION="Create" '
            'OBJVIEW="Accounting Voucher View">\n'
            f'      <DATE>{self._tally_date(voucher["date"])}</DATE>\n'
            '      <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>\n'
            f'      <VOUCHERNUMBER>{self._esc(voucher["reference"])}</VOUCHERNUMBER>\n'
            f'      <PARTYLEDGERNAME>{self._esc(mapping.payable_account)}</PARTYLEDGERNAME>\n'
            f'      <PARTYNAME>{self._esc(voucher["party"]["name"])}</PARTYNAME>\n'
            f'      <GSTREGISTRATIONTYPE>{"Regular" if voucher["party"]["gstin"] else "Unregistered"}</GSTREGISTRATIONTYPE>\n'
            '      <PERSISTEDSTATUS>Unposted</PERSISTEDSTATUS>\n'
            f'      <AMOUNT>{float(voucher["total"]):.2f}</AMOUNT>\n'
            + '\n'.join(entries) + '\n'
            '    </VOUCHER>\n'
            '  </TALLYMESSAGE>'
        )

    def envelope(self, invoices, mapping):
        messages = '\n'.join(self.voucher_xml(inv, mapping) for inv in invoices)
        return (
            '<ENVELOPE>\n'
            '  <HEADER>\n'
            '    <TALLYREQUEST>Import Data</TALLYREQUEST>\n'
            '  </HEADER>\n'
            '  <BODY>\n'
            '    <IMPORTDATA>\n'
            '      <REQUESTDESC>\n'
            '        <REPORTNAME>Vouchers</REPORTNAME>\n'
            '        <STATICVARIABLES>\n'
            '          <SVCURRENTCOMPANY></SVCURRENTCOMPANY>\n'
            '        </STATICVARIABLES>\n'
            '      </REQUESTDESC>\n'
            '      <REQUESTDATA>\n'
            f'{messages}\n'
            '      </REQUESTDATA>\n'
            '    </IMPORTDATA>\n'
            '  </BODY>\n'
            '</ENVELOPE>\n'
        )

    def post_voucher(self, invoice, mapping):
        self._validate_mapping(mapping)
        xml = self.voucher_xml(invoice, mapping)  # validation happens inside build_voucher
        if '<VOUCHER ' not in xml:
            raise ERPConnectorError('Tally voucher XML could not be generated.')
        stamp = date.today().strftime('%Y%m%d')
        seq = ''.join(random.choices(string.digits, k=5))
        reference = f'TLY-{stamp}-{seq}'
        logger.info('Simulated Tally XML voucher accepted for %s -> %s',
                    invoice.invoice_number or invoice.pk, reference)
        return reference

    def export_documents(self, invoices, mapping):
        xml = self.envelope(invoices, mapping)
        stamp = timezone.localdate().strftime('%Y%m%d')
        return f'tally-purchase-vouchers-{stamp}.xml', 'application/xml', xml.encode()


def export_csv(invoices, mapping=None):
    """Generic flat-file CSV export accepted by most accounting systems."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['voucher_type', 'voucher_reference', 'voucher_date', 'vendor_name',
                     'vendor_gstin', 'supply_type', 'expense_account', 'payable_account',
                     'cgst_account', 'sgst_account', 'igst_account', 'subtotal', 'tax_amount',
                     'total_amount', 'invoice_number', 'erp_status'])
    for invoice in invoices:
        vendor = invoice.vendor
        interstate = _interstate(invoice)
        local_mapping = mapping if mapping is not None else get_default_mapping(vendor)
        writer.writerow([
            'Purchase',
            invoice.invoice_number or f'INV-{invoice.pk}',
            invoice.invoice_date or '',
            vendor.name if vendor else '',
            vendor.gstin if vendor else '',
            'INTER_STATE' if interstate else 'INTRA_STATE',
            local_mapping.expense_account if local_mapping else '',
            local_mapping.payable_account if local_mapping else '',
            local_mapping.cgst_account if local_mapping else '',
            local_mapping.sgst_account if local_mapping else '',
            local_mapping.igst_account if local_mapping else '',
            invoice.subtotal or '0',
            invoice.tax_amount or '0',
            invoice.total_amount or '0',
            invoice.invoice_number or '',
            invoice.erp_status,
        ])
    stamp = timezone.localdate().strftime('%Y%m%d')
    return f'accounting-export-{stamp}.csv', 'text/csv', buffer.getvalue().encode()


def export_json(invoices, mapping=None):
    """Generic JSON export accepted by REST-capable accounting systems."""
    documents = []
    for invoice in invoices:
        vendor = invoice.vendor
        interstate = _interstate(invoice)
        documents.append({
            'document_type': 'PURCHASE_VOUCHER',
            'reference': invoice.invoice_number or f'INV-{invoice.pk}',
            'date': str(invoice.invoice_date or ''),
            'vendor': {'name': vendor.name, 'gstin': vendor.gstin} if vendor else None,
            'supply_type': 'INTER_STATE' if interstate else 'INTRA_STATE',
            'currency': invoice.currency,
            'subtotal': str(invoice.subtotal or '0'),
            'tax_amount': str(invoice.tax_amount or '0'),
            'total_amount': str(invoice.total_amount or '0'),
            'lines': [
                {'description': line.description, 'hsn_code': line.hsn_code,
                 'quantity': str(line.quantity), 'unit': line.unit,
                 'rate': str(line.unit_price), 'amount': str(line.line_total),
                 'tax_rate': str(line.tax_rate)}
                for line in invoice.line_items.all()
            ],
            'erp_status': invoice.erp_status,
        })
    body = {'document_count': len(documents), 'documents': documents,
            'generated_at': timezone.now().isoformat()}
    stamp = timezone.localdate().strftime('%Y%m%d')
    return f'accounting-export-{stamp}.json', 'application/json', json.dumps(body, indent=2).encode()


def get_connector():
    """Factory driven by the ERP_CONNECTOR setting (simulated|tally_xml)."""
    from django.conf import settings
    choice = (getattr(settings, 'ERP_CONNECTOR', 'simulated') or 'simulated').lower()
    if choice == 'tally_xml':
        return TallyXMLConnector()
    return SimulatedERPConnector()


def get_default_mapping(vendor=None):
    """Vendor-specific mapping when present, else the active default mapping."""
    from .models import GLAccountMapping
    if vendor is not None:
        row = GLAccountMapping.objects.filter(vendor=vendor, is_active=True).first()
        if row:
            return row
    return GLAccountMapping.objects.filter(vendor__isnull=True, is_active=True).first()


def post_invoice_to_erp(invoice, user, format=None, replace_log=None):
    """Post one invoice voucher through the configured connector.

    Writes/updates an ERPSyncLog, mirrors the outcome onto the Invoice
    (erp_status / erp_reference) and returns a small result dict. Raises
    ERPConnectorError (after recording the failure) when posting fails.
    """
    from .models import ERPSyncLog

    format = format or ERPSyncLog.Format.SINGLE_POST
    mapping = get_default_mapping(invoice.vendor)
    connector = get_connector()
    sync_log = replace_log
    try:
        erp_reference = connector.post_voucher(invoice, mapping)
        if sync_log is None:
            sync_log = ERPSyncLog(invoice=invoice, connector=connector.name, format=format)
        sync_log.status = ERPSyncLog.Status.SYNCED
        sync_log.erp_reference = erp_reference
        sync_log.error = ''
        sync_log.connector = connector.name
        sync_log.posted_at = timezone.now()
        if user is not None and user.is_authenticated:
            sync_log.requested_by = user
        sync_log.payload_preview = {
            'voucher_type': 'Purchase',
            'reference': invoice.invoice_number or f'INV-{invoice.pk}',
            'total_amount': str(invoice.total_amount),
            'ledger_count': 2 + (1 if (invoice.tax_amount or Decimal('0')) > 0 else 0),
        }
        sync_log.save()
        invoice.erp_status = Invoice.ErpStatus.SYNCED
        invoice.erp_reference = erp_reference
        invoice.save(update_fields=['erp_status', 'erp_reference', 'updated_at'])
        return {'status': 'SYNCED', 'erp_reference': erp_reference, 'log_id': sync_log.pk,
                'connector': connector.name}
    except ERPConnectorError as exc:
        if sync_log is None:
            sync_log = ERPSyncLog(invoice=invoice, connector=connector.name, format=format)
        sync_log.status = ERPSyncLog.Status.FAILED
        sync_log.error = str(exc)[:2000]
        sync_log.connector = connector.name
        if user is not None and user.is_authenticated:
            sync_log.requested_by = user
        sync_log.save()
        invoice.erp_status = Invoice.ErpStatus.FAILED
        invoice.save(update_fields=['erp_status', 'updated_at'])
        logger.warning('ERP posting failed for invoice %s: %s', invoice.pk, exc)
        raise
