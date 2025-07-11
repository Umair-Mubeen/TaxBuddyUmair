from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path('', views.index, name='index'),  # Home Page
    # path('contact-us', views.Contact, name='contact-us'),  # Contact Page

    path('BlogDetails/<slug:slug>/', views.BlogDetails, name='BlogDetails'),  # BlogDetails Page
    path('userComments', views.userComments, name='userComments'),  # Comments Page

    #Dashboard URL
    path('Login', views.Login, name='Login'),  # Login Page
    path('Logout', views.Logout, name='Logout'),  # Login Page
    path('Dashboard', views.Dashboard, name='Dashboard'),  # Dashboard Page
    path('AddEditBlog/<slug:slug>/', views.AddEditBlog, name='AddEditBlog'),
    path('AddEditBlog/', views.AddEditBlog, name='AddEditBlog'),  # For create without slug
    path('deleteBlog/<slug:slug>/', views.deleteBlog, name='deleteBlog'),  # For create without slug

    path('ManageBlogs', views.ManageBlogs, name='ManageBlogs'),  # ManageBlogsPage

    path("contact", views.contact, name='contact'),
    path("Calculator", views.SalarySlab, name='Calculator'),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)