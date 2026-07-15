import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-nova-voice-agent-super-secret-key-12345'

DEBUG = True

ALLOWED_HOSTS = ['*']

# Configuración de orígenes de confianza para la protección CSRF en producción (HTTPS)
CSRF_TRUSTED_ORIGINS = [
    'https://*.up.railway.app',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

railway_url = os.environ.get("RAILWAY_STATIC_URL")
if railway_url:
    if not railway_url.startswith("http"):
        CSRF_TRUSTED_ORIGINS.append(f"https://{railway_url}")
    else:
        CSRF_TRUSTED_ORIGINS.append(railway_url)

railway_public = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if railway_public:
    CSRF_TRUSTED_ORIGINS.append(f"https://{railway_public}")


INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'auth.middleware.AdminAuthMiddleware',
]

ROOT_URLCONF = 'django_project.urls'

ASGI_APPLICATION = 'django_project.asgi.application'

TEMPLATES = []

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'web'),
]

# Logging para ver tracebacks completos de errores 500
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
