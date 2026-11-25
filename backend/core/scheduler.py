"""In-process background scheduler (optional, APScheduler-based).

Started from CoreConfig.ready() via `autostart()` and from wsgi.py for
production servers. Guards:

- never starts when SCHEDULER_ENABLED is false (default);
- never starts for management commands other than `runserver`
  (migrate / test / shell / seed_demo etc.);
- does not start twice under the Django autoreloader (RUN_MAIN check +
  a module-level started flag);
- every job swallows exceptions and logs them so one bad run never kills
  the scheduler thread.

Jobs (intervals via .env, see SCHEDULER_* in .env.example):
- workflow automation: approval escalation + reminders
- pending OCR processing (catch-up after restarts)
- IMAP email inbox polling (only when EMAIL_INGEST_HOST is configured)
"""
import logging
import os
import sys

from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger('workflow')

_started = False
_scheduler = None

# Commands that must NEVER trigger the scheduler when invoked via manage.py.
_BLOCKED_COMMANDS = {
    'test', 'migrate', 'makemigrations', 'shell', 'shell_plus', 'dbshell',
    'check', 'collectstatic', 'seed_demo', 'generate_sample_invoices',
    'ingest_folder', 'process_pending_ocr', 'run_workflow_automation',
    'poll_email_inbox', 'showmigrations', 'sqlmigrate', 'flush', 'dumpdata',
    'loaddata', 'createsuperuser', 'startapp', 'startproject', 'inspectdb',
    'runfcgi', 'squashmigrations', 'sendtestemail', 'diffsettings',
}


def _manage_py_invocation():
    return len(sys.argv) > 0 and sys.argv[0].endswith('manage.py')


def _is_test_run():
    """True under `manage.py test` or pytest."""
    if _manage_py_invocation() and len(sys.argv) > 1 and sys.argv[1] in ('test', 'testserver'):
        return True
    if any(arg for arg in sys.argv if 'pytest' in str(arg) or 'py.test' in str(arg)):
        return True
    return 'PYTEST_CURRENT_TEST' in os.environ


def can_autostart():
    """Decide whether this process may start the scheduler."""
    if not getattr(settings, 'SCHEDULER_ENABLED', False):
        return False
    if _is_test_run():
        return False
    if _manage_py_invocation():
        command = sys.argv[1] if len(sys.argv) > 1 else ''
        if command in _BLOCKED_COMMANDS:
            return False
        if command != 'runserver':
            # Unknown/other commands: stay safe and do not start.
            return False
        # Under the autoreloader only the child process (RUN_MAIN=true) runs jobs.
        if 'RUN_MAIN' not in os.environ and '--noreload' not in sys.argv:
            return False
    # WSGI/ASGI servers (gunicorn, waitress, daphne...) have no manage.py in
    # argv - they are production contexts and may start.
    return True


def _job(job_name):
    """Wrap a job function with connection hygiene + error containment."""
    def wrapper():
        from django.db import connection

        try:
            close_old_connections()
            fn = _JOBS[job_name]
            result = fn()
            logger.info('Scheduler job %s finished: %s', job_name, result)
        except Exception as exc:  # noqa: BLE001 - never kill the scheduler thread
            logger.exception('Scheduler job %s failed: %s', job_name, exc)
        finally:
            try:
                close_old_connections()
                connection.close()
            except Exception:  # noqa: BLE001
                pass
    wrapper.__name__ = f'scheduler_{job_name}'
    return wrapper


def _job_workflow_automation():
    from workflow.services import run_automation
    return run_automation()


def _job_process_pending_ocr():
    from invoices.models import Invoice
    from invoices.services.pipeline import process_ocr

    pending = Invoice.objects.filter(ocr_status__in=[Invoice.OcrStatus.PENDING,
                                                     Invoice.OcrStatus.PROCESSING])
    count = pending.count()
    for invoice in pending.iterator():
        process_ocr(invoice.pk)
    return {'processed': count}


def _job_poll_email_inbox():
    from invoices.services.email_ingest import poll_imap_inbox

    result = poll_imap_inbox()
    if not result.get('enabled'):
        return result
    return {'messages': len(result.get('messages', []))}


_JOBS = {
    'workflow_automation': _job_workflow_automation,
    'process_pending_ocr': _job_process_pending_ocr,
    'poll_email_inbox': _job_poll_email_inbox,
}


def start():
    """Create and start the BackgroundScheduler (idempotent)."""
    global _started, _scheduler
    if _started:
        return _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning('APScheduler not installed; background scheduler disabled.')
        return None

    scheduler = BackgroundScheduler(daemon=True, coalesce=True, max_instances=1)
    intervals = {
        'workflow_automation': max(30, getattr(settings, 'SCHEDULER_WORKFLOW_SECONDS', 300)),
        'process_pending_ocr': max(30, getattr(settings, 'SCHEDULER_OCR_SECONDS', 60)),
        'poll_email_inbox': max(60, getattr(settings, 'SCHEDULER_EMAIL_SECONDS', 300)),
    }
    for job_name, seconds in intervals.items():
        if job_name == 'poll_email_inbox' and not getattr(settings, 'EMAIL_INGEST_HOST', ''):
            logger.info('Email inbox polling skipped (EMAIL_INGEST_HOST not configured).')
            continue
        scheduler.add_job(_job(job_name), 'interval', seconds=seconds,
                          id=job_name, replace_existing=True)
        logger.info('Scheduled job %s every %ss', job_name, seconds)
    scheduler.start()
    _started = True
    _scheduler = scheduler
    logger.info('Background scheduler started (%s jobs).', len(scheduler.get_jobs()))
    return scheduler


def autostart():
    """Called from CoreConfig.ready() and wsgi.py; applies all guards."""
    if can_autostart():
        return start()
    return None


def shutdown():
    global _started, _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
    _started = False
    _scheduler = None
