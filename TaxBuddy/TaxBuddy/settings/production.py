from .base import *

DEBUG = False

ALLOWED_HOSTS = ['taxbuddyumair.com', 'www.taxbuddyumair.com', '.taxbuddyumair.com', '31.97.49.72']

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'


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

