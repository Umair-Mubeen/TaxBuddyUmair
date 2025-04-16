from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path('', views.index, name='index'),  # Home Page
    path('contact-us', views.Contact, name='contact-us'),  # Contact Page
    path('TaxCalculator', views.TaxCalculator, name='TaxCalculator'),  # Tax Calculator Page

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)