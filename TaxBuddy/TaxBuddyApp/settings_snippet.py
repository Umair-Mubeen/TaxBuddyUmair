# ================================================================
# TaxBuddy Umair — settings.py additions
# Copy these sections into your existing settings.py
# ================================================================

# ── INSTALLED APPS ───────────────────────────────────────────────
# Add these to your INSTALLED_APPS list:
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',   # ← ADD THIS for sitemap.xml
    'core',                      # ← your app
]

# ── TEMPLATES ────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],       # ← points to your templates folder
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

# ── STATIC FILES ─────────────────────────────────────────────────
STATIC_URL       = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']       # ← your static folder
STATIC_ROOT      = BASE_DIR / 'staticfiles'    # ← for collectstatic on production

# Use ManifestStaticFilesStorage for cache-busting in production
# (adds hash to filenames so browsers always load latest version)
# STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# ── MEDIA FILES ──────────────────────────────────────────────────
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── SECURITY ─────────────────────────────────────────────────────
# For production — uncomment these:
# SECURE_BROWSER_XSS_FILTER       = True
# SECURE_CONTENT_TYPE_NOSNIFF     = True
# X_FRAME_OPTIONS                 = 'DENY'
# SECURE_HSTS_SECONDS             = 31536000
# SECURE_SSL_REDIRECT             = True
# SESSION_COOKIE_SECURE           = True
# CSRF_COOKIE_SECURE              = True

# ── reCAPTCHA (optional but recommended) ─────────────────────────
# Get your keys from https://www.google.com/recaptcha/admin/
# RECAPTCHA_SITE_KEY   = 'your-site-key-here'
# RECAPTCHA_SECRET_KEY = 'your-secret-key-here'

# ── EMAIL (for comment notifications) ────────────────────────────
# EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST          = 'smtp.gmail.com'
# EMAIL_PORT          = 587
# EMAIL_USE_TLS       = True
# EMAIL_HOST_USER     = 'your@gmail.com'
# EMAIL_HOST_PASSWORD = 'your-app-password'  # Use Gmail App Password
# DEFAULT_FROM_EMAIL  = 'TaxBuddy Umair <your@gmail.com>'
# ADMIN_EMAIL         = 'umair.mubeenir@gmail.com'

# ── CACHES (speeds up sitemap & robots.txt) ──────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'taxbuddy-cache',
    }
}

# ── LOGGING (optional — catches errors in production) ────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
