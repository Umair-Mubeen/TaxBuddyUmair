from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Blog, GlossaryTerm, Instrument


class BlogSitemap(Sitemap):
    """Published blog articles."""
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        return Blog.objects.filter(
            status='published',
            is_deleted=False
        ).order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        # Prefer reverse() so the sitemap follows urls.py automatically.
        # If Blog has get_absolute_url(), Django uses it and you can delete this.
        # VERIFY the URL name below matches urls.py.
        return reverse('BlogDetails', kwargs={'slug': obj.slug})


class BlogCategorySitemap(Sitemap):
    """Blog category listing pages (income tax / sales tax)."""
    changefreq = 'weekly'
    priority = 0.6
    protocol = 'https'

    def items(self):
        # Keep in sync with the categories linked in navbar.html
        return ['income-tax', 'sales-tax']

    def location(self, slug):
        return reverse('viewBlogs_category', kwargs={'slug': slug})


class GlossarySitemap(Sitemap):
    """Individual glossary term pages — one indexable page per term."""
    changefreq = 'monthly'
    priority = 0.6
    protocol = 'https'

    def items(self):
        return GlossaryTerm.objects.filter(is_active=True).order_by('term')

    def location(self, obj):
        return reverse('glossary_detail', kwargs={'slug': obj.slug})


class SROSitemap(Sitemap):
    """SRO / circular / notification detail pages."""
    changefreq = 'monthly'
    priority = 0.7
    protocol = 'https'

    def items(self):
        return Instrument.objects.all().order_by('-issue_date')

    def lastmod(self, obj):
        # Instrument has no updated_at field; issue_date is the closest signal.
        return obj.issue_date

    def location(self, obj):
        return reverse('sro_detail', kwargs={'slug': obj.slug})


class HomeSitemap(Sitemap):
    """Homepage on its own so it can carry priority 1.0."""
    changefreq = 'weekly'
    priority = 1.0
    protocol = 'https'

    def items(self):
        return ['index']

    def location(self, item):
        return reverse(item)


class StaticSitemap(Sitemap):
    """Core content and tool landing pages."""
    changefreq = 'monthly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        return [
            'about_us',
            'contact',
            'atl_check',
            'tax_calendar',
            'fbr_iris_guide',
            'income_tax_guides',
            'sales_tax_guides',
            'income_tax_rates',
            'withholding_tax_rates',
            'question_list',
            'online_services',
            'viewBlogs',
            'sro_list',
            'glossary_list',
        ]

    def location(self, item):
        return reverse(item)


class LegalSitemap(Sitemap):
    """Policy pages — indexable but low priority."""
    changefreq = 'yearly'
    priority = 0.3
    protocol = 'https'

    def items(self):
        return [
            'privacy_policy',
            'terms_and_conditions',
        ]

    def location(self, item):
        return reverse(item)


class CalculatorSitemap(Sitemap):
    """Interactive tools — highest-value pages after the homepage."""
    changefreq = 'monthly'
    priority = 0.9
    protocol = 'https'

    def items(self):
        return [
            'SalaryCalculator',
            'SalaryCalculator2027',
            'BusinessCalculator',
            'AOPCalculator',
            'PropertyCalculator',
            'TaxCalculator4C',
            'Withholding_Tax_Card',
            'refund_analyzer',
            'freelancer_calculator',
            'freelancer_calculator',
            'advance_tax_calculator',
        ]

    def location(self, item):
        return reverse(item)


# ---------------------------------------------------------------------------
# Register in urls.py:
#
# from .sitemaps import (
#     HomeSitemap, StaticSitemap, LegalSitemap, CalculatorSitemap,
#     BlogSitemap, BlogCategorySitemap, GlossarySitemap, SROSitemap,
# )
#
# sitemaps = {
#     'home':        HomeSitemap,
#     'calculators': CalculatorSitemap,
#     'static':      StaticSitemap,
#     'blog':        BlogSitemap,
#     'categories':  BlogCategorySitemap,
#     'sros':        SROSitemap,
#     'glossary':    GlossarySitemap,
#     'legal':       LegalSitemap,
# }
# ---------------------------------------------------------------------------