"""Run the approval escalation & reminder automation (cron-friendly)."""
from django.core.management.base import BaseCommand

from workflow.services import run_automation


class Command(BaseCommand):
    help = 'Escalate overdue approvals and send reminder notifications.'

    def handle(self, *args, **options):
        result = run_automation()
        self.stdout.write(self.style.SUCCESS(
            f"Escalated: {result['escalated']}, reminders sent: {result['reminders']}"))
