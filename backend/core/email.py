"""Email notification helpers.

Notification emails (approval requests, reminders, escalations) are sent
through Django's standard email backend (console backend by default in
development - see EMAIL_BACKEND in settings). Failures are logged and never
propagate: a broken SMTP server must not break the approval workflow.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger('workflow')


def send_notification_email(user, subject, message, link=''):
    """Best-effort email to a user. Returns True when the email was sent."""
    try:
        recipient = getattr(user, 'email', '') or ''
        if not recipient:
            return False
        body = message
        if link:
            body = f'{message}\n\nOpen in the AP Automation app: {link}'
        sent = send_mail(
            subject=f'[AP Automation] {subject}',
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'ap-automation@templegate.example.com'),
            recipient_list=[recipient],
            fail_silently=False,
        )
        return bool(sent)
    except Exception as exc:  # noqa: BLE001 - email must never break the workflow
        logger.warning('Notification email to %s failed: %s', getattr(user, 'username', '?'), exc)
        return False
