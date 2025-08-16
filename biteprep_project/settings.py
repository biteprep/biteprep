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
# Update ALLOWED_HOSTS to include the Render domain if deploying there
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
RENDER_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME')
if RENDER_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_HOSTNAME)


# SECURITY: Load the secret admin path from env vars. Provide a default if missing.
SECRET_ADMIN_PATH = os.getenv('SECRET_ADMIN_PATH', 'manage-biteprep-secure-access/')
# Ensure the path ends with a slash
if not SECRET_ADMIN_PATH.endswith('/'):
    SECRET_ADMIN_PATH += '/'

# FIX: Reordered INSTALLED_APPS to ensure admin_honeypot loads before django.contrib.admin
INSTALLED_APPS = [
    'quiz.apps.QuizConfig',
    'users.apps.UsersConfig',
    'crispy_forms',
    'crispy_bootstrap5',
    
    # Must come BEFORE django.contrib.admin
    'admin_honeypot',
    
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
    'simple_history',
    'impersonate',
    'rangefilter',
    'import_export', # NEW: Added for data management
]

# MIDDLEWARE
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
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --- Email Configuration (Handles Deferral Securely) ---
# Basic configuration - adjust based on your actual email service provider
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST')
# Use a try-except block for EMAIL_PORT in case the env var is missing or invalid
try:
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
except ValueError:
    EMAIL_PORT = 587
    
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'webmaster@localhost')


# --- Static and Media Files Configuration ---
STATIC_URL = 'static/'
# The location where collectstatic will put files (required for deployment)
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# --- Cloud Storage Configuration (Handles Deferral Securely) ---
# Determine if we should use cloud storage (e.g., AWS S3)
USE_S3 = os.getenv('USE_S3', 'False') == 'True'

if USE_S3:
    # AWS S3 Configuration (Requires setting corresponding environment variables)
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

    # S3 Static files configuration
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3StaticStorage'
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'

    # S3 Media files configuration
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
    
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
             "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
        },
    }

else:
    # Local storage configuration with Whitenoise for static files
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            # Use Whitenoise for efficient static file serving in production (Crucial for Render)
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }


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
    # Ensure cookies are only sent over HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS (HTTP Strict Transport Security) - tells browsers to only use HTTPS
    # Start short (e.g., 1 hour) and increase once confirmed working.
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Prevent the browser from guessing the content type
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Optional: Redirect HTTP to HTTPS. Often handled by the hosting platform (like Render).
    # SECURE_SSL_REDIRECT = True


# --- Impersonation Security Settings ---
IMPERSONATE = {
    'REDIRECT_URL': '/dashboard/',
}


# --- Logging Configuration (Production Ready) ---
# Basic logging is set at the top. Advanced configuration for production:
if not DEBUG:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
        },
        'root': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'loggers': {
            'django': {
                'handlers': ['console'],
                'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
                'propagate': False,
            },
            # Added logger for the application itself
            'quiz': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'users': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
        },
    }