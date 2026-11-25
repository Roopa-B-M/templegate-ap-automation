from django.http import FileResponse, HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Notification
from core.audit import log
from core.permissions import IsFinanceOrAdmin
from invoices.models import Invoice
from .models import PaymentRequest
from .serializers import PaymentSerializer
from .services import (BankGatewayError, create_payment, generate_payment_advice_pdf,
                       generate_payment_number, get_bank_gateway, process_payment,
                       reconcile_bank_statement)


class PaymentViewSet(viewsets.ModelViewSet):
    """/api/payments/ - payment requests, approvals, bank execution, advice."""
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ('status', 'method')
    search_fields = ('payment_number', 'invoice__invoice_number', 'invoice__vendor__name')
    ordering_fields = ('created_at', 'scheduled_date', 'amount')
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return PaymentRequest.objects.select_related('invoice', 'invoice__vendor',
                                                     'requested_by', 'approved_by')

    def get_permissions(self):
        if self.action in ('create', 'approve', 'schedule', 'process', 'cancel'):
            return [IsFinanceOrAdmin()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        invoice_id = request.data.get('invoice_id')
        method = (request.data.get('method') or 'NEFT').upper()
        scheduled_date = request.data.get('scheduled_date') or None
        invoice = Invoice.objects.filter(pk=invoice_id).first()
        if invoice is None:
            return Response({'detail': 'Invoice not found.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payment = create_payment(invoice, request.user, method, scheduled_date)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log(entity='PaymentRequest', entity_id=payment.pk, entity_repr=str(payment),
            changes={'created': {'new': payment.payment_number}})
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        payment = self.get_object()
        if payment.status != PaymentRequest.Status.PENDING_APPROVAL:
            return Response({'detail': f'Payment is {payment.get_status_display()}.'},
                            status=status.HTTP_400_BAD_REQUEST)
        payment.status = PaymentRequest.Status.APPROVED
        payment.approved_by = request.user
        payment.save(update_fields=['status', 'approved_by', 'updated_at'])
        log(entity='PaymentRequest', entity_id=payment.pk, entity_repr=str(payment),
            changes={'status': {'new': 'APPROVED'}})
        return Response({'detail': 'Payment approved'})

    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        payment = self.get_object()
        if payment.status != PaymentRequest.Status.APPROVED:
            return Response({'detail': 'Only approved payments can be scheduled.'},
                            status=status.HTTP_400_BAD_REQUEST)
        scheduled = request.data.get('scheduled_date')
        if not scheduled:
            return Response({'detail': 'scheduled_date is required.'}, status=status.HTTP_400_BAD_REQUEST)
        payment.scheduled_date = scheduled
        payment.status = PaymentRequest.Status.SCHEDULED
        payment.save(update_fields=['scheduled_date', 'status', 'updated_at'])
        payment.invoice.status = Invoice.Status.SCHEDULED
        payment.invoice.save(update_fields=['status', 'updated_at'])
        log(entity='PaymentRequest', entity_id=payment.pk, entity_repr=str(payment),
            changes={'status': {'new': 'SCHEDULED'}, 'scheduled_date': {'new': scheduled}})
        return Response({'detail': f'Payment scheduled for {scheduled}'})

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """Executes the (simulated) banking transfer."""
        payment = self.get_object()
        try:
            process_payment(payment)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log(entity='PaymentRequest', entity_id=payment.pk, entity_repr=str(payment),
            changes={'status': {'new': payment.status},
                     'bank_reference': {'new': payment.bank_reference}})
        detail = ('Payment processed. UTR: ' + payment.bank_reference if payment.bank_reference
                  else f'Payment failed: {payment.failure_reason}')
        return Response({'detail': detail, 'status': payment.status,
                         'payment': PaymentSerializer(payment).data})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        payment = self.get_object()
        if payment.status == PaymentRequest.Status.PROCESSED:
            return Response({'detail': 'Processed payments cannot be cancelled.'},
                            status=status.HTTP_400_BAD_REQUEST)
        payment.status = PaymentRequest.Status.CANCELLED
        payment.save(update_fields=['status', 'updated_at'])
        if payment.invoice.status in (Invoice.Status.PAYMENT_REQUESTED, Invoice.Status.SCHEDULED,
                                      Invoice.Status.PAYMENT_FAILED):
            payment.invoice.status = Invoice.Status.APPROVED
            payment.invoice.save(update_fields=['status', 'updated_at'])
        log(entity='PaymentRequest', entity_id=payment.pk, entity_repr=str(payment),
            changes={'status': {'new': 'CANCELLED'}})
        return Response({'detail': 'Payment cancelled; invoice returned to approved'})


    @action(detail=False, methods=['get'], url_path='bank-mode')
    def bank_mode(self, request):
        """GET /api/payments/bank-mode/ - which gateway is active (for UI labels)."""
        gateway = get_bank_gateway()
        return Response({'mode': 'simulated' if gateway.name == 'SimulatedBankGateway' else 'file',
                         'gateway': gateway.name,
                         'note': ('Bank transfers are simulated locally. No live bank connection '
                                  'is made.' if gateway.name == 'SimulatedBankGateway' else
                                  'File mode: export payment instructions and reconcile the bank '
                                  'statement; no live bank link.')})

    @action(detail=False, methods=['post'], url_path='bank-file')
    def bank_file(self, request):
        """POST /api/payments/bank-file/ {payment_ids: [...]} - NEFT/RTGS bulk CSV."""
        payment_ids = request.data.get('payment_ids') or []
        if not payment_ids:
            return Response({'detail': 'payment_ids is required.'}, status=status.HTTP_400_BAD_REQUEST)
        payments = (PaymentRequest.objects.filter(pk__in=payment_ids)
                    .select_related('invoice', 'invoice__vendor')
                    .order_by('scheduled_date', 'id'))
        if not payments:
            return Response({'detail': 'No matching payments found.'}, status=status.HTTP_400_BAD_REQUEST)
        not_scheduled = [p.payment_number for p in payments if p.status != PaymentRequest.Status.SCHEDULED]
        if not_scheduled:
            return Response({'detail': 'Only SCHEDULED payments can be exported; found other status: '
                                       + ', '.join(not_scheduled)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            filename, content_type, payload = get_bank_gateway().generate_bulk_file(payments)
        except BankGatewayError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log(entity='PaymentRequest', entity_id=0, entity_repr='bulk bank file',
            changes={'payments': {'new': list(payments.values_list('payment_number', flat=True))},
                     'filename': {'new': filename}})
        response = HttpResponse(payload, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class PaymentStatementReconcileView(APIView):
    """POST /api/payments/reconcile-statement/ - upload a bank statement CSV."""
    permission_classes = (IsFinanceOrAdmin,)

    def post(self, request):
        upload = request.FILES.get('file') or request.FILES.get('statement')
        if upload is None:
            return Response({'detail': 'Attach the statement CSV as "file".'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            result = reconcile_bank_statement(upload, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log(entity='PaymentRequest', entity_id=0, entity_repr='bank statement reconcile',
            changes={'matched': {'new': len(result['matched'])},
                     'unmatched': {'new': len(result['unmatched'])}})
        return Response({'detail': f"Reconciled {len(result['matched'])} payment(s); "
                                   f"{len(result['unmatched'])} unmatched row(s).",
                         **result})


class PaymentAdviceView(APIView):
    """GET /api/payments/{id}/advice/ - downloadable remittance advice PDF."""

    def get(self, request, payment_id):
        payment = PaymentRequest.objects.filter(pk=payment_id).first()
        if payment is None:
            return Response({'detail': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)
        pdf_bytes = generate_payment_advice_pdf(payment)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="payment-advice-{payment.payment_number}.pdf"'
        return response
