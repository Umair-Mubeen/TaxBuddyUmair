from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView

from .sitemaps import BlogSitemap, StaticSitemap, CalculatorSitemap
from . import views

sitemaps = {
    'static': StaticSitemap,
    'calculators': CalculatorSitemap,
    'blog': BlogSitemap,
}

urlpatterns = [

    # ── PUBLIC PAGES ──────────────────────────────────────────
    path('', views.index, name='index'),
    path('login/', views.Login, name='Login'),
    path('logout/', views.Logout, name='Logout'),
    path('search/', views.search, name='search'),

    # ── SRO TRACKER ───────────────────────────────────────────
    path('sros/', views.sro_list, name='sro_list'),
    path('sros/<slug:slug>/', views.sro_detail, name='sro_detail'),
    path('subscribe/', views.subscribe, name='subscribe'),

    # ── GLOSSARY ──────────────────────────────────────────────
    path('glossary/', views.glossary_list, name='glossary_list'),
    path('glossary/<slug:slug>/', views.glossary_detail, name='glossary_detail'),

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
    path('Withholding-Tax-Card/', views.Withholding_Tax_Card, name='Withholding_Tax_Card'),
    path('freelancer-tax-calculator/', views.freelancer_calculator, name='freelancer_calculator'),
    path('advance-tax-calculator/', views.advance_tax_calculator, name='advance_tax_calculator'),
    path('capital-gains-tax-calculator/', views.capital_gains_tax_calculator, name='capital_gains_tax_calculator'),

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

    # SRO Management
    path('manage-sros/',            views.manage_sros, name='manage_sros'),
    path('add-sro/',                views.add_edit_sro, name='add_sro'),
    path('edit-sro/<int:pk>/',      views.add_edit_sro, name='edit_sro'),
    path('delete-sro/<int:pk>/',    views.delete_sro,  name='delete_sro'),

    # Glossary Management
    path('manage-glossary/',           views.manage_glossary,  name='manage_glossary'),
    path('add-glossary/',              views.add_edit_glossary, name='add_glossary'),
    path('edit-glossary/<int:pk>/',    views.add_edit_glossary, name='edit_glossary'),
    path('delete-glossary/<int:pk>/',  views.delete_glossary,  name='delete_glossary'),

    # ── AI CHAT ──────────────────────────────────────────────
    path('ai-chat/', views.ai_chat, name='ai_chat'),
    path('api/atl-search/', views.atl_search_api, name='atl_search_api'),

    # ── BLOG (MUST BE LAST — slug patterns are greedy) ────────
    path('blog/', views.viewBlogs, name='viewBlogs'),
    path('blog/<slug:slug>/', views.viewBlogs, name='viewBlogs_category'),
    path('api/wht-rates/',       views.wht_rates_api,        name='wht_rates_api'),

    # ── KARACHI FMV CALCULATOR ────────────────────────────────
    path('karachi-fmv-calculator/', views.karachi_fmv_calculator, name='karachi_fmv_calculator'),
    path('api/fmv-areas/', views.fmv_areas_api, name='fmv_areas_api'),
    path('api/fmv-calculate/', views.fmv_calculate_api, name='fmv_calculate_api'),

    # Blog detail — clean /articles/ prefix avoids slug collisions
    path('articles/<slug:slug>/', views.BlogDetails, name='BlogDetails'),
    path('salary-tax-calculator-2026-27/', views.SalaryCalculator2027, name='SalaryCalculator2027'),
    path('refund-analyzer/', views.refund_analyzer, name='refund_analyzer'),
    path('refund-analyzer/extract/', views.refund_analyzer_extract, name='refund_analyzer_extract'),
    path('salary-tax-slabs-history/', views.salary_rate_history,name='salary_rate_history'),
    # Legacy 301 redirect: old /<slug>/ → /articles/<slug>/
    # Keeps old Google-indexed URLs working
    path('<slug:slug>/', views.legacy_blog_redirect, name='legacy_blog_redirect'),
# ════════════════════════════════════════════════════════════════
#  ADD these to TaxBuddyApp/urls.py  urlpatterns  (before the greedy
#  blog/<slug> and <slug> catch-all patterns at the very bottom).
# ════════════════════════════════════════════════════════════════



# ════════════════════════════════════════════════════════════════
#  ALSO add the page URL name to CalculatorSitemap in
#  TaxBuddyApp/sitemaps.py so it appears in sitemap.xml. Example:
#
#    class CalculatorSitemap(Sitemap):
#        def items(self):
#            return [
#                ...existing names...,
#                'karachi_fmv_calculator',
#            ]
#        def location(self, name):
#            return reverse(name)
# ════════════════════════════════════════════════════════════════
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)