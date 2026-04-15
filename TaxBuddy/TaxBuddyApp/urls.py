from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from . import views



urlpatterns = [

    # ── PUBLIC PAGES ──────────────────────────────────────────
    path('', views.index, name='index'),
    path('login/', views.Login, name='Login'),
    path('logout/', views.Logout, name='Logout'),

    # ── MCQ / QUIZ ────────────────────────────────────────────
    path('income-tax-mcqs-pakistan/', views.question_list, name='question_list'),
    path('income-tax-mcqs-pakistan/<slug:category_slug>', views.question_list, name='question_list_category'),
    path('tax-quiz/', views.tax_knowledge_quiz, name='tax_knowledge_quiz'),

    # ── GUIDES & RATES ────────────────────────────────────────
    path('income-tax-guides/', views.income_tax_guides, name='income_tax_guides'),
    path('sales-tax-guides/', views.sales_tax_guides, name='sales_tax_guides'),
    path('income-tax-rates/', views.income_tax_rates, name='income_tax_rates'),
    path('withholding-tax-rates/', views.withholding_tax_rates, name='withholding_tax_rates'),

    # ── BLOG ──────────────────────────────────────────────────
    #path('blog/', views.viewBlogs, name='viewBlogs'),
    #path('<slug:slug>/', views.BlogDetails, name='BlogDetails'),

path('blog/', views.viewBlogs, name='viewBlogs'),
path('blog/<slug:slug>/', views.viewBlogs, name='viewBlogs'),
    path('comments/', views.userComments, name='userComments'),

    # ── CONTACT ───────────────────────────────────────────────
    path('contact/', views.contact, name='contact'),

    # ── CALCULATORS ───────────────────────────────────────────
    path('SalaryCalculator/', views.SalaryCalculator, name='SalaryCalculator'),
    path('BusinessCalculator/', views.BusinessCalculator, name='BusinessCalculator'),
    path('AOPCalculator/', views.AOPCalculator, name='AOPCalculator'),
    path('PropertyCalculator/', views.PropertyCalculator, name='PropertyCalculator'),
    path('TaxCalculator4C/', views.TaxCalculator4C, name='TaxCalculator4C'),

    # ── API ───────────────────────────────────────────────────
    path('api/section-4c-rate/', views.section_4c_rate_view, name='section_4c_rate'),




    # ── POLICY PAGES ─────────────────────────────────────────
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-and-conditions/', views.terms_and_conditions, name='terms_and_conditions'),

    # ── MISC ──────────────────────────────────────────────────
    path('online-services/', views.online_services, name='online_services'),
    path('layout/', views.layout, name='layout'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('test/', views.test, name='test'),

    # ── ADMIN / CPANEL ────────────────────────────────────────
    path('dashboard/', views.Dashboard, name='Dashboard'),
    path('manage-blogs/', views.ManageBlogs, name='ManageBlogs'),
    path('add-blog/', views.AddEditBlog, name='AddBlog'),
    path('edit-blog/<slug:slug>/', views.AddEditBlog, name='EditBlog'),
    path('delete-blog/<slug:slug>/', views.deleteBlog, name='deleteBlog'),
    path('add-tax-brackets/', views.add_salary_tax_brackets, name='add_salary_tax_brackets'),

    # ── QUESTION MANAGEMENT ───────────────────────────────────
    path('questions/add/', views.add_question, name='questions-add'),
    path('questions/', views.view_questions, name='questions-list'),
    path('questions/edit/<int:pk>/', views.edit_question, name='questions-edit'),
    path('questions/delete/<int:pk>/', views.delete_question, name='questions-delete'),

    # ── CUSTOM ERROR HANDLERS ─────────────────────────────────
    # Register these in your main urls.py (not here):
    # handler404 = 'yourapp.views.custom_404'
    # handler500 = 'yourapp.views.custom_500'
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)