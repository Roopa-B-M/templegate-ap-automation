"""Approval workflow engine: task generation, sequential/parallel approvals,
escalation and reminder automation."""
import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Notification
from core.audit import log
from core.email import send_notification_email
from invoices.models import Invoice
from .models import ApprovalMatrix, ApprovalTask

logger = logging.getLogger('workflow')
User = get_user_model()


def _notify(user, title, message, notif_type=Notification.Types.INFO, link=''):
    """In-app notification + best-effort email to the same recipient."""
    Notification.objects.create(user=user, title=title, message=message,
                                type=notif_type, link=link)
    send_notification_email(user, title, message, link=link)


def start_approval(invoice, requester):
    """Generate approval tasks from the active matrix and notify assignees."""
    amount = invoice.total_amount or Decimal('0')
    rules = [r for r in ApprovalMatrix.objects.filter(active=True).order_by('level')
             if r.min_amount <= amount and (r.max_amount is None or amount <= r.max_amount)]
    if not rules:
        raise ValueError('No active approval matrix rule matches this invoice amount. '
                         'Ask an administrator to configure the approval matrix.')

    # Resubmission: clear any previous (unfinished) tasks
    invoice.approval_tasks.all().delete()

    created_tasks = []
    for rule in rules:
        if rule.is_parallel:
            approvers = list(User.objects.filter(role=rule.approver_role, is_active=True)
                             .exclude(pk=invoice.created_by_id))
            if not approvers:
                raise ValueError(f'No active user with role {rule.approver_role} exists to '
                                 f'approve level {rule.level} (parallel).')
        else:
            candidates = list(User.objects.filter(role=rule.approver_role, is_active=True)
                              .exclude(pk=invoice.created_by_id))
            if not candidates:
                raise ValueError(f'No active user with role {rule.approver_role} exists to '
                                 f'approve level {rule.level}.')
            # least-loaded assignment
            load = {u.pk: ApprovalTask.objects.filter(approver=u, status=ApprovalTask.Status.PENDING).count()
                    for u in candidates}
            approvers = [min(candidates, key=lambda u: load[u.pk])]

        for approver in approvers:
            task = ApprovalTask.objects.create(
                invoice=invoice, matrix=rule, level=rule.level,
                approver=approver, approver_role=rule.approver_role,
                is_parallel=rule.is_parallel, escalation_hours=rule.escalation_hours,
                due_at=timezone.now() + timedelta(hours=rule.escalation_hours),
                is_active=(rule == rules[0]),
            )
            created_tasks.append(task)
            if task.is_active:
                _notify(approver, 'Approval required',
                        f'Invoice {invoice.invoice_number or invoice.pk} '
                        f'({invoice.vendor.name if invoice.vendor else "no vendor"}) - '
                        f'amount {invoice.total_amount} needs your approval at level {rule.level}.',
                        Notification.Types.APPROVAL, link=f'/invoices/{invoice.pk}')

    invoice.status = Invoice.Status.PENDING_APPROVAL
    invoice.save(update_fields=['status', 'updated_at'])
    log(entity='Invoice', entity_id=invoice.pk, entity_repr=str(invoice),
        changes={'submit_approval': {'new': f'{len(created_tasks)} tasks'}})
    logger.info('Invoice %s submitted for approval: %s tasks',
                invoice.pk, len(created_tasks))
    return created_tasks


def _activate_next_level(invoice):
    """Activate the first level with pending tasks after a level completes."""
    for task in invoice.approval_tasks.order_by('level'):
        if task.status == ApprovalTask.Status.PENDING and not task.is_active:
            task.is_active = True
            task.save(update_fields=['is_active'])
            if task.approver:
                _notify(task.approver, 'Approval required',
                        f'Invoice {invoice.invoice_number or invoice.pk} advanced to level '
                        f'{task.level} - your approval is now required.',
                        Notification.Types.APPROVAL, link=f'/invoices/{invoice.pk}')


