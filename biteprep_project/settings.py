# biteprep_project/settings.py

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv
import logging

# Set up basic logging configuration early to catch startup issues
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('SECRET_KEY')

# CRITICAL: Ensure SECRET_KEY is set in production
if not SECRET_KEY:
    if os.getenv('DEBUG', 'False') == 'True':
        logger.warning("WARNING: SECRET_KEY not set. Using an insecure default for development.")
        SECRET_KEY = 'django-insecure-development-key'
    else:
        # Raise error if the key is missing in production
        raise ValueError("FATAL: The SECRET_KEY environment variable must be set in production.")

DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

# SECURITY: Load the secret admin path from env vars. Provide a default if missing.
SECRET_ADMIN_PATH = os.getenv('SECRET_ADMIN_PATH', 'manage-biteprep-secure-access/')
# Ensure the path ends with a slash
if not SECRET_ADMIN_PATH.endswith('/'):
    SECRET_ADMIN_PATH += '/'

INSTALLED_APPS = [
    'quiz.apps.QuizConfig',
    'users.apps.UsersConfig',
    'crispy_forms',
    'crispy_bootstrap5',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'storages', # Added for cloud media storage
    'django_otp',
    'django_otp.plugins.otp_totp',
    'admin_honeypot',
    'simple_history',
    'impersonate',
    'rangefilter',
    'import_export', # NEW: Added for data management
]

# MIDDLEWARE
# (Middleware remains the same)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # OTPMiddleware must come after AuthenticationMiddleware
    'django_otp.middleware.OTPMiddleware',
    'impersonate.middleware.ImpersonateMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'users.middleware.EnsureProfileMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'biteprep_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'biteprep_project.wsgi.application'

# Database configuration
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600
    )
}

# Password validators
# (Validators remain the same)
# ...

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --- Email Configuration (Handles Deferral Securely) ---
# (Email configuration remains the same)
# ...

# --- Static and Media Files Configuration ---
# (Static/Media configuration remains the same)
# ...

# --- Cloud Storage Configuration (Handles Deferral Securely) ---
# (Cloud Storage configuration remains the same)
# ...


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# NEW: Optional configuration for django-import-export
IMPORT_EXPORT_USE_TRANSACTIONS = True

# Security settings for production
if not DEBUG:
    # ... (Security settings remain the same)


# --- Impersonation Security Settings ---
# (Impersonation settings remain the same)
# ...

# --- Logging Configuration (Production Ready) ---
# (Logging configuration remains the same)
# ...