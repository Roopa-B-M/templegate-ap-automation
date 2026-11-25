"""Ingest all invoice files from a local folder through the email pipeline.

Demo-friendly alternative to a real IMAP mailbox: every supported file in
<path> is created as an Invoice with source=EMAIL and pushed through the
same OCR/validation pipeline as attachments ingested by `poll_email_inbox`
or the /api/invoices/email-ingest/ endpoint.

Usage:
    python manage.py ingest_folder /path/to/folder
    python manage.py ingest_folder /path/to/folder --from-email vendor@example.com
    python manage.py ingest_folder sample_invoices --subject "Monthly invoices"
"""
import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from django.conf import settings

from invoices.services.email_ingest import ingest_email_attachments


class Command(BaseCommand):
    help = ('Ingest every supported invoice file in a local folder as if it arrived '
            'by email (source=EMAIL).')

    def add_arguments(self, parser):
        parser.add_argument('path', help='Folder containing invoice files (PDF/JPG/PNG/TIFF).')
        parser.add_argument('--from-email', default='vendor@example.com',
                            help='From address recorded on the ingested invoices.')
        parser.add_argument('--subject', default='Folder ingestion',
                            help='Subject recorded for this batch.')
        parser.add_argument('--user', default='ap.clerk',
                            help='Username of the account the ingestion is attributed to.')
        parser.add_argument('--no-ocr', action='store_true',
                            help='Only create the invoices (OCR stays pending).')

    def handle(self, *args, **options):
        folder = options['path']
        if not os.path.isdir(folder):
            raise CommandError(f'"{folder}" is not a directory.')

        allowed = settings.ALLOWED_INVOICE_EXTENSIONS
        names = sorted(os.listdir(folder))
        targets = [n for n in names if os.path.splitext(n)[1].lower() in allowed]

        # Skip the readme - only files with supported extensions are ingested.
        if not targets:
            raise CommandError(f'No supported invoice files ({", ".join(sorted(allowed))}) in "{folder}".')

        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(username=options['user']).first() or User.objects.filter(
            is_superuser=True).first()
        if user is None:
            raise CommandError('No user found; run migrations and create a user first.')

        self.stdout.write(f'Ingesting {len(targets)} file(s) from {folder} as source=EMAIL ...')
        files = []
        for name in targets:
            with open(os.path.join(folder, name), 'rb') as fh:
                files.append(ContentFile(fh.read(), name=name))
        uploaded, failed = ingest_email_attachments(
            files, user, from_email=options['from_email'], subject=options['subject'],
            start_ocr=not options['no_ocr'])

        if options['no_ocr']:
            self.stdout.write(self.style.WARNING('OCR left pending (--no-ocr). Run '
                                                 'python manage.py process_pending_ocr later.'))
        for invoice in uploaded:
            self.stdout.write(f'  created Invoice #{invoice.pk} from {invoice.file_name} '
                              f'(OCR {invoice.ocr_status})')
        for failure in failed:
            self.stdout.write(self.style.WARNING(f"  rejected {failure['file_name']}: {failure['reason']}"))
        self.stdout.write(self.style.SUCCESS(
            f'Done: {len(uploaded)} ingested, {len(failed)} rejected.'))
