from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit import log
from core.permissions import IsAdmin, IsAdminOrClerk, IsFinanceOrAdmin
from .models import Vendor, VendorBankAccount
from .serializers import VendorBankAccountSerializer, VendorSerializer


class VendorViewSet(viewsets.ModelViewSet):
    """Vendor master + onboarding workflow: /api/vendors/"""
    serializer_class = VendorSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ('status',)
    search_fields = ('code', 'name', 'gstin', 'email')
    ordering_fields = ('name', 'code', 'created_at')

    def get_queryset(self):
        return Vendor.objects.annotate(
            invoice_count=Count('invoices', distinct=True),
            total_billed=Sum('invoices__total_amount'),
        )

    def perform_create(self, serializer):
        vendor = serializer.save(created_by=self.request.user, status=Vendor.Status.DRAFT)
        log(entity='Vendor', entity_id=vendor.pk, entity_repr=str(vendor))

    def perform_update(self, serializer):
        vendor = serializer.save()
        log(entity='Vendor', entity_id=vendor.pk, entity_repr=str(vendor))

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrClerk])
    def submit(self, request, pk=None):
        """Onboarding workflow step 1: DRAFT/REJECTED -> PENDING_APPROVAL."""
        vendor = self.get_object()
        if vendor.status not in (Vendor.Status.DRAFT, Vendor.Status.REJECTED):
            return Response(
                {'detail': f'Vendor in status {vendor.get_status_display()} cannot be submitted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        vendor.status = Vendor.Status.PENDING_APPROVAL
        vendor.save(update_fields=['status', 'updated_at'])
        log(entity='Vendor', entity_id=vendor.pk, entity_repr=str(vendor),
            changes={'status': {'new': 'PENDING_APPROVAL'}})
        return Response({'detail': 'Vendor submitted for approval'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        vendor = self.get_object()
        if vendor.status != Vendor.Status.PENDING_APPROVAL:
            return Response({'detail': 'Only pending vendors can be approved.'},
                            status=status.HTTP_400_BAD_REQUEST)
        vendor.status = Vendor.Status.APPROVED
        vendor.approved_by = request.user
        vendor.approved_at = timezone.now()
        vendor.onboarding_notes = request.data.get('notes', vendor.onboarding_notes)
        vendor.save(update_fields=['status', 'approved_by', 'approved_at', 'onboarding_notes', 'updated_at'])
        log(entity='Vendor', entity_id=vendor.pk, entity_repr=str(vendor),
            changes={'status': {'new': 'APPROVED'}})
        return Response({'detail': 'Vendor approved'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def reject(self, request, pk=None):
        vendor = self.get_object()
        if vendor.status != Vendor.Status.PENDING_APPROVAL:
            return Response({'detail': 'Only pending vendors can be rejected.'},
                            status=status.HTTP_400_BAD_REQUEST)
        vendor.status = Vendor.Status.REJECTED
        vendor.onboarding_notes = request.data.get('notes', '') or 'Rejected without notes.'
        vendor.save(update_fields=['status', 'onboarding_notes', 'updated_at'])
        log(entity='Vendor', entity_id=vendor.pk, entity_repr=str(vendor),
            changes={'status': {'new': 'REJECTED'}})
        return Response({'detail': 'Vendor rejected'})


class VendorBankAccountViewSet(viewsets.ModelViewSet):
    """Nested bank account management: /api/vendors/{vendor_pk}/bank-accounts/"""
    serializer_class = VendorBankAccountSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrClerk()]
        if self.action == 'verify':
            return [IsFinanceOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return VendorBankAccount.objects.filter(vendor_id=self.kwargs['vendor_pk'])

    def perform_create(self, serializer):
        vendor = Vendor.objects.get(pk=self.kwargs['vendor_pk'])
        if serializer.validated_data.get('is_primary'):
            vendor.bank_accounts.update(is_primary=False)
        account = serializer.save(vendor=vendor)
        log(entity='VendorBankAccount', entity_id=account.pk, entity_repr=str(account))

    def perform_update(self, serializer):
        account = serializer.save()
        log(entity='VendorBankAccount', entity_id=account.pk, entity_repr=str(account))

    def perform_destroy(self, instance):
        log(entity='VendorBankAccount', entity_id=instance.pk, entity_repr=str(instance))
        instance.delete()

    @action(detail=True, methods=['post'], permission_classes=[IsFinanceOrAdmin])
    def verify(self, request, vendor_pk=None, pk=None):
        account = self.get_object()
        account.is_verified = True
        account.save(update_fields=['is_verified'])
        log(entity='VendorBankAccount', entity_id=account.pk, entity_repr=str(account),
            changes={'is_verified': {'new': True}})
        return Response({'detail': 'Bank account marked as verified'})
