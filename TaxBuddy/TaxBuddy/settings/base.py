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


# ── TaxBuddy Umair AI limits + cost monitor (Phase 0, see TaxBuddyApp/ai_guard.py) ──
def _env_num(name, default, cast=float):
    """Read a number from .env; a blank or wrong value falls back to the default."""
    try:
        return cast(str(os.getenv(name, default)).strip().replace(",", ""))
    except (TypeError, ValueError):
        return cast(default)

AI_SESSION_HOURLY_LIMIT = _env_num("AI_SESSION_HOURLY_LIMIT", 25, int)
AI_IP_HOURLY_LIMIT = _env_num("AI_IP_HOURLY_LIMIT", 40, int)
AI_DAILY_LIMIT = _env_num("AI_DAILY_LIMIT", 400, int)
AI_DAILY_TOKEN_LIMIT = _env_num("AI_DAILY_TOKEN_LIMIT", 4000000, int)
AI_DAILY_BUDGET_USD = _env_num("AI_DAILY_BUDGET_USD", 0)
AI_PRICE_INPUT_PER_MTOK = _env_num("AI_PRICE_INPUT_PER_MTOK", 0)
AI_PRICE_OUTPUT_PER_MTOK = _env_num("AI_PRICE_OUTPUT_PER_MTOK", 0)