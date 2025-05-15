from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path('', views.index, name='index'),  # Home Page
    path('contact-us', views.Contact, name='contact-us'),  # Contact Page
    path('TaxCalculator', views.TaxCalculator, name='TaxCalculator'),  # Tax Calculator Page
    path('BlogDetails', views.BlogDetails, name='BlogDetails'),  # BlogDetails Page

    #Dashboard URL
    path('Login', views.Login, name='Login'),  # Login Page
    path('Logout', views.Logout, name='Logout'),  # Login Page
    path('Dashboard', views.Dashboard, name='Dashboard'),  # Dashboard Page
    path('AddEditBlog', views.AddEditBlog, name='AddEditBlog'), # AddEditBlog Page
    path('ManageBlogs', views.ManageBlogs, name='ManageBlogs'),  # ManageBlogs Page


]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)