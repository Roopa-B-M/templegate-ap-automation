"""Scheduler guard tests: never starts during migrate/test/shell, once under runserver."""
import sys
from unittest import mock

from django.test import TestCase, override_settings

from core import scheduler


def with_argv(*args):
    return mock.patch.object(sys, 'argv', list(args))


class SchedulerGuardTests(TestCase):
    def _reset(self):
        scheduler._started = False
        scheduler._scheduler = None

    def tearDown(self):
        self._reset()

    def test_disabled_by_default(self):
        self._reset()
        self.assertFalse(scheduler.can_autostart())

    @override_settings(SCHEDULER_ENABLED=True)
    def test_manage_migrate_never_starts(self):
        self._reset()
        with with_argv('manage.py', 'migrate'):
            self.assertFalse(scheduler.can_autostart())

    @override_settings(SCHEDULER_ENABLED=True)
    def test_manage_test_never_starts(self):
        self._reset()
        with with_argv('manage.py', 'test'):
            self.assertFalse(scheduler.can_autostart())

    @override_settings(SCHEDULER_ENABLED=True)
    def test_manage_shell_never_starts(self):
        self._reset()
        with with_argv('manage.py', 'shell'):
            self.assertFalse(scheduler.can_autostart())

    @override_settings(SCHEDULER_ENABLED=True)
    def test_seed_and_sample_commands_never_start(self):
        self._reset()
        for command in ('seed_demo', 'generate_sample_invoices', 'ingest_folder',
                        'makemigrations', 'check', 'collectstatic'):
            with with_argv('manage.py', command):
                self.assertFalse(scheduler.can_autostart(), f'{command} must not start the scheduler')

    @override_settings(SCHEDULER_ENABLED=True)
    def test_runserver_child_process_starts(self):
        self._reset()
        with with_argv('manage.py', 'runserver'), \
                mock.patch.dict('os.environ', {'RUN_MAIN': 'true'}):
            self.assertTrue(scheduler.can_autostart())

    @override_settings(SCHEDULER_ENABLED=True)
    def test_runserver_autoreload_parent_does_not_start(self):
        self._reset()
        with with_argv('manage.py', 'runserver'), \
                mock.patch.dict('os.environ', {}, clear=True):
            # no RUN_MAIN -> autoreloader parent process
            self.assertFalse(scheduler.can_autostart())

    @override_settings(SCHEDULER_ENABLED=True)
    def test_runserver_noreload_starts(self):
        self._reset()
        with with_argv('manage.py', 'runserver', '--noreload'), \
                mock.patch.dict('os.environ', {}, clear=True):
            self.assertTrue(scheduler.can_autostart())

    @override_settings(SCHEDULER_ENABLED=True)
    def test_wsgi_context_starts(self):
        self._reset()
        with with_argv('gunicorn', 'ap_automation.wsgi:application'):
            self.assertTrue(scheduler.can_autostart())

    def test_test_runner_context_never_starts(self):
        self._reset()
        with with_argv('manage.py', 'test', 'tests.test_scheduler_guard'):
            self.assertFalse(scheduler.can_autostart())

    def test_job_wrapper_swallows_exceptions(self):
        """A failing job must not raise out of the scheduler thread."""
        broken = mock.Mock(side_effect=RuntimeError('boom'))
        with mock.patch.dict(scheduler._JOBS, {'workflow_automation': broken}):
            scheduler._job('workflow_automation')()  # must not raise
        broken.assert_called_once()

    def test_start_is_idempotent(self):
        self._reset()
        fake = mock.MagicMock()
        fake.get_jobs.return_value = []
        with mock.patch('apscheduler.schedulers.background.BackgroundScheduler',
                        return_value=fake):
            first = scheduler.start()
            second = scheduler.start()
        fake.start.assert_called_once()
        self.assertIs(first, second)
        self.assertTrue(scheduler._started)
