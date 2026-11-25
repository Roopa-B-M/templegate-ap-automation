"""ERP / accounting integration API.

All endpoints are restricted to Finance and Admin roles. Only APPROVED or
PAID invoices can be posted to the ERP. Every posting attempt is written to
ERPSyncLog and mirrored onto Invoice.erp_status / erp_reference.
"""
import logging

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log
from core.permissions import IsFinanceOrAdmin
from invoices.models import Invoice
from .models import ERPSyncLog, GLAccountMapping
from .serializers import ERPSyncLogSerializer, GLAccountMappingSerializer
from .services import (ERPConnectorError, export_csv, export_json, get_connector,
                       get_default_mapping, post_invoice_to_erp)

logger = logging.getLogger('accounting')


class GLAccountMappingViewSet(viewsets.ModelViewSet):
    """/api/accounting/mappings/ - CRUD for ledger account mappings."""
    queryset = GLAccountMapping.objects.select_related('vendor')
    serializer_class = GLAccountMappingSerializer
    permission_classes = (IsFinanceOrAdmin,)
    filterset_fields = ('vendor', 'is_active')
    search_fields = ('name', 'expense_account', 'payable_account', 'vendor__name')
    ordering_fields = ('name', 'created_at')

    def perform_create(self, serializer):
        mapping = serializer.save()
        log(entity='GLAccountMapping', entity_id=mapping.pk, entity_repr=str(mapping))

    def perform_update(self, serializer):
        mapping = serializer.save()
        log(entity='GLAccountMapping', entity_id=mapping.pk, entity_repr=str(mapping))

    def perform_destroy(self, instance):
        log(entity='GLAccountMapping', entity_id=instance.pk, entity_repr=str(instance))
        instance.delete()


class ERPSyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    """/api/accounting/sync-logs/ - ERP posting history (paginated)."""
    queryset = ERPSyncLog.objects.select_related('invoice', 'invoice__vendor', 'requested_by')
    serializer_class = ERPSyncLogSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ('status', 'format', 'invoice')
    search_fields = ('erp_reference', 'invoice__invoice_number', 'invoice__vendor__name')
    ordering_fields = ('created_at', 'status')

    def get_permissions(self):
        # Posting actions are Finance/Admin only; the log itself is viewable by all roles.
        if self.action == 'retry':
            return [IsFinanceOrAdmin()]
        return [IsAuthenticated()]


class AccountingOperationsViewSet(viewsets.ViewSet):
    """/api/accounting/ - posting, bulk export and connector status."""
    permission_classes = (IsFinanceOrAdmin,)

    @action(detail=False, methods=['get'], url_path='status')
    def connector_status(self, request):
        """Connector identity + simulation flag so the UI can label the mode."""
        connector = get_connector()
        return Response({
            'connector': connector.name,
            'export_format': connector.export_format,
            'mode': 'simulated',
            'note': 'ERP posting is simulated locally. No live ERP connection is made.',
        })

    @action(detail=False, methods=['post'], url_path=r'post-invoice/(?P<invoice_id>\d+)')
    def post_invoice(self, request, invoice_id=None):
        invoice = Invoice.objects.filter(pk=invoice_id).first()
        if invoice is None:
            return Response({'detail': 'Invoice not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            result = post_invoice_to_erp(invoice, request.user, format=ERPSyncLog.Format.SINGLE_POST)
        except ERPConnectorError as exc:
            log(entity='Invoice', entity_id=invoice.pk, entity_repr=str(invoice),
                changes={'erp_post': {'new': f'FAILED: {exc}'}})
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log(entity='Invoice', entity_id=invoice.pk, entity_repr=str(invoice),
            changes={'erp_post': {'new': result['erp_reference']}})
        return Response({'detail': f"Voucher posted. ERP reference: {result['erp_reference']}",
                         **result})

    @action(detail=False, methods=['post'], url_path='bulk-export')
    def bulk_export(self, request):
        """Export approved/paid invoices in a date range as tally_xml|csv|json.

        Body: {"date_from": "2025-01-01", "date_to": "2025-12-31", "format": "csv"}
        Every invoice included is posted (simulated) and marked SYNCED with an
        ERP reference; failures are recorded per invoice in ERPSyncLog.
        """
        date_from = request.data.get('date_from')
        date_to = request.data.get('date_to')
        export_format = (request.data.get('format') or '').upper() or 'CSV'
        if export_format not in ('CSV', 'JSON', 'TALLY_XML'):
            return Response({'detail': "format must be one of: CSV, JSON, TALLY_XML."},
                            status=status.HTTP_400_BAD_REQUEST)
        qs = Invoice.objects.filter(status__in=(Invoice.Status.APPROVED, Invoice.Status.PAID)) \
            .select_related('vendor').prefetch_related('line_items').order_by('invoice_date', 'id')
        if date_from:
            qs = qs.filter(invoice_date__gte=date_from)
        if date_to:
            qs = qs.filter(invoice_date__lte=date_to)
        invoices = list(qs)
        if not invoices:
            return Response({'detail': 'No approved/paid invoices found in that date range.'},
                            status=status.HTTP_400_BAD_REQUEST)

        connector = get_connector()
        posted, failed = [], []
        for invoice in invoices:
            try:
                result = post_invoice_to_erp(invoice, request.user,
                                             format=ERPSyncLog.Format(export_format))
                posted.append({'invoice_id': invoice.pk, 'erp_reference': result['erp_reference']})
            except ERPConnectorError as exc:
                failed.append({'invoice_id': invoice.pk, 'reason': str(exc)})

        exportable = [Invoice.objects.get(pk=p['invoice_id']) for p in posted]
        if export_format == 'CSV':
            filename, content_type, payload = export_csv(exportable)
        elif export_format == 'JSON':
            filename, content_type, payload = export_json(exportable)
        else:
            mapping = get_default_mapping()
            filename, content_type, payload = connector.export_documents(exportable, mapping)

        log(entity='System', entity_id=0, entity_repr='ERP bulk export',
            changes={'format': {'new': export_format},
                     'posted': {'new': len(posted)}, 'failed': {'new': len(failed)}})
        response = HttpResponse(payload, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Sync-Posted'] = str(len(posted))
        response['X-Sync-Failed'] = str(len(failed))
        response['X-Export-Filename'] = filename
        return response


class AccountingRetryView(APIView):
    """POST /api/accounting/retry/{log_id}/ - retry a FAILED ERP posting."""
    permission_classes = (IsFinanceOrAdmin,)

    def post(self, request, log_id):
        sync_log = ERPSyncLog.objects.select_related('invoice').filter(pk=log_id).first()
        if sync_log is None:
            return Response({'detail': 'Sync log not found.'}, status=status.HTTP_404_NOT_FOUND)
        if sync_log.status != ERPSyncLog.Status.FAILED:
            return Response({'detail': f'Only FAILED postings can be retried (this one is '
                                       f'{sync_log.get_status_display()}).'},
                            status=status.HTTP_400_BAD_REQUEST)
        invoice = sync_log.invoice
        try:
            result = post_invoice_to_erp(invoice, request.user, format=sync_log.format,
                                         replace_log=sync_log)
        except ERPConnectorError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log(entity='Invoice', entity_id=invoice.pk, entity_repr=str(invoice),
            changes={'erp_retry': {'new': result['erp_reference']}})
        return Response({'detail': f"Retry succeeded. ERP reference: {result['erp_reference']}",
                         **result})
