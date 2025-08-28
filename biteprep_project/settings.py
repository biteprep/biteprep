# biteprep_project/settings.py - PRODUCTION SECURE VERSION

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv
import logging
from django.core.exceptions import ImproperlyConfigured

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Security function to get required env variables
def get_env_variable(var_name, default=None, required=False):
    """Get environment variable or raise exception if required."""
    value = os.getenv(var_name, default)
    if required and value is None:
        raise ImproperlyConfigured(f"The {var_name} environment variable is required.")
    return value

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_env_variable('SECRET_KEY', required=True)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = get_env_variable('DEBUG', 'False') == 'True'

# Production check
IS_PRODUCTION = not DEBUG

# Allowed hosts - properly configured
ALLOWED_HOSTS = []
allowed_hosts_str = get_env_variable('ALLOWED_HOSTS', '')
if allowed_hosts_str:
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_str.split(',')]

RENDER_HOSTNAME = get_env_variable('RENDER_EXTERNAL_HOSTNAME')
if RENDER_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_HOSTNAME)

# Add localhost only in development
if DEBUG:
    ALLOWED_HOSTS.extend(['127.0.0.1', 'localhost'])

# CSRF Trusted Origins - Critical for production
CSRF_TRUSTED_ORIGINS = []
csrf_origins = get_env_variable('CSRF_TRUSTED_ORIGINS', '')
if csrf_origins:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins.split(',')]
elif IS_PRODUCTION and RENDER_HOSTNAME:
    CSRF_TRUSTED_ORIGINS = [f'https://{RENDER_HOSTNAME}']

# Admin security
SECRET_ADMIN_PATH = get_env_variable('SECRET_ADMIN_PATH', 'admin/')
if not SECRET_ADMIN_PATH.endswith('/'):
    SECRET_ADMIN_PATH += '/'

# Application definition
INSTALLED_APPS = [
    'quiz.apps.QuizConfig',
    'users.apps.UsersConfig',
    'crispy_forms',
    'crispy_bootstrap5',
    # Security apps
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_ratelimit',  # Add back rate limiting
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    # Additional apps
    'storages',
    'simple_history',
    'impersonate',
    'rangefilter',
    'import_export',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'impersonate.middleware.ImpersonateMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'users.middleware.EnsureProfileMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Security middleware for production
if IS_PRODUCTION:
    MIDDLEWARE.insert(1, 'django.middleware.security.SecurityMiddleware')

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

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Cache configuration
REDIS_URL = get_env_variable('REDIS_URL')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CONNECTION_POOL_KWARGS': {'max_connections': 50},
            },
            'KEY_PREFIX': 'biteprep',
            'TIMEOUT': 300,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

# Password validation - Enhanced for production
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12 if IS_PRODUCTION else 8,  # Stronger in production
        }
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

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Storage configuration
USE_S3 = get_env_variable('USE_S3', 'False') == 'True'

if USE_S3:
    AWS_ACCESS_KEY_ID = get_env_variable('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = get_env_variable('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = get_env_variable('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = get_env_variable('AWS_S3_REGION_NAME', 'us-east-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    AWS_DEFAULT_ACL = None  # Use S3 bucket's policy
    AWS_S3_VERIFY = True
    
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Stripe configuration
STRIPE_PUBLISHABLE_KEY = get_env_variable('STRIPE_PUBLISHABLE_KEY')
STRIPE_SECRET_KEY = get_env_variable('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = get_env_variable('STRIPE_WEBHOOK_SECRET')

# Authentication
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'
AUTH_USER_MODEL = 'auth.User'

# Session configuration - SECURE
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_NAME = 'biteprep_sessionid'
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'  # Better compatibility than 'Strict'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# CSRF Protection - ENHANCED
CSRF_COOKIE_NAME = 'biteprep_csrftoken'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = False  # Use cookies for better performance
CSRF_FAILURE_VIEW = 'quiz.views.csrf_failure'

# Security Settings - PRODUCTION
if IS_PRODUCTION:
    # HTTPS/SSL
    SECURE_SSL_REDIRECT = get_env_variable('SECURE_SSL_REDIRECT', 'True') == 'True'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # Security headers
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    # HSTS
    SECURE_HSTS_SECONDS = int(get_env_variable('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Additional security
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", 'cdn.jsdelivr.net', 'cdnjs.cloudflare.com')
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", 'cdn.jsdelivr.net', 'fonts.googleapis.com')
CSP_FONT_SRC = ("'self'", 'fonts.gstatic.com')
CSP_IMG_SRC = ("'self'", 'data:', 'https:')

# File upload security
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100  # Prevent parameter pollution
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
MAX_IMAGE_UPLOAD_SIZE = 2097152  # 2MB

# Email configuration
EMAIL_BACKEND = get_env_variable('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = get_env_variable('EMAIL_HOST', '')
EMAIL_PORT = int(get_env_variable('EMAIL_PORT', '587'))
EMAIL_USE_TLS = get_env_variable('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = get_env_variable('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = get_env_variable('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = get_env_variable('DEFAULT_FROM_EMAIL', 'noreply@biteprep.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Crispy forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Import-export
IMPORT_EXPORT_USE_TRANSACTIONS = True
IMPORT_EXPORT_SKIP_ADMIN_LOG = False

# Impersonation security
IMPERSONATE = {
    'REDIRECT_URL': '/dashboard/',
    'USE_HTTP_REFERER': False,
    'REQUIRE_SUPERUSER': True,
}

# Logging configuration - PRODUCTION READY
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'root': {
        'handlers': ['console', 'file'] if IS_PRODUCTION else ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'] if IS_PRODUCTION else ['console'],
            'level': get_env_variable('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file', 'mail_admins'] if IS_PRODUCTION else ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'quiz': {
            'handlers': ['console', 'file'] if IS_PRODUCTION else ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'users': {
            'handlers': ['console', 'file'] if IS_PRODUCTION else ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'security': {
            'handlers': ['security_file'] if IS_PRODUCTION else ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
if IS_PRODUCTION:
    logs_dir = BASE_DIR / 'logs'
    logs_dir.mkdir(exist_ok=True)

# Error tracking with Sentry
SENTRY_DSN = get_env_variable('SENTRY_DSN')
if SENTRY_DSN and IS_PRODUCTION:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(
                transaction_style='function_name',
                middleware_spans=False,
            ),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment=get_env_variable('ENVIRONMENT', 'production'),
        release=get_env_variable('RELEASE_VERSION', 'unknown'),
    )

# Admin customization
ADMIN_SITE_HEADER = "BitePrep Control Center"
ADMIN_SITE_TITLE = "BitePrep Admin"
ADMIN_INDEX_TITLE = "Management Dashboard"

# Celery Configuration (if using background tasks)
if REDIS_URL:
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = TIME_ZONE
    CELERY_TASK_SOFT_TIME_LIMIT = 60
    CELERY_TASK_TIME_LIMIT = 120

# Registration control
REGISTRATION_OPEN = get_env_variable('REGISTRATION_OPEN', 'True') == 'True'

# Admin alerts
ADMINS = [('Admin', get_env_variable('ADMIN_EMAIL', 'admin@biteprep.com'))]
MANAGERS = ADMINS