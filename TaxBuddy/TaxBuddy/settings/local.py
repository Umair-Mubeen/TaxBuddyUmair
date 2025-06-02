from .base import *

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'TaxBuddyApp' / 'static']
