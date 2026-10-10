"""
Django settings for AI Client Query Triage and Draft Reply Assistant.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if present
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-client-query-triage-demo-key-9988776655'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 't')

allowed_hosts_str = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_str.split(',') if h.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Project Apps
    'core',
    'ingestion',
    'triage',
    'routing',
    'worker',
    'dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'dashboard.context_processors.app_status',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,  # Prevent SQLite locks under worker concurrency
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
LOGIN_URL = '/login/'

# ==========================================
# Application Specific Configuration
# ==========================================

# AI Configuration
AI_MODE = os.environ.get('AI_MODE', 'mock')  # 'mock' or 'claude'
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ANTHROPIC_MODEL = os.environ.get('ANTHROPIC_MODEL', 'claude-3-7-sonnet-20250219')

# Email Provider Configuration
EMAIL_MODE = os.environ.get('EMAIL_MODE', 'demo')  # 'demo' or 'gmail'
GMAIL_CREDENTIALS_FILE = os.environ.get('GMAIL_CREDENTIALS_FILE', str(BASE_DIR / 'credentials.json'))
GMAIL_TOKEN_FILE = os.environ.get('GMAIL_TOKEN_FILE', str(BASE_DIR / 'token.json'))

# Notification Configuration
NOTIFICATION_MODE = os.environ.get('NOTIFICATION_MODE', 'log')  # 'log', 'slack', 'teams'
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
TEAMS_WEBHOOK_URL = os.environ.get('TEAMS_WEBHOOK_URL', '')

# Background Worker Settings
WORKER_POLL_INTERVAL = float(os.environ.get('WORKER_POLL_INTERVAL', '2.0'))
WORKER_MAX_RETRIES = int(os.environ.get('WORKER_MAX_RETRIES', '3'))
WORKER_LEASE_SECONDS = int(os.environ.get('WORKER_LEASE_SECONDS', '300'))

# Default SLA Targets (in minutes)
SLA_TARGETS_MINUTES = {
    'critical': int(os.environ.get('SLA_CRITICAL_MINUTES', '30')),
    'high': int(os.environ.get('SLA_HIGH_MINUTES', '120')),
    'normal': int(os.environ.get('SLA_NORMAL_MINUTES', '480')),
    'low': int(os.environ.get('SLA_LOW_MINUTES', '1440')),
}
