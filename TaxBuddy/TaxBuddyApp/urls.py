from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path("sitemap.xml", TemplateView.as_view(template_name="sitemap.xml", content_type="application/xml")),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),

    path('', views.index, name='index'),  # Home Page
    # path('contact-us', views.Contact, name='contact-us'),  # Contact Page
    path('userComments', views.userComments, name='userComments'),  # Comments Page
path("terms-and-conditions/", views.terms_and_conditions, name="terms-and-conditions"),
    #Dashboard URL
    path('Login', views.Login, name='Login'),  # Login Page
    path('Logout', views.Logout, name='Logout'),  # Login Page
    path('Dashboard', views.Dashboard, name='Dashboard'),  # Dashboard Page
# Add new question (card form)
    path("questions-add/", views.add_question, name="questions-add"),
    path("view-questions/", views.view_questions, name="view-questions"),
 path("questions/edit/<int:pk>/", views.edit_question, name="questions-edit"),
    path("questions/delete/<int:pk>/", views.delete_question, name="questions-delete"),

    path("section-4c-rate/", views.section_4c_rate_view, name="section_4c_rate"),

    path("income-tax-mcqs-pakistan", views.question_list, name="income-tax-mcqs-pakistan"),
path("online-services", views.online_services, name="online-services"),
    path('AddEditBlog/', views.AddEditBlog, name='AddBlog'),  # create
    path('AddEditBlog/<slug:slug>/', views.AddEditBlog, name='EditBlog'),
    path('blog/<slug:slug>/', views.viewBlogs, name='viewBlogs'),  # BlogDetails Page
    path('<slug:slug>/', views.BlogDetails, name='BlogDetails'),  # BlogDetails Page
    path('deleteBlog/<slug:slug>/', views.deleteBlog, name='deleteBlog'),  # For create without slug

    path('ManageBlogs', views.ManageBlogs, name='ManageBlogs'),  # ManageBlogsPage

    path('contact', views.contact, name='contact'),
    path("SalaryCalculator", views.SalaryCalculator, name='SalaryCalculator'),
    path("BusinessCalculator", views.BusinessCalculator, name='BusinessCalculator'),
    path("AOPCalculator", views.AOPCalculator, name='AOPCalculator'),
    path("PropertyCalculator", views.PropertyCalculator, name='PropertyCalculator'),

    #tax slab brackets
    path("add_salary_tax_brackets", views.add_salary_tax_brackets,name="add_salary_tax_brackets"),
    path("privacy-policy", views.privacy_policy, name="privacy_policy"),
    path("TaxCalculator4C", views.TaxCalculator4C, name="TaxCalculator4C"),
    path("income-tax-guides", views.income_tax_guides, name="income-tax-guides"),
path("sales-tax-guides", views.sales_tax_guides, name="sales-tax-guides"),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)