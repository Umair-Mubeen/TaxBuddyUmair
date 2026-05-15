from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Blog, TaxGuide


class BlogSitemap(Sitemap):
    """Sitemap for all published blog posts."""
    changefreq = 'weekly'
    priority    = 0.8
    protocol    = 'https'

    def items(self):
        return Blog.objects.filter(
            status='published',
            is_deleted=False
        ).order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return f'/articles/{obj.slug}/'


class TaxGuideSitemap(Sitemap):
    """Sitemap for Tax Guides."""
    changefreq = 'monthly'
    priority    = 0.85
    protocol    = 'https'

    def items(self):
        return TaxGuide.objects.filter(is_active=True)

    def location(self, obj):
        return f'/income-tax-guides/' if obj.category == 'income_tax' else f'/sales-tax-guides/'


class StaticSitemap(Sitemap):
    """Sitemap for all static/tool pages."""
    changefreq = 'monthly'
    priority    = 0.9
    protocol    = 'https'

    def items(self):
        return [
            'index',
            'income_tax_guides',
            'sales_tax_guides',
            'income_tax_rates',
            'withholding_tax_rates',
            'SalaryCalculator',
            'BusinessCalculator',
            'AOPCalculator',
            'PropertyCalculator',
            'TaxCalculator4C',
            'question_list',
            'online_services',
            'privacy_policy',
            'terms_and_conditions',
            'viewBlogs',
        ]

    def location(self, item):
        return reverse(item)


class CalculatorSitemap(Sitemap):
    """Calculators get highest priority."""
    changefreq = 'monthly'
    priority    = 1.0
    protocol    = 'https'

    def items(self):
        return [
            'SalaryCalculator',
            'BusinessCalculator',
            'AOPCalculator',
            'PropertyCalculator',
            'TaxCalculator4C',
        ]

    def location(self, item):
        return reverse(item)