from .base import *

DEBUG = False
# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'


STATICFILES_DIRS = [
    BASE_DIR / 'TaxBuddyApp' / 'static',
]
# Media files (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

ALLOWED_HOSTS = ['taxbuddyumair.com', 'www.taxbuddyumair.com', '.taxbuddyumair.com', '31.97.49.72']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'taxbuddyumair',
        'USER': 'taxbuddyuser',            # your MySQL user
        'PASSWORD': 'Kotri@786', # your MySQL user's password
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
ROOT_URLCONF = 'TaxBuddy.urls'
WSGI_APPLICATION = 'TaxBuddy.wsgi.application'


# ═══ ADD TO TaxBuddy/settings/production.py (end of file) ═══

# 1) Security headers handled by Django
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "SAMEORIGIN"

# 2) ETag + CSP/Permissions-Policy middleware
#    (inserted right after SecurityMiddleware; MIDDLEWARE comes from base.py)
_i = MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1
for _m in ('TaxBuddyApp.security_headers.SecurityHeadersMiddleware',
           'django.middleware.http.ConditionalGetMiddleware'):
    if _m not in MIDDLEWARE:
        MIDDLEWARE.insert(_i, _m)

# HSTS is added in nginx (see nginx_snippet.conf) — nginx always knows the request is HTTPS.

