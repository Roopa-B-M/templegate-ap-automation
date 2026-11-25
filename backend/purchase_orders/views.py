from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit import log
from core.permissions import IsAdminOrClerk
from invoices.models import Invoice
from .models import GRN, PurchaseOrder
from .serializers import GRNSerializer, PurchaseOrderSerializer


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """/api/purchase-orders/ - create/list/retrieve + status transitions."""
    serializer_class = PurchaseOrderSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ('status', 'vendor')
    search_fields = ('po_number', 'vendor__name')
    ordering_fields = ('po_date', 'po_number', 'total_amount')

    def get_queryset(self):
        return PurchaseOrder.objects.select_related('vendor').annotate(
            invoice_count=Count('invoices', distinct=True),
        )

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrClerk()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        po = serializer.save(created_by=self.request.user)
        log(entity='PurchaseOrder', entity_id=po.pk, entity_repr=str(po))

    @action(detail=True, methods=['patch', 'post'])
    def status(self, request, pk=None):
        po = self.get_object()
        new_status = (request.data.get('status') or '').upper()
        if new_status not in PurchaseOrder.Status.values:
            return Response({'detail': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
        po.status = new_status
        po.save(update_fields=['status', 'updated_at'])
        log(entity='PurchaseOrder', entity_id=po.pk, entity_repr=str(po),
            changes={'status': {'new': new_status}})
        return Response({'detail': f'PO marked {new_status}'})


class GRNViewSet(viewsets.ModelViewSet):
    """/api/grns/ - list/retrieve + create (goods receipt posting)."""
    serializer_class = GRNSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ('po',)
    search_fields = ('grn_number', 'po__po_number')
    ordering_fields = ('receipt_date', 'grn_number')
    http_method_names = ['get', 'post', 'head', 'options']  # receipts are immutable once posted

    def get_queryset(self):
        return GRN.objects.select_related('po', 'po__vendor', 'received_by').prefetch_related('lines__po_line')

    def get_permissions(self):
        if self.action == 'create':
            return [IsAdminOrClerk()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        grn = serializer.save(received_by=self.request.user)
        log(entity='GRN', entity_id=grn.pk, entity_repr=str(grn))
