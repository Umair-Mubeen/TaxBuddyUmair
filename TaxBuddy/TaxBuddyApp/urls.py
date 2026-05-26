from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap

from .sitemaps import BlogSitemap, StaticSitemap, CalculatorSitemap, TaxGuideSitemap
from . import views

sitemaps = {
    'static':      StaticSitemap(),
    'calculators': CalculatorSitemap(),
    'blog':        BlogSitemap(),
    'guides':      TaxGuideSitemap(),
}

urlpatterns = [

    # ── PUBLIC PAGES ──────────────────────────────────────────
    path('', views.index, name='index'),
    path('login/', views.Login, name='Login'),
    path('logout/', views.Logout, name='Logout'),

    # ── CONTACT ───────────────────────────────────────────────
    path('contact/', views.contact, name='contact'),
    path('comments/', views.userComments, name='userComments'),

    # ── GUIDES & RATES ────────────────────────────────────────
    path('income-tax-guides/', views.income_tax_guides, name='income_tax_guides'),
    path('sales-tax-guides/', views.sales_tax_guides, name='sales_tax_guides'),
    path('income-tax-rates/', views.withholding_tax_rates, name='income_tax_rates'),
    path('withholding-tax-rates/', views.withholding_tax_rates, name='withholding_tax_rates'),

    # ── MCQ / QUIZ ────────────────────────────────────────────
    path('income-tax-mcqs-pakistan/', views.question_list, name='question_list'),
    path('income-tax-mcqs-pakistan/<slug:category_slug>/', views.question_list, name='question_list_category'),
    #path('tax-quiz/', views.tax_knowledge_quiz, name='tax_knowledge_quiz'),

    # ── CALCULATORS ───────────────────────────────────────────
    path('SalaryCalculator/', views.SalaryCalculator, name='SalaryCalculator'),
    path('BusinessCalculator/', views.BusinessCalculator, name='BusinessCalculator'),
    path('AOPCalculator/', views.AOPCalculator, name='AOPCalculator'),
    path('PropertyCalculator/', views.PropertyCalculator, name='PropertyCalculator'),
    path('TaxCalculator4C/', views.TaxCalculator4C, name='TaxCalculator4C'),

    # ── API ───────────────────────────────────────────────────
    path('api/section-4c-rate/', views.section_4c_rate_view, name='section_4c_rate'),

    # ── SEO ───────────────────────────────────────────────────
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', views.robots_txt, name='robots_txt'),

    # ── POLICY PAGES ─────────────────────────────────────────
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-and-conditions/', views.terms_and_conditions, name='terms_and_conditions'),

    # ── MISC ──────────────────────────────────────────────────
    path('online-services/', views.online_services, name='online_services'),
    path('layout/', views.layout, name='layout'),
    path('test/', views.test, name='test'),

    # ── NEW PAGES ─────────────────────────────────────────────
    path('about-us/',       views.about_us,       name='about_us'),
    path('atl-check/',      views.atl_check,      name='atl_check'),
    path('tax-calendar/',   views.tax_calendar,   name='tax_calendar'),
    path('fbr-iris-guide/', views.fbr_iris_guide, name='fbr_iris_guide'),

    # ── 301 REDIRECTS — Fix Soft 404 MCQ category pages ───────
    path('income-tax-mcqs-pakistan/exemptions-and-tax-concessions/', views.redirect_to_mcqs),
    path('income-tax-mcqs-pakistan/deductible-allowances/',          views.redirect_to_mcqs),
    path('income-tax-mcqs-pakistan/types-of-income/',                views.redirect_to_mcqs),
    path('income-tax-mcqs-pakistan/computation-of-taxable-income/', views.redirect_to_mcqs),

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


    # ── WHT / ADVANCE TAX RATE MANAGEMENT ─────────────────────
    path('manage-wht-rates/',         views.manage_wht_rates, name='manage_wht_rates'),
    path('add-wht-rate/',             views.add_wht_rate,     name='add_wht_rate'),
    path('edit-wht-rate/<int:pk>/',   views.edit_wht_rate,    name='edit_wht_rate'),
    path('delete-wht-rate/<int:pk>/', views.delete_wht_rate,  name='delete_wht_rate'),

    # Guide Management
    path('manage-guides/',          views.manage_guides, name='manage_guides'),
    path('add-guide/',              views.add_guide,     name='add_guide'),
    path('edit-guide/<int:pk>/',    views.edit_guide,    name='edit_guide'),
    path('delete-guide/<int:pk>/',  views.delete_guide,  name='delete_guide'),

    # FAQ Management
    path('manage-faqs/',            views.manage_faqs, name='manage_faqs'),
    path('add-faq/',                views.add_faq,     name='add_faq'),
    path('edit-faq/<int:pk>/',      views.edit_faq,    name='edit_faq'),
    path('delete-faq/<int:pk>/',    views.delete_faq,  name='delete_faq'),

    # ── AI CHAT ──────────────────────────────────────────────
    path('ai-chat/', views.ai_chat, name='ai_chat'),
    path('api/atl-search/', views.atl_search_api, name='atl_search_api'),

    # ── BLOG (MUST BE LAST — slug patterns are greedy) ────────
    path('blog/', views.viewBlogs, name='viewBlogs'),
    path('blog/<slug:slug>/', views.viewBlogs, name='viewBlogs_category'),

    # Blog detail — clean /articles/ prefix avoids slug collisions
    path('articles/<slug:slug>/', views.BlogDetails, name='BlogDetails'),

    # Legacy 301 redirect: old /<slug>/ → /articles/<slug>/
    # Keeps old Google-indexed URLs working
    path('<slug:slug>/', views.legacy_blog_redirect, name='legacy_blog_redirect'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)