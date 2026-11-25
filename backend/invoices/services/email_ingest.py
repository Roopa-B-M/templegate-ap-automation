"""Email ingestion channel.

Two real ingestion paths:
1. API endpoint /api/invoices/email-ingest/ - the mail-room operator
   forwards an email's metadata + attachments through the UI/API.
2. Management command `poll_email_inbox` - connects to a configured IMAP
   mailbox (EMAIL_INGEST_* settings), downloads unseen message attachments
   and runs them through the same pipeline.
"""
import logging

from ..models import Invoice
from .pipeline import create_invoice_from_file, process_async

logger = logging.getLogger('invoices')


def ingest_email_attachments(files, user, from_email='', subject='', start_ocr=True):
    """Creates invoices (source=EMAIL) from attachments and starts OCR."""
    uploaded, failed = [], []
    for f in files:
        try:
            invoice = create_invoice_from_file(f, user, source=Invoice.Source.EMAIL)
            uploaded.append(invoice)
            if start_ocr:
                process_async(invoice)
        except ValueError as exc:
            failed.append({'file_name': getattr(f, 'name', '?'), 'reason': str(exc)})
    if uploaded:
        logger.info('Email ingestion from %s (%s): %s attachments accepted',
                    from_email or 'unknown', subject or 'no subject', len(uploaded))
    return uploaded, failed


def poll_imap_inbox(user=None):
    """Fetch unseen messages from the configured IMAP mailbox."""
    from django.conf import settings as s

    if not s.EMAIL_INGEST_HOST:
        return {'enabled': False, 'detail': 'EMAIL_INGEST_HOST is not configured.'}
    import email
    from email.header import decode_header
    import imaplib

    mail = imaplib.IMAP4_SSL(s.EMAIL_INGEST_HOST, s.EMAIL_INGEST_PORT)
    mail.login(s.EMAIL_INGEST_USER, s.EMAIL_INGEST_PASSWORD)
    mail.select('INBOX')
    status, data = mail.search(None, 'UNSEEN')
    results = []
    for num in data[0].split():
        _, msg_data = mail.fetch(num, '(RFC822)')
        message = email.message_from_bytes(msg_data[0][1])
        subject = ''
        raw = message.get('Subject', '')
        parts = decode_header(raw)
        subject = ''.join(
            part.decode(charset or 'utf-8', errors='ignore') if isinstance(part, bytes) else part
            for part, charset in parts
        )
        from_email = message.get('From', '')
        for part in message.walk():
            filename = part.get_filename()
            if filename and part.get_content_disposition() == 'attachment':
                content = part.get_payload(decode=True)
                if not content:
                    continue
                from django.core.files.base import ContentFile
                attachment = ContentFile(content, name=filename)
                uploaded, failed = ingest_email_attachments(
                    [attachment], user, from_email=from_email, subject=subject)
                results.append({'subject': subject, 'uploaded': len(uploaded), 'failed': failed})
        mail.store(num, '+FLAGS', '\\Seen')
    mail.logout()
    return {'enabled': True, 'messages': results}
