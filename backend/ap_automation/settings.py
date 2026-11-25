"""
Django settings for the TempleGate AP Automation backend.

Configuration is driven by environment variables loaded from backend/.env
(see .env.example). PostgreSQL is the primary (and required production)
database engine.
"""
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

import os  # noqa: E402  (after load_dotenv so .env values are visible)

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-me')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('1', 'true', 'yes')
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    # Project apps (core LAST so its ready() can register audit signals for all models)
    'accounts.apps.AccountsConfig',
    'vendors.apps.VendorsConfig',
    'purchase_orders.apps.PurchaseOrdersConfig',
    'invoices.apps.InvoicesConfig',
    'workflow.apps.WorkflowConfig',
    'payments.apps.PaymentsConfig',
    'accounting.apps.AccountingConfig',
    'analytics.apps.AnalyticsConfig',
    'seeds.apps.SeedsConfig',
    'core.apps.CoreConfig',
]

MIDDLEWARE = [
    'core.middleware.RequestProviderMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ap_automation.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ap_automation.wsgi.application'

# ---------------------------------------------------------------------------
# Database - PostgreSQL (required for this project)
# ---------------------------------------------------------------------------
DB_URL = os.getenv('DB_URL')
if DB_URL:
    DATABASES = {'default': dj_database_url.parse(DB_URL, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'templegate_ap'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': 600,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'accounts.User'

# ---------------------------------------------------------------------------
# DRF / JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
        'core.renderers.CSVRenderer',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.DefaultPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        'CORS_ALLOWED_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173',
    ).split(',') if o.strip()
]
CORS_ALLOW_CREDENTIALS = True
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATA_UPLOAD_MAX_NUMBER_FILES = 100
FILE_UPLOAD_MAX_MEMORY_SIZE = 26214400  # 25 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50 MB (bulk uploads)

# ---------------------------------------------------------------------------
# Email (console backend by default; configure SMTP in production)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'ap-automation@templegate.example.com')

# ---------------------------------------------------------------------------
# OCR / integrations
# ---------------------------------------------------------------------------
TESSERACT_CMD = os.getenv('TESSERACT_CMD', '')

# ---------------------------------------------------------------------------
# Business configuration
# ---------------------------------------------------------------------------
COMPANY_NAME = os.getenv('COMPANY_NAME', 'Templegate Technologies & Services Pvt. Ltd.')
COMPANY_ADDRESS = os.getenv('COMPANY_ADDRESS', 'Unit 7, Tech Park One, Baner Road, Pune, Maharashtra 411045')
COMPANY_GSTIN = os.getenv('COMPANY_GSTIN', '27AABCT1234A1Z0')
COMPANY_STATE_CODE = os.getenv('COMPANY_STATE_CODE', '27')

TOLERANCE_AMOUNT_PCT = float(os.getenv('TOLERANCE_AMOUNT_PCT', '0.5'))
TOLERANCE_QUANTITY_PCT = float(os.getenv('TOLERANCE_QUANTITY_PCT', '0'))
VALID_GST_RATES = {0, 0.25, 3, 5, 12, 18, 28}

ESCALATION_DEFAULT_HOURS = int(os.getenv('ESCALATION_DEFAULT_HOURS', '48'))
REMINDER_INTERVAL_HOURS = int(os.getenv('REMINDER_INTERVAL_HOURS', '24'))

MAX_INVOICE_FILE_MB = 25
ALLOWED_INVOICE_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff'}

# ---------------------------------------------------------------------------
# ERP / accounting integration (see accounting/services.py)
# ---------------------------------------------------------------------------
# Which ERP connector to use: 'simulated' (default) or 'tally_xml' (Tally
# compatible XML vouchers, posting still simulated locally).
ERP_CONNECTOR = os.getenv('ERP_CONNECTOR', 'simulated')

# ---------------------------------------------------------------------------
# Banking integration (see payments/services.py)
# ---------------------------------------------------------------------------
# 'simulated' executes transfers in-process; 'file' generates NEFT/RTGS bulk
# payment instruction CSVs for upload to your bank's corporate portal.
BANK_GATEWAY = os.getenv('BANK_GATEWAY', 'simulated')

# ---------------------------------------------------------------------------
# Extraction: rule-based engine + optional AI assist
# ---------------------------------------------------------------------------
# 'none' (default) uses only the rule-based field identification engine.
# 'llm' enables an optional AI assist used only when the rule engine's
# confidence is low or mandatory fields are missing. Requires AI_API_KEY.
AI_EXTRACTION_PROVIDER = os.getenv('AI_EXTRACTION_PROVIDER', 'none')
AI_API_KEY = os.getenv('AI_API_KEY', '')
AI_MODEL = os.getenv('AI_MODEL', 'glm-4-flash')
AI_ASSIST_CONFIDENCE_THRESHOLD = float(os.getenv('AI_ASSIST_CONFIDENCE_THRESHOLD', '0.75'))
AI_ASSIST_TIMEOUT_SECONDS = int(os.getenv('AI_ASSIST_TIMEOUT_SECONDS', '20'))

# ---------------------------------------------------------------------------
# In-process background scheduler (core/scheduler.py, APScheduler)
# ---------------------------------------------------------------------------
SCHEDULER_ENABLED = os.getenv('SCHEDULER_ENABLED', 'False').lower() in ('1', 'true', 'yes')
SCHEDULER_WORKFLOW_SECONDS = int(os.getenv('SCHEDULER_WORKFLOW_SECONDS', '300'))
SCHEDULER_OCR_SECONDS = int(os.getenv('SCHEDULER_OCR_SECONDS', '60'))
SCHEDULER_EMAIL_SECONDS = int(os.getenv('SCHEDULER_EMAIL_SECONDS', '300'))

# IMAP inbox polling for automatic email ingestion (optional)
EMAIL_INGEST_HOST = os.getenv('EMAIL_INGEST_HOST', '')
EMAIL_INGEST_PORT = int(os.getenv('EMAIL_INGEST_PORT', '993'))
EMAIL_INGEST_USER = os.getenv('EMAIL_INGEST_USER', '')
EMAIL_INGEST_PASSWORD = os.getenv('EMAIL_INGEST_PASSWORD', '')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'standard': {'format': '[{asctime}] {levelname} {name}: {message}', 'style': '{'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django.db.backends': {'level': 'WARNING'},
        'invoices': {'level': 'INFO'},
        'payments': {'level': 'INFO'},
        'workflow': {'level': 'INFO'},
    },
}
