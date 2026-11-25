import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ap_automation.settings')
application = get_wsgi_application()

# Start the optional in-process background scheduler in production server
# contexts (gunicorn/waitress/uwsgi). Guards in core.scheduler prevent double
# starts and no-ops under migrate/test/shell.
from core import scheduler  # noqa: E402

scheduler.autostart()
