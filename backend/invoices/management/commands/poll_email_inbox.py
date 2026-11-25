"""Optional IMAP inbox polling for automatic email ingestion."""
from django.core.management.base import BaseCommand

from invoices.services.email_ingest import poll_imap_inbox


class Command(BaseCommand):
    help = 'Poll the configured IMAP inbox and ingest invoice attachments (email ingestion).'

    def handle(self, *args, **options):
        result = poll_imap_inbox()
        if not result.get('enabled'):
            self.stdout.write(self.style.WARNING(result['detail']))
            return
        self.stdout.write(self.style.SUCCESS(f'Processed {len(result["messages"])} message(s)'))
