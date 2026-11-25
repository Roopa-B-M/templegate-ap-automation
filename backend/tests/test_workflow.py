"""Approval workflow tests: matrix levels, parallel approval, escalation, reminders."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import Notification
from invoices.models import Invoice
from tests.utils import D, make_manual_invoice, make_user, make_vendor
from workflow.models import ApprovalMatrix, ApprovalTask
from workflow.services import act_on_task, run_automation, start_approval

Decimal = D


class WorkflowTests(TestCase):
    def setUp(self):
        self.vendor = make_vendor(code='V-WF')
        self.clerk = make_user('wf-clerk', 'AP_CLERK')
        self.approver1 = make_user('wf-appr1', 'APPROVER')
        self.approver2 = make_user('wf-appr2', 'APPROVER')
        self.finance1 = make_user('wf-fin1', 'FINANCE')
        self.finance2 = make_user('wf-fin2', 'FINANCE')
        self.admin = make_user('wf-admin', 'ADMIN', is_staff=True, is_superuser=True)
        ApprovalMatrix.objects.create(name='Level 1', level=1, min_amount=Decimal('0'),
                                      max_amount=Decimal('50000'), approver_role='APPROVER',
                                      escalation_hours=48)
        ApprovalMatrix.objects.create(name='Level 2', level=2, min_amount=Decimal('50000.01'),
                                      max_amount=None, approver_role='FINANCE',
                                      escalation_hours=24)

    def _invoice(self, number='INV-WF1', amount=Decimal('17090.00')):
        invoice = make_manual_invoice(self.vendor, invoice_number=number)
        Invoice.objects.filter(pk=invoice.pk).update(total_amount=amount)
        invoice.refresh_from_db()
        return invoice

    def test_start_approval_creates_task_and_notifies(self):
        invoice = self._invoice()
        tasks = start_approval(invoice, self.clerk)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].approver_role, 'APPROVER')
        self.assertTrue(tasks[0].is_active)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PENDING_APPROVAL)
        self.assertTrue(Notification.objects.filter(user=tasks[0].approver, type='APPROVAL').exists())

    def test_sequential_levels_activate_in_order(self):
        invoice = self._invoice(amount=Decimal('85000'))  # matches level 2 (finance)
        tasks = start_approval(invoice, self.clerk)
        self.assertEqual(tasks[0].approver_role, 'FINANCE')
        act_on_task(tasks[0], self.finance1, 'approve', comments='ok')
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.APPROVED)

    def test_rejection_skips_remaining_tasks(self):
        invoice = self._invoice(amount=Decimal('85000'))
        tasks = start_approval(invoice, self.clerk)
        act_on_task(tasks[0], self.finance1, 'reject', comments='price wrong')
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.REJECTED)
        tasks[0].refresh_from_db()
        self.assertEqual(tasks[0].status, ApprovalTask.Status.REJECTED)

    def test_parallel_approval_requires_every_user_of_role(self):
        # Remove the overlapping level-2 band so only the parallel rule matches.
        ApprovalMatrix.objects.filter(level=2).delete()
        matrix = ApprovalMatrix.objects.create(
            name='Finance Parallel', level=3, min_amount=Decimal('100000'),
            max_amount=None, approver_role='FINANCE', is_parallel=True, escalation_hours=24)
        invoice = self._invoice(amount=Decimal('150000'))
        tasks = start_approval(invoice, self.clerk)
        finance_tasks = [t for t in tasks if t.approver_role == 'FINANCE']
        self.assertEqual(len(finance_tasks), 2)  # finance1 + finance2

        # First approval does NOT complete the level.
        act_on_task([t for t in finance_tasks if t.approver == self.finance1][0],
                    self.finance1, 'approve')
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PENDING_APPROVAL)
        # Second approval completes the parallel level.
        act_on_task([t for t in finance_tasks if t.approver == self.finance2][0],
                    self.finance2, 'approve')
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.APPROVED)

    def test_approver_role_is_enforced(self):
        invoice = self._invoice()
        tasks = start_approval(invoice, self.clerk)
        with self.assertRaises(ValueError):
            act_on_task(tasks[0], self.clerk, 'approve')  # clerk cannot approve

    def test_inactive_future_levels_blocked(self):
        # Add a wide level-1 band so BOTH levels match 150000: level 1 active,
        # level 2 (finance) must wait for the earlier level to complete.
        ApprovalMatrix.objects.create(name='Wide Level 1', level=1, min_amount=Decimal('0'),
                                      max_amount=None, approver_role='APPROVER',
                                      escalation_hours=48)
        invoice = self._invoice(amount=Decimal('150000'))
        tasks = start_approval(invoice, self.clerk)
        finance_tasks = [t for t in tasks if t.approver_role == 'FINANCE']
        self.assertTrue(finance_tasks)
        with self.assertRaises(ValueError):
            act_on_task(finance_tasks[0], self.finance1, 'approve')

    def test_escalation_moves_overdue_task_to_admin(self):
        invoice = self._invoice()
        tasks = start_approval(invoice, self.clerk)
        task = tasks[0]
        # Simulate an overdue task (created 3 days ago, escalation after 48h).
        ApprovalTask.objects.filter(pk=task.pk).update(
            created_at=timezone.now() - timedelta(hours=72))
        ApprovalTask.objects.filter(pk=task.pk).update(
            due_at=timezone.now() - timedelta(hours=24))
        result = run_automation()
        task.refresh_from_db()
        self.assertEqual(task.approver, self.admin)
        self.assertEqual(task.approver_role, 'ADMIN')
        self.assertTrue(task.escalated)
        self.assertGreaterEqual(result['escalated'], 1)
        self.assertTrue(Notification.objects.filter(type='ESCALATION').exists())

    def test_reminder_sent_after_interval(self):
        invoice = self._invoice()
        tasks = start_approval(invoice, self.clerk)
        task = tasks[0]
        reminder_every = max(6, task.escalation_hours // 2)
        ApprovalTask.objects.filter(pk=task.pk).update(
            created_at=timezone.now() - timedelta(hours=reminder_every + 1))
        before = task.reminder_count
        result = run_automation()
        task.refresh_from_db()
        self.assertGreater(task.reminder_count, before)
        self.assertGreaterEqual(result['reminders'], 1)
        self.assertTrue(Notification.objects.filter(user=task.approver, type='WARNING').exists())

    def test_no_matrix_rule_raises_helpful_error(self):
        ApprovalMatrix.objects.all().delete()
        invoice = self._invoice()
        with self.assertRaises(ValueError):
            start_approval(invoice, self.clerk)
