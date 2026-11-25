from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit import log
from core.permissions import IsAdmin
from invoices.models import Invoice
from .models import ApprovalMatrix, ApprovalTask
from .serializers import ApprovalMatrixSerializer, ApprovalTaskSerializer
from .services import act_on_task, run_automation


class ApprovalTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """/api/approvals/ - the approver's inbox."""
    serializer_class = ApprovalTaskSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ('status', 'level', 'approver_role')
    ordering_fields = ('due_at', 'created_at', 'level')

    def get_queryset(self):
        user = self.request.user
        qs = ApprovalTask.objects.select_related('invoice', 'invoice__vendor', 'approver')
        if not (user.is_superuser or user.role == 'ADMIN'):
            qs = qs.filter(approver=user)
        return qs.order_by('due_at', 'id')

    @action(detail=True, methods=['post'])
    def action(self, request, pk=None):
        """POST /api/approvals/{id}/action/ {action: approve|reject, comments}"""
        task = self.get_object()
        act = (request.data.get('action') or '').lower()
        comments = request.data.get('comments', '')
        if act not in ('approve', 'reject'):
            return Response({'detail': "action must be 'approve' or 'reject'."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            act_on_task(task, request.user, act, comments)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        invoice = Invoice.objects.get(pk=task.invoice_id)
        return Response({'detail': f'Task {act}d successfully. Invoice status: '
                                   f'{invoice.get_status_display()}'})


class ApprovalMatrixViewSet(viewsets.ModelViewSet):
    """/api/workflow/matrix/ - configurable approval matrix (admin)."""
    queryset = ApprovalMatrix.objects.all()
    serializer_class = ApprovalMatrixSerializer
    permission_classes = (IsAdmin,)
    filterset_fields = ('approver_role', 'active', 'is_parallel')
    ordering_fields = ('level',)

    def perform_create(self, serializer):
        matrix = serializer.save()
        log(entity='ApprovalMatrix', entity_id=matrix.pk, entity_repr=str(matrix))

    def perform_update(self, serializer):
        matrix = serializer.save()
        log(entity='ApprovalMatrix', entity_id=matrix.pk, entity_repr=str(matrix))

    def perform_destroy(self, instance):
        log(entity='ApprovalMatrix', entity_id=instance.pk, entity_repr=str(instance))
        instance.delete()

    @action(detail=False, methods=['post'], url_path='run-automation')
    def run_automation_view(self, request):
        """POST /api/workflow/matrix/run-automation/ - escalation & reminders."""
        result = run_automation()
        log(entity='System', entity_id=0, entity_repr='workflow automation',
            changes={'result': {'new': result}})
        return Response(result)
