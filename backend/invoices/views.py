import logging

from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit import log
from core.permissions import IsAdmin, IsAdminOrClerk
from purchase_orders.models import PurchaseOrder
from .models import Invoice
from .serializers import InvoiceDetailSerializer, InvoiceListSerializer
from .services import pipeline
from .services.email_ingest import ingest_email_attachments
from .services.matching import run_match
from .services.validation import run_validation

logger = logging.getLogger('invoices')

CONTENT_TYPES = {
    'PDF': 'application/pdf', 'JPG': 'image/jpeg', 'JPEG': 'image/jpeg',
    'PNG': 'image/png', 'TIF': 'image/tiff', 'TIFF': 'image/tiff',
}


class InvoiceViewSet(viewsets.ModelViewSet):
    """/api/invoices/ - capture, OCR, review, validation, matching, workflow hand-off."""
    permission_classes = (IsAuthenticated,)
    filterset_fields = ('status', 'ocr_status', 'vendor', 'po')
    search_fields = ('invoice_number', 'vendor__name', 'po__po_number')
    ordering_fields = ('created_at', 'invoice_date', 'due_date', 'total_amount')

    def get_queryset(self):
        qs = Invoice.objects.select_related('vendor', 'po', 'created_by')
        params = self.request.query_params
        status_param = params.get('status')
        if status_param:
            qs = qs.filter(status=status_param.upper())
        vendor_id = params.get('vendor_id') or params.get('vendor')
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        po_number = params.get('po_number')
        if po_number:
            qs = qs.filter(po__po_number__iexact=po_number)
        date_from, date_to = params.get('date_from'), params.get('date_to')
        if date_from:
            qs = qs.filter(invoice_date__gte=date_from)
        if date_to:
            qs = qs.filter(invoice_date__lte=date_to)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return InvoiceListSerializer
        return InvoiceDetailSerializer

    def get_permissions(self):
        if self.action in ('upload', 'email_ingest', 'extracted_fields', 'reprocess_ocr'):
            return [IsAdminOrClerk()]
        if self.action == 'override_exception':
            return [IsAdmin()]
        return [IsAuthenticated()]

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """Bulk invoice capture (drag & drop, multi-format)."""
        files = request.FILES.getlist('files') or (request.FILES.getlist('file') or [])
        if not files:
            return Response({'detail': 'No files received.'}, status=status.HTTP_400_BAD_REQUEST)
        vendor_id = request.data.get('vendor_id') or None
        po_number = request.data.get('po_number') or None
        uploaded, failed = [], []
        for f in files:
            try:
                invoice = pipeline.create_invoice_from_file(
                    f, request.user, vendor_id=vendor_id, po_number=po_number)
                pipeline.process_async(invoice)
                uploaded.append({'id': invoice.pk, 'file_name': invoice.file_name,
                                 'status': invoice.status, 'ocr_status': invoice.ocr_status})
            except ValueError as exc:
                failed.append({'file_name': getattr(f, 'name', '?'), 'reason': str(exc)})
        return Response({'uploaded': uploaded, 'failed': failed}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='email-ingest')
    def email_ingest(self, request):
        """Email ingestion channel (mail-room simulation)."""
        attachments = request.FILES.getlist('attachments') or request.FILES.getlist('files') or []
        if not attachments:
            return Response({'detail': 'No attachments received.'}, status=status.HTTP_400_BAD_REQUEST)
        uploaded, failed = ingest_email_attachments(
            attachments, request.user,
            from_email=request.data.get('from_email', ''),
            subject=request.data.get('subject', ''),
        )
        return Response(
            {'uploaded': [{'id': i.pk, 'file_name': i.file_name, 'status': i.status,
                           'ocr_status': i.ocr_status} for i in uploaded],
             'failed': failed},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='file')
    def file(self, request, pk=None):
        """Streams the original invoice document (auth-protected)."""
        invoice = self.get_object()
        if not invoice.file:
            return Response({'detail': 'No file stored for this invoice.'}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(invoice.file.open('rb'),
                            content_type=CONTENT_TYPES.get(invoice.file_type, 'application/octet-stream'),
                            as_attachment=False, filename=invoice.file_name)

    @action(detail=True, methods=['post'])
    def reprocess_ocr(self, request, pk=None):
        invoice = self.get_object()
        invoice.ocr_status = Invoice.OcrStatus.PENDING
        invoice.ocr_error = ''
        invoice.save(update_fields=['ocr_status', 'ocr_error', 'updated_at'])
        pipeline.process_async(invoice)
        return Response({'detail': 'OCR reprocessing started'})

    # ------------------------------------------------------------------
    # Review & engines
    # ------------------------------------------------------------------
    @action(detail=True, methods=['put'], url_path='extracted-fields')
    def extracted_fields(self, request, pk=None):
        """Save human-reviewed data; automatically re-runs validation + matching."""
        invoice = self.get_object()
        from .serializers import InvoiceReviewSerializer
        serializer = InvoiceReviewSerializer(instance=invoice, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = pipeline.apply_reviewed_fields(invoice, request.data)
        log(entity='Invoice', entity_id=updated.pk, entity_repr=str(updated),
            changes={'review': {'new': 'fields confirmed by reviewer'}})
        return Response(InvoiceDetailSerializer(updated).data)

    @action(detail=True, methods=['post'])
    def validate(self, request, pk=None):
        invoice = self.get_object()
        result = run_validation(invoice)
        return Response({'detail': 'Validation complete', 'result': result,
                         'invoice': InvoiceDetailSerializer(invoice).data})

    @action(detail=True, methods=['post'])
    def match(self, request, pk=None):
        invoice = self.get_object()
        po = None
        po_id = request.data.get('po_id')
        if po_id:
            po = PurchaseOrder.objects.filter(pk=po_id).first()
            if po is None:
                return Response({'detail': 'PO not found.'}, status=status.HTTP_400_BAD_REQUEST)
        result, ok = run_match(invoice, po=po)
        log(entity='Invoice', entity_id=invoice.pk, entity_repr=str(invoice),
            changes={'match': {'new': f'{result.match_type} {result.status}'}})
        return Response({'detail': 'Matching complete', 'matched': ok,
                         'invoice': InvoiceDetailSerializer(invoice).data})

    # ------------------------------------------------------------------
    # Workflow & lifecycle
    # ------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='submit-approval')
    def submit_approval(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status not in (Invoice.Status.VALIDATED, Invoice.Status.MATCHED):
            return Response(
                {'detail': f'Invoice in status {invoice.get_status_display()} cannot be submitted. '
                           'Resolve validation/matching first.'},
                status=status.HTTP_400_BAD_REQUEST)
        from workflow.services import start_approval
        try:
            tasks = start_approval(invoice, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': f'Submitted for approval ({len(tasks)} task(s) created)',
                         'invoice': InvoiceDetailSerializer(invoice).data})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status == Invoice.Status.PAID:
            return Response({'detail': 'Paid invoices cannot be cancelled.'},
                            status=status.HTTP_400_BAD_REQUEST)
        invoice.status = Invoice.Status.CANCELLED
        invoice.save(update_fields=['status', 'updated_at'])
        log(entity='Invoice', entity_id=invoice.pk, entity_repr=str(invoice),
            changes={'status': {'new': 'CANCELLED'}})
        return Response({'detail': 'Invoice cancelled'})

    @action(detail=True, methods=['post'], url_path='override-exception')
    def override_exception(self, request, pk=None):
        """Admin override of a validation/matching exception (audited, reason required)."""
        invoice = self.get_object()
        reason = (request.data.get('reason') or '').strip()
        if len(reason) < 5:
            return Response({'detail': 'A reason (min 5 chars) is required to override.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if invoice.status not in (Invoice.Status.EXCEPTION, Invoice.Status.MATCH_EXCEPTION):
            return Response({'detail': 'Invoice is not in an exception state.'},
                            status=status.HTTP_400_BAD_REQUEST)
        invoice.status = (Invoice.Status.MATCHED if getattr(invoice, 'match_result', None)
                          else Invoice.Status.VALIDATED)
        invoice.save(update_fields=['status', 'updated_at'])
        from .models import ValidationResult
        ValidationResult.objects.create(
            invoice=invoice, check_code=ValidationResult.CheckCode.ADMIN_OVERRIDE,
            status=ValidationResult.Status.WARN,
            message=f'Exception overridden by {request.user.username}: {reason}',
            details={'reason': reason, 'previous_status': 'EXCEPTION'},
        )
        log(entity='Invoice', entity_id=invoice.pk, entity_repr=str(invoice),
            changes={'override': {'new': reason}})
        return Response({'detail': 'Exception overridden',
                         'invoice': InvoiceDetailSerializer(invoice).data})

    @action(detail=True, methods=['post'])
    def hold(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status in (Invoice.Status.PAID, Invoice.Status.CANCELLED):
            return Response({'detail': f'Cannot hold a {invoice.get_status_display()} invoice.'},
                            status=status.HTTP_400_BAD_REQUEST)
        invoice.status = Invoice.Status.ON_HOLD
        invoice.save(update_fields=['status', 'updated_at'])
        return Response({'detail': 'Invoice placed on hold'})



