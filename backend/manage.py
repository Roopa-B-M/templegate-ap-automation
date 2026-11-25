#!/usr/bin/env python
"""Django management entrypoint for the TempleGate AP Automation backend."""
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ap_automation.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Activate your virtual environment and "
            "run `pip install -r requirements.txt` first."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
