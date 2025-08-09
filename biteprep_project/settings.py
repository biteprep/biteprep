# biteprep_project/settings.py

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('SECRET_KEY')
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
]

# MIDDLEWARE updated: Removed ForceProjectTemplateContextMiddleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # OTPMiddleware must come after AuthenticationMiddleware
    'django_otp.middleware.OTPMiddleware',
    # 'users.middleware.ForceProjectTemplateContextMiddleware', # REMOVED
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
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --- Email Configuration (CRITICAL FOR PRODUCTION) ---
# Use SMTP for sending emails (e.g., password resets).
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
# Safely convert port to integer
try:
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
except (ValueError, TypeError):
    EMAIL_PORT = 587

EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@biteprep.com')

if DEBUG and not EMAIL_HOST:
    # In development, if no host is set, print emails to the console.
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# --- Static and Media Files Configuration ---

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default configuration for static files using WhiteNoise
DEFAULT_STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- Cloud Storage Configuration for Media Files (CRITICAL FOR PRODUCTION) ---
# Prevents uploaded images from being deleted on server restarts (ephemeral filesystems).
# Uses AWS S3 compatible storage (e.g., DigitalOcean Spaces, AWS S3).

AWS_ACCESS_KEY_ID = os.getenv('SPACES_KEY')
AWS_SECRET_ACCESS_KEY = os.getenv('SPACES_SECRET')
AWS_STORAGE_BUCKET_NAME = os.getenv('SPACES_BUCKET')
AWS_S3_ENDPOINT_URL = os.getenv('SPACES_ENDPOINT_URL') # e.g., https://fra1.digitaloceanspaces.com
AWS_S3_REGION_NAME = os.getenv('SPACES_REGION')
# Optional: If you use a CDN or custom domain in front of your bucket
AWS_S3_CUSTOM_DOMAIN = os.getenv('SPACES_CUSTOM_DOMAIN')


# Configure the storage backends (Using Django 4.2+ STORAGES dictionary)
STORAGES = {
    "staticfiles": {
        "BACKEND": DEFAULT_STATICFILES_STORAGE,
    },
}

if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    }
    
    # If using a custom domain/CDN, the MEDIA_URL is derived from it.
    if AWS_S3_CUSTOM_DOMAIN:
         MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
    # Otherwise, it's derived from the endpoint URL
    elif AWS_S3_ENDPOINT_URL:
        # Note: S3Boto3Storage handles the final URL construction correctly internally.
        MEDIA_URL = f'{AWS_S3_ENDPOINT_URL}/'
   
    AWS_S3_FILE_OVERWRITE = False # Prevent overwriting files with the same name
    AWS_DEFAULT_ACL = 'public-read' # Ensure uploaded files are readable if using ACLs
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
else:
    # Fallback to local storage for development
    if not DEBUG:
        print("WARNING: Production environment detected but cloud storage credentials (SPACES_KEY/SECRET/BUCKET) missing. Media uploads will fail or be lost.")
    
    STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Security settings for production
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')

    # --- Advanced Security Headers ---
    # HTTP Strict Transport Security (HSTS) - CRITICAL for HTTPS-only sites
    # Start with a short time (1 hour = 3600s) to test deployment, then increase significantly (e.g., 1 year = 31536000).
    SECURE_HSTS_SECONDS = 3600 
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True # Prevents MIME-type sniffing vulnerabilities.


# --- Impersonation Security Settings ---
# Define global rules to strictly control who can impersonate whom.

def IMPERSONATE_CUSTOM_ALLOW(request):
    # Rule 1: Only allow users who are staff or superusers to initiate impersonation.
    if not request.user.is_authenticated:
        return False
    return request.user.is_staff or request.user.is_superuser

def IMPERSONATE_CUSTOM_TARGET(user):
    # Rule 2: Do not allow impersonating other staff or superuser accounts.
    return not user.is_staff and not user.is_superuser

# --- Logging Configuration ---
# Ensures application errors (INFO level and above) are captured in production logs.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose' if DEBUG else 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        # Set root level to INFO in production, DEBUG locally
        'level': 'INFO' if not DEBUG else 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO' if not DEBUG else 'DEBUG',
            'propagate': False,
        },
        # Add specific loggers for your applications (quiz, users)
        # This allows capturing specific app events (like Stripe webhooks)
        'quiz': {
            'handlers': ['console'],
            'level': 'INFO' if not DEBUG else 'DEBUG',
            'propagate': False,
        },
        'users': {
            'handlers': ['console'],
            'level': 'INFO' if not DEBUG else 'DEBUG',
            'propagate': False,
        },
    },
}