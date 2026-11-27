# base.py
import os

from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "claude-haiku-5-5")


BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = 'your-secret-key'
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'TaxBuddyApp',
    'django.contrib.humanize',
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

ROOT_URLCONF = 'TaxBuddy.urls'

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

WSGI_APPLICATION = 'TaxBuddy.wsgi.application'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')




DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'taxbuddyumair',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}


# Paste into TaxBuddy/settings/base.py, right after the AI_MODEL line.
# (If production.py defines its own CACHES, add the "ai" entry there too.)

# ── TaxBuddy Umair AI limits + cost monitor (Phase 0, see TaxBuddyApp/ai_guard.py) ──
AI_SESSION_HOURLY_LIMIT = int(os.getenv("AI_SESSION_HOURLY_LIMIT", "25"))
AI_IP_HOURLY_LIMIT = int(os.getenv("AI_IP_HOURLY_LIMIT", "40"))
AI_DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "400"))
AI_DAILY_TOKEN_LIMIT = int(os.getenv("AI_DAILY_TOKEN_LIMIT", "4000000"))
AI_DAILY_BUDGET_USD = float(os.getenv("AI_DAILY_BUDGET_USD", "0"))
AI_PRICE_INPUT_PER_MTOK = float(os.getenv("AI_PRICE_INPUT_PER_MTOK", "0"))
AI_PRICE_OUTPUT_PER_MTOK = float(os.getenv("AI_PRICE_OUTPUT_PER_MTOK", "0"))

# "ai" cache is shared by all Gunicorn workers (MySQL table) so limits hold.
# One-time: python manage.py createcachetable
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "ai": {"BACKEND": "django.core.cache.backends.db.DatabaseCache",
           "LOCATION": "taxbuddy_ai_cache"},
}