def act_on_task(task, user, action, comments=''):
    """Approve/reject one task; drives the invoice state machine."""
    if task.status != ApprovalTask.Status.PENDING:
        raise ValueError(f'Task already {task.get_status_display().lower()}.')
    if not task.is_active:
        raise ValueError('This task is waiting for a previous approval level to complete.')
    if not (user.is_superuser or user.role == task.approver_role or task.approver_id == user.id):
        raise ValueError('You are not authorised to act on this approval task.')

    invoice = task.invoice
    if action == 'approve':
        task.status = ApprovalTask.Status.APPROVED
        task.approved_at = timezone.now()
        task.comments = comments or task.comments
        task.save()
        pending_same_level = invoice.approval_tasks.filter(level=task.level, status=ApprovalTask.Status.PENDING).exists()
        if not pending_same_level:
            pending_any = invoice.approval_tasks.filter(status=ApprovalTask.Status.PENDING).exists()
            if pending_any:
                _activate_next_level(invoice)
            else:
                invoice.status = Invoice.Status.APPROVED
                invoice.approved_at = timezone.now()
                invoice.save(update_fields=['status', 'approved_at', 'updated_at'])
                if invoice.created_by:
                    _notify(invoice.created_by, 'Invoice approved',
                            f'Invoice {invoice.invoice_number or invoice.pk} has been fully approved '
                            'and is ready for payment processing.',
                            Notification.Types.SUCCESS, link=f'/invoices/{invoice.pk}')
        log(user=user, entity='ApprovalTask', entity_id=task.pk, entity_repr=str(task),
            changes={'action': {'new': 'APPROVE'}, 'comments': {'new': comments}})
        logger.info('Task %s approved by %s', task.pk, user.username)
    elif action == 'reject':
        task.status = ApprovalTask.Status.REJECTED
        task.comments = comments or 'Rejected without comments.'
        task.save()
        invoice.approval_tasks.filter(status=ApprovalTask.Status.PENDING).exclude(pk=task.pk) \
            .update(status=ApprovalTask.Status.SKIPPED)
        invoice.status = Invoice.Status.REJECTED
        invoice.save(update_fields=['status', 'updated_at'])
        if invoice.created_by:
            _notify(invoice.created_by, 'Invoice rejected',
                    f'Invoice {invoice.invoice_number or invoice.pk} was rejected at level '
                    f'{task.level} by {user.username}. Comments: {task.comments}',
                    Notification.Types.ERROR, link=f'/invoices/{invoice.pk}')
        log(user=user, entity='ApprovalTask', entity_id=task.pk, entity_repr=str(task),
            changes={'action': {'new': 'REJECT'}, 'comments': {'new': task.comments}})
        logger.info('Task %s rejected by %s', task.pk, user.username)
    else:
        raise ValueError("Action must be 'approve' or 'reject'.")
    return task


def run_automation():
    """Escalation + reminder pass. Called by management command / admin endpoint."""
    now = timezone.now()
    escalated_count = 0
    reminder_count = 0

    for task in ApprovalTask.objects.filter(status=ApprovalTask.Status.PENDING, is_active=True) \
            .select_related('invoice', 'approver'):
        invoice = task.invoice
        hours_open = (now - task.created_at).total_seconds() / 3600
        link = f'/invoices/{invoice.pk}'

        if not task.escalated and hours_open >= task.escalation_hours:
            admins = list(User.objects.filter(role=User.Roles.ADMIN, is_active=True))
            if admins:
                task.escalated = True
                task.approver = admins[0]
                task.approver_role = User.Roles.ADMIN
                task.due_at = now + timedelta(hours=24)
                task.save(update_fields=['escalated', 'approver', 'approver_role', 'due_at'])
                escalated_count += 1
                for admin in admins:
                    _notify(admin, 'Approval escalated',
                            f'Invoice {invoice.invoice_number or invoice.pk} was not approved within '
                            f'{task.escalation_hours}h and has been escalated to you (level {task.level}).',
                            Notification.Types.ESCALATION, link=link)
                if invoice.created_by:
                    _notify(invoice.created_by, 'Approval escalated',
                            f'Approval of invoice {invoice.invoice_number or invoice.pk} has been escalated.',
                            Notification.Types.ESCALATION, link=link)
                logger.warning('Task %s escalated to admin', task.pk)
        else:
            reminder_every = max(6, (task.escalation_hours // 2) or 6)
            if hours_open >= reminder_every * (task.reminder_count + 1):
                task.reminder_count += 1
                task.save(update_fields=['reminder_count'])
                reminder_count += 1
                if task.approver:
                    _notify(task.approver, 'Approval reminder',
                            f'Reminder ({task.reminder_count}): invoice '
                            f'{invoice.invoice_number or invoice.pk} awaits your approval (level {task.level}).',
                            Notification.Types.WARNING, link=link)

    logger.info('Workflow automation run: %s escalated, %s reminders', escalated_count, reminder_count)
    return {'escalated': escalated_count, 'reminders': reminder_count}
