from datetime import timedelta
from decimal import Decimal
import random

from django.contrib.auth.decorators import login_required
from django.conf import settings
import requests
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.utils.text import slugify
from django.contrib import messages
from django.utils.timezone import now
from django.db.models import Q, F
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator

from .models import (
    Blog, Comment, Contact, TaxBracket, Business_AOP_Slab,
    Property_Business_AOP_Slab, Question, Option,
    SuperTax4CRate, Category, Tag, Testimonial, FAQ
)
from .forms import ContactForm, CommentForm


# ─────────────────────────────────────────────────────────────
# UTILITY HELPERS
# ─────────────────────────────────────────────────────────────

def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_income(request_post, field='income_amount'):
    raw = request_post.get(field, '').strip()
    if not raw:
        return None, "Income amount is required."
    try:
        amount = int(raw)
        if amount < 0:
            return None, "Income amount cannot be negative."
        return amount, None
    except ValueError:
        return None, "Please enter a valid numeric income amount."


# ─────────────────────────────────────────────────────────────
# PUBLIC VIEWS
# ─────────────────────────────────────────────────────────────

def index(request):
    try:
        questions_qs  = Question.objects.filter(is_active=True).prefetch_related("options")
        questions_list = list(questions_qs)
        preview_questions = random.sample(questions_list, min(len(questions_list), 3))

        latest_blogs = Blog.objects.filter(
            status='published', is_deleted=False
        ).order_by('-created_at')[:6]

        testimonials = Testimonial.objects.filter(is_active=True)[:3]
        faqs         = FAQ.objects.filter(page='home', is_active=True)[:5]

        contact_form = ContactForm()
        if request.method == 'POST' and 'contact_submit' in request.POST:
            contact_form = ContactForm(request.POST)
            if contact_form.is_valid():
                contact_form.save()
                messages.success(request, "Thank you! We will contact you shortly.")
                return redirect('/#contact')

        context = {
            'latest_blogs':       latest_blogs,
            'preview_questions':  preview_questions,
            'testimonials':       testimonials,
            'faqs':               faqs,
            'contact_form':       contact_form,
            'meta_title':         'TaxBuddy Umair | Income & Sales Tax Consultant Pakistan',
            'meta_description':   'Expert income tax and sales tax guides, calculators and MCQs for Pakistan. Updated for FBR 2025-26.',
        }
        return render(request, 'index.html', context)

        # return HttpResponse(str(context))

        return render(request, 'index.html', {'context' : context})
    except Exception as e:
        return HttpResponse(str(e))


def Login(request):
    try:
        if request.method == 'POST':
            username = request.POST.get('username', '').strip()
            pwd      = request.POST.get('password', '')
            user     = authenticate(request, username=username, password=pwd)
            if user:
                login(request, user)
                return redirect('Dashboard')
            messages.error(request, "Invalid username or password.")
        return render(request, 'Login.html')
    except Exception as e:
        return HttpResponse(str(e))


def Logout(request):
    logout(request)
    return redirect('/')


def BlogDetails(request, slug=None):
    if not slug:
        raise Http404("Blog slug not provided")

    blog = get_object_or_404(
        Blog, slug__iexact=slug.strip(), status='published', is_deleted=False
    )
    Blog.objects.filter(pk=blog.pk).update(view_count=F('view_count') + 1)

    blog_comments = Comment.objects.filter(status=1, slug=blog.slug)
    related_blogs = Blog.objects.filter(
        status='published', is_deleted=False
    ).exclude(slug=slug).order_by('-created_at')[:5]

    comment_form = CommentForm(initial={'slug': blog.slug})
    if request.method == 'POST':
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            Comment.objects.create(
                blog=blog,
                name=comment_form.cleaned_data['user'],
                email_address=comment_form.cleaned_data['email'],
                comment=comment_form.cleaned_data['comment'],
                slug=slug,
            )
            messages.success(request, "Comment submitted for review.")
            return redirect(reverse('BlogDetails', kwargs={'slug': slug}))

    return render(request, 'partials/BlogDetails.html', {
        'blog':          blog,
        'userComments':  blog_comments,
        'length':        blog_comments.count(),
        'blogList':      related_blogs,
        'tags_list':     blog.get_tags_list(),
        'comment_form':  comment_form,
        'meta_title':    blog.meta_title or blog.title,
        'meta_description': blog.meta_description,
    })


def viewBlogs(request, slug=None):
    try:
        if not slug:
            blogs = Blog.objects.filter(status='published', is_deleted=False).order_by('-created_at')
            category_name = 'All'
        else:
            category_name = slug.replace('-', ' ').strip()
            blogs = Blog.objects.filter(
                category__iexact=category_name,
                status='published',
                is_deleted=False
            ).order_by('-created_at')
            # Do NOT raise 404 — show empty state instead

        # Get unique categories for filter pills
        raw_cats = Blog.objects.filter(
            status='published', is_deleted=False
        ).exclude(category='').values_list('category', flat=True).distinct()
        categories = [(c.strip(), c.strip().lower().replace(' ', '-')) for c in raw_cats]

        paginator = Paginator(blogs, 9)
        page_obj  = paginator.get_page(request.GET.get('page'))

        return render(request, "clone.html", {
            "page_obj":      page_obj,
            "categories":    categories,
            "category_name": category_name,
            "meta_title":    f"{category_name} Tax Blog | TaxBuddy Umair",
        })
    except Exception as e:
        return render(request, "404.html", {"error": str(e)}, status=404)


def userComments(request):
    if request.method == 'POST':
        slug = request.POST.get('slug', '').strip()
        form = CommentForm(request.POST)
        if form.is_valid():
            blog = get_object_or_404(Blog, slug=slug)
            Comment.objects.create(
                blog=blog,
                name=form.cleaned_data['user'],
                email_address=form.cleaned_data['email'],
                comment=form.cleaned_data['comment'],
                slug=slug,
            )
            messages.success(request, "Comment submitted for review.")
            return redirect(reverse('BlogDetails', kwargs={'slug': slug}))
        messages.error(request, "Please fill all fields correctly.")
        return redirect(reverse('BlogDetails', kwargs={'slug': slug}) if slug else '/')
    return redirect('/')


def contact(request):
    if request.method == "POST":
        try:
            token = request.POST.get('g-recaptcha-response', '')
            recaptcha_secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', '')
            if recaptcha_secret:
                r = requests.post(
                    'https://www.google.com/recaptcha/api/siteverify',
                    data={'secret': recaptcha_secret, 'response': token},
                    timeout=5
                )
                result = r.json()
                if not result.get('success') or result.get('score', 0) < 0.5:
                    messages.error(request, "Captcha verification failed. Please try again.")
                    return redirect('/#contact')

            # Honeypot spam check — bots fill hidden field, humans don't
            if request.POST.get('website_url', ''):
                messages.success(request, "Thank you! We will contact you shortly.")
                return redirect('/#contact')

            form = ContactForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Thank you! We will contact you shortly.")
            else:
                messages.error(request, "Please fill in all required fields correctly.")
            return redirect('/#contact')
        except requests.RequestException:
            messages.error(request, "Could not verify captcha. Please try again.")
            return redirect('/#contact')
        except Exception as e:
            messages.error(request, "Something went wrong. Please try again.")
            return redirect('/#contact')
    return redirect('/')


def privacy_policy(request):
    return render(request, 'partials/privacy_policy.html', {
        'meta_title': 'Privacy Policy | TaxBuddy Umair',
    })


def terms_and_conditions(request):
    return render(request, 'partials/terms_conditions.html', {
        'meta_title': 'Terms & Conditions | TaxBuddy Umair',
    })


def income_tax_guides(request):
    blogs = Blog.objects.filter(
        category__iexact='income tax', status='published', is_deleted=False
    ).order_by('-created_at')
    faqs  = FAQ.objects.filter(page='income_tax', is_active=True)
    return render(request, 'income-tax-guides.html', {
        'blogs': blogs,
        'faqs':  faqs,
        'meta_title': 'Income Tax Guides Pakistan 2025-26 | TaxBuddy Umair',
        'meta_description': 'Complete income tax guides for salaried, business, and freelancers in Pakistan. Updated for FBR 2025-26.',
    })


def sales_tax_guides(request):
    blogs = Blog.objects.filter(
        category__iexact='sales tax', status='published', is_deleted=False
    ).order_by('-created_at')
    faqs  = FAQ.objects.filter(page='sales_tax', is_active=True)
    return render(request, 'sales-tax-guides.html', {
        'blogs': blogs,
        'faqs':  faqs,
        'meta_title': 'Sales Tax Guides Pakistan 2025-26 | TaxBuddy Umair',
    })


def income_tax_rates(request):
    try:
        active_section = request.GET.get('section', 'salary')
        selected_year  = request.GET.get("year")

        salary_years   = list(TaxBracket.objects.values_list("year", flat=True).distinct())
        business_years = list(Business_AOP_Slab.objects.values_list("year", flat=True).distinct())
        years          = sorted(set(salary_years + business_years), reverse=True)

        if not selected_year:
            selected_year = years[0] if years else None

        salary_brackets      = TaxBracket.objects.filter(year=selected_year).order_by("income_min")
        business_aop_brackets = Business_AOP_Slab.objects.filter(year=selected_year).order_by("income_min")

        for b in salary_brackets:
            b.rate_percent = b.rate * 100
        for b in business_aop_brackets:
            b.rate_percent = b.rate * 100

        company_tax_rates = {
            "2024-2025": {"Banking Company": 44, "Small Company": 20, "Any Other Company": 29},
            "2025-2026": {"Banking Company": 43, "Small Company": 20, "Any Other Company": 29},
            "2026-2027": {"Banking Company": 42, "Small Company": 20, "Any Other Company": 29},
        }

        return render(request, "partials/income_tax_rates.html", {
            "salary_brackets":    salary_brackets,
            "business_brackets":  business_aop_brackets,
            "aop_brackets":       business_aop_brackets,
            "years":              years,
            "selected_year":      selected_year,
            "active_section":     active_section,
            "company_tax_rates":  company_tax_rates,
            "meta_title":         f"Income Tax Rates {selected_year} Pakistan | TaxBuddy Umair",
        })
    except Exception as e:
        return HttpResponse("Exception: " + str(e))


def withholding_tax_rates(request):
    active_section = request.GET.get('section', 'sale')
    return render(request, 'partials/withholding-tax-rates.html', {
        'active_section': active_section,
        'meta_title': 'Withholding Tax Rates Pakistan 2025-26 | TaxBuddy Umair',
    })


def online_services(request):
    return render(request, "partials/online_services.html", {
        'meta_title': 'Online Tax Services | TaxBuddy Umair',
    })


def layout(request):
    blogs = Blog.objects.filter(status='published', is_deleted=False)
    return render(request, 'layout.html', {"blogs": blogs})


def test(request):
    return render(request, 'test.html')


# ─────────────────────────────────────────────────────────────
# CALCULATORS
# ─────────────────────────────────────────────────────────────

def AOPCalculator(request):
    context = {
        'title': 'AOP',
        'url': '/AOPCalculator/',
        'meta_title': 'AOP Income Tax Calculator Pakistan 2025-26 | TaxBuddy Umair',
        'meta_description': 'Calculate AOP (Association of Persons) income tax across multiple tax years using FBR slabs.',
        'content': {
            "title": "AOP Income Tax Calculator – Pakistan",
            "badge": "Multi-Year Tax Comparison",
            "intro": "Calculate and compare AOP tax liability across different tax years under ITO 2001.",
            "who": ["Registered partnership firms", "Unregistered partnership firms",
                    "Joint ventures", "Businesses classified as AOP"],
            "features": ["Compare AOP tax across multiple tax years",
                         "Yearly tax calculation based on AOP slabs",
                         "Accurate slab-based computation"],
            "notes": ["Partners' share may be taxed separately",
                      "Withholding tax adjustments not included",
                      "Actual liability may vary after assessment"],
        },
        'years': _get_all_tax_years(),
    }
    if request.method == 'POST':
        income_amount, error = validate_income(request.POST)
        if error:
            messages.error(request, error)
        else:
            income_type  = request.POST.get('income_type', 'Yearly')
            tax_year_1   = request.POST.get('tax_year_1')
            tax_year_2   = request.POST.get('tax_year_2')
            yearly_income = income_amount * 12 if income_type == 'Monthly' else income_amount
            try:
                context.update(FetchResult(tax_year_1, tax_year_2, 'AOP', yearly_income))
                context['income_type'] = income_type
            except Exception:
                messages.error(request, "Could not calculate tax. Please check your inputs.")
    return render(request, 'partials/aop_slab.html', context)


def BusinessCalculator(request):
    context = {
        'title': 'Business Individual',
        'url': '/BusinessCalculator/',
        'meta_title': 'Business Income Tax Calculator Pakistan 2025-26 | TaxBuddy Umair',
        'content': {
            "title": "Business Income Tax Calculator – Pakistan",
            "badge": "Monthly & Yearly Comparison",
            "intro": "Calculate and compare business income tax across different tax years.",
            "who": ["Sole proprietors", "Freelancers earning business income",
                    "Small and medium business owners", "Service providers and traders"],
            "features": ["Compare business tax across tax years",
                         "Monthly and yearly tax calculation",
                         "Net income based calculation"],
            "notes": ["Allowable expenses reduce taxable income",
                      "Advance and withholding tax not included",
                      "Sales tax excluded from this calculation"],
        },
        'years': _get_all_tax_years(),
    }
    if request.method == 'POST':
        income_amount, error = validate_income(request.POST)
        if error:
            messages.error(request, error)
        else:
            income_type  = request.POST.get('income_type', 'Yearly')
            tax_year_1   = request.POST.get('tax_year_1')
            tax_year_2   = request.POST.get('tax_year_2')
            yearly_income = income_amount * 12 if income_type == 'Monthly' else income_amount
            try:
                context.update(FetchResult(tax_year_1, tax_year_2, 'Business Individual', yearly_income))
                context['income_type'] = income_type
            except Exception:
                messages.error(request, "Could not calculate tax. Please check your inputs.")
    return render(request, 'partials/business_slab.html', context)


def SalaryCalculator(request):
    context = {
        'title': 'Salary Individual',
        'url': '/SalaryCalculator/',
        'meta_title': 'Salary Tax Calculator Pakistan 2025-26 | TaxBuddy Umair',
        'meta_description': 'Free salary income tax calculator for Pakistan. Compare tax across FBR tax years instantly.',
        'content': {
            "title": "Salary Income Tax Calculator – Pakistan",
            "badge": "Compare Tax by Year",
            "intro": "Calculate and compare salary tax liability across different FBR tax years.",
            "who": ["Government employees", "Private sector employees",
                    "Contract-based salaried individuals",
                    "Individuals earning salary income in Pakistan"],
            "features": ["Compare tax for multiple tax years",
                         "Monthly and yearly tax calculation",
                         "Based on FBR notified tax slabs"],
            "notes": ["Tax credits and exemptions not included",
                      "Allowances may be taxable depending on law",
                      "Final tax may vary based on individual profile"],
        },
        'years': _get_all_tax_years(),
    }
    if request.method == 'POST':
        income_amount, error = validate_income(request.POST)
        if error:
            messages.error(request, error)
        else:
            income_type   = request.POST.get('income_type', 'Yearly')
            tax_year_1    = request.POST.get('tax_year_1')
            tax_year_2    = request.POST.get('tax_year_2')
            yearly_income = income_amount * 12 if income_type == 'Monthly' else income_amount
            try:
                context.update(FetchResult(tax_year_1, tax_year_2, 'Salary Individual', yearly_income))
                context['income_type'] = income_type
            except Exception:
                messages.error(request, "Could not calculate tax. Please check your inputs.")
    return render(request, 'partials/salary_slab.html', context)


def PropertyCalculator(request):
    context = {
        'meta_title': 'Property / Rental Income Tax Calculator Pakistan | TaxBuddy Umair',
        'years': _get_all_tax_years(),
    }
    if request.method == 'POST':
        tax_year_1  = request.POST.get('tax_year_1')
        tax_year_2  = request.POST.get('tax_year_2')
        income_type = request.POST.get('income_type', 'Yearly')
        gross_rent  = to_int(request.POST.get('gross_rent', 0))

        if gross_rent <= 0:
            messages.error(request, "Please enter a valid gross rent amount.")
            return render(request, 'partials/property_rent.html', context)

        deductions = sum(to_int(request.POST.get(f)) for f in [
            'repairs_allowance', 'insurance_premium', 'local_taxes', 'ground_rent',
            'borrowed_interest', 'hbfc_payments', 'mortgage_interest',
            'admin_expenses', 'legal_expenses', 'irrecoverable_rent',
        ])
        yearly_income     = gross_rent * 12 if income_type == 'Monthly' else gross_rent
        net_rental_income = max(0, yearly_income - deductions)
        context.update(FetchResult(tax_year_1, tax_year_2, 'Rental Income', net_rental_income))
        context.update({
            'net_income_rental': net_rental_income,
            'total_deductions':  deductions,
            'yearly_income':     yearly_income,
            'income_type':       income_type,
        })
    return render(request, 'partials/property_rent.html', context)


def TaxCalculator4C(request):
    return render(request, 'TaxCalculator4C.html', {
        'meta_title': 'Super Tax Section 4C Calculator Pakistan | TaxBuddy Umair',
    })


def section_4c_rate_view(request):
    try:
        income   = int(float(request.GET.get("income", 0)))
        tax_year = int(request.GET.get("tax_year"))
    except (TypeError, ValueError):
        return JsonResponse({"rate": 0, "rate_percent": 0, "error": "Invalid input"}, status=400)

    slab = (
        SuperTax4CRate.objects
        .filter(tax_year=tax_year, income_from__lte=income)
        .filter(Q(income_to__gte=income) | Q(income_to__isnull=True))
        .order_by("income_from").first()
    )
    rate = float(slab.rate) if slab else 0.0
    return JsonResponse({
        "tax_year": tax_year,
        "income": income,
        "rate": rate,
        "rate_percent": round(rate * 100, 2),
    })


# ─────────────────────────────────────────────────────────────
# TAX CALCULATION CORE
# ─────────────────────────────────────────────────────────────

def _get_all_tax_years():
    s = list(TaxBracket.objects.values_list("year", flat=True).distinct())
    b = list(Business_AOP_Slab.objects.values_list("year", flat=True).distinct())
    return sorted(set(s + b), reverse=True)


def FetchResult(tax_year_1, tax_year_2, taxpayer_type, yearly_income):
    if taxpayer_type == 'Salary Individual':
        qs1 = TaxBracket.objects.filter(year=tax_year_1)
        qs2 = TaxBracket.objects.filter(year=tax_year_2)
    elif taxpayer_type in ('Business Individual', 'AOP'):
        qs1 = Business_AOP_Slab.objects.filter(year=tax_year_1)
        qs2 = Business_AOP_Slab.objects.filter(year=tax_year_2)
    else:
        qs1 = Property_Business_AOP_Slab.objects.filter(year=tax_year_1)
        qs2 = Property_Business_AOP_Slab.objects.filter(year=tax_year_2)

    def build_brackets(qs):
        return {
            (float(s.income_min), float(s.income_max) if s.income_max else float('inf')):
            (float(s.rate), float(s.base_income), float(s.base_tax))
            for s in qs
        }

    surcharge_rates = {"2024-2025": 0.10, "2025-2026": 0.09}
    surcharge_1 = surcharge_rates.get(tax_year_1, 0)
    surcharge_2 = surcharge_rates.get(tax_year_2, 0)

    return {
        'taxpayer_type':     taxpayer_type,
        'tax_year_1':        tax_year_1,
        'tax_year_2':        tax_year_2,
        'tax_year_1_result': calculate_tax(yearly_income, build_brackets(qs1), surcharge_1),
        'tax_year_2_result': calculate_tax(yearly_income, build_brackets(qs2), surcharge_2),
        'monthly_income':    int(yearly_income / 12),
        'yearly_income':     yearly_income,
        'surcharge_label_1': f"Surcharge {int(surcharge_1*100)}%" if surcharge_1 else None,
        'surcharge_label_2': f"Surcharge {int(surcharge_2*100)}%" if surcharge_2 else None,
    }


def calculate_tax(income, tax_brackets, surcharge_rate):
    SURCHARGE_THRESHOLD = 10_000_000
    for (lower, upper), (rate, base_threshold, fixed_tax) in tax_brackets.items():
        if lower <= income <= upper:
            if rate == 0:
                tax = tax_on_exceeding = amount_exceeding = 0
            else:
                amount_exceeding = income - base_threshold
                tax_on_exceeding = amount_exceeding * rate
                tax = round(fixed_tax + tax_on_exceeding)

            surcharge = 0
            total_tax_with_surcharge = tax
            if income > SURCHARGE_THRESHOLD:
                surcharge = round(tax * surcharge_rate)
                total_tax_with_surcharge = tax + surcharge

            return {
                'income': income, 'lower': lower, 'upper': upper,
                'base_threshold': base_threshold, 'fixed_tax': fixed_tax,
                'amount_exceeding': round(amount_exceeding),
                'rate': rate * 100,
                'tax_on_exceeding': round(tax_on_exceeding),
                'total_tax': tax, 'per_month': round(total_tax_with_surcharge / 12),
                'total_tax_with_surcharge': total_tax_with_surcharge,
                'surcharge': surcharge,
            }

    return {
        'income': income, 'lower': 0, 'upper': 0, 'base_threshold': 0,
        'fixed_tax': 0, 'amount_exceeding': 0, 'rate': 0,
        'tax_on_exceeding': 0, 'total_tax': 0, 'per_month': 0,
        'total_tax_with_surcharge': 0, 'surcharge': 0,
    }


# ─────────────────────────────────────────────────────────────
# MCQ / QUIZ
# ─────────────────────────────────────────────────────────────

def tax_knowledge_quiz(request):
    questions = (
        Question.objects.filter(is_active=True)
        .select_related("category")
        .prefetch_related("options")
        .order_by("category__order", "id")
    )
    return render(request, "tax-knowledge-quizz.html", {
        "questions": questions,
        "meta_title": "Tax Knowledge Quiz Pakistan | TaxBuddy Umair",
    })


def question_list(request, category_slug=None):
    try:
        OPTION_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        questions = Question.objects.prefetch_related("options").order_by("id")
        selected_category = None

        if category_slug:
            all_categories = (
                Question.objects.exclude(category__isnull=True).exclude(category='')
                .values_list("category", flat=True).distinct()
            )
            for c in all_categories:
                if slugify(c.strip()) == category_slug:
                    selected_category = c.strip()
                    break
            if selected_category:
                questions = questions.filter(category=selected_category)

        paginator = Paginator(questions, 10)
        page_obj  = paginator.get_page(request.GET.get("page"))

        raw_categories = (
            Question.objects.exclude(category__isnull=True).exclude(category='')
            .values_list("category", flat=True).distinct()
        )
        categories = [
            {"name": c.strip(), "slug": slugify(c.strip())}
            for c in sorted(set(raw_categories))
        ]

        return render(request, "partials/mcq-layout.html", {
            "page_obj":          page_obj,
            "categories":        categories,
            "selected_category": selected_category,
            "category_slug":     category_slug,
            "option_labels":     OPTION_LABELS,
            "meta_title":        f"{'Income Tax' if not selected_category else selected_category} MCQs Pakistan | TaxBuddy Umair",
            "meta_description":  "Practice 200+ income tax MCQs for CA, ICMAP, ACCA, and CSS exam preparation. ITO 2001 based.",
        })
    except Exception as e:
        return HttpResponse("Exception: " + str(e))


# ─────────────────────────────────────────────────────────────
# ADMIN / CPANEL VIEWS
# ─────────────────────────────────────────────────────────────

@login_required(login_url='Login')
def Dashboard(request):
    context = {
        'total_blogs':    Blog.objects.filter(is_deleted=False).count(),
        'published_blogs': Blog.objects.filter(status='published', is_deleted=False).count(),
        'total_contacts': Contact.objects.count(),
        'unread_contacts': Contact.objects.filter(is_read=False).count(),
        'total_questions': Question.objects.count(),
    }
    return render(request, 'Cpanel/Dashboard.html', context)


@login_required
def AddEditBlog(request, slug=None):
    blog = None
    if slug:
        blog = get_object_or_404(Blog, slug=slug, is_deleted=False)

    if request.method == "POST":
        data = {
            'title':            request.POST.get("title", "").strip(),
            'type':             request.POST.get("type"),
            'content':          request.POST.get("content"),
            'status':           request.POST.get("status"),
            'meta_title':       request.POST.get("meta_title", "").strip(),
            'meta_description': request.POST.get("meta_description", "").strip(),
            'tag':              request.POST.get("tag", ""),
            'category':         request.POST.get("category"),
        }
        if blog:
            for key, val in data.items():
                setattr(blog, key, val)
        else:
            blog = Blog(**data, author=request.user)

        if request.FILES.get("featured_image"):
            blog.featured_image = request.FILES["featured_image"]

        blog.save()
        messages.success(request, "Blog saved successfully.")
        return redirect("ManageBlogs")

    return render(request, "Cpanel/AddEditBlog.html", {"blog": blog})


@login_required(login_url='Login')
def deleteBlog(request, slug=None):
    blog = get_object_or_404(Blog, slug=slug, is_deleted=False)
    blog.is_deleted = True
    blog.deleted_at = now()
    blog.save()
    messages.success(request, "Blog deleted successfully.")
    return redirect('ManageBlogs')


@login_required(login_url='Login')
def ManageBlogs(request):
    result = Blog.objects.filter(is_deleted=False).order_by('-id')
    return render(request, 'Cpanel/ManageBlogs.html', {'result': result})


@login_required(login_url='Login')
def add_salary_tax_brackets(request):
    if request.method == 'POST':
        try:
            tax_year      = request.POST.get('tax_year')
            income_min    = request.POST.get('income_min')
            income_max    = request.POST.get('income_max')
            rate          = request.POST.get('rate')
            base_income   = request.POST.get('base_income')
            base_tax      = request.POST.get('base_tax')
            taxpayer_type = request.POST.get('taxpayer_type')
            income_max_val = None if income_max in ('', None, 'inf') else income_max

            if taxpayer_type == 'ind_aop_person':
                Business_AOP_Slab.objects.create(
                    year=tax_year, income_min=income_min, income_max=income_max_val,
                    rate=Decimal(str(rate)), base_income=base_income, base_tax=base_tax,
                )
            else:
                TaxBracket.objects.create(
                    year=tax_year, income_min=income_min, income_max=income_max_val,
                    rate=Decimal(str(rate)), base_income=base_income, base_tax=base_tax,
                )
            messages.success(request, "Tax bracket added successfully.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    return render(request, 'Cpanel/add_salary_tax_brackets.html')


@login_required(login_url='Login')
def add_question(request):
    if request.method == "POST":
        question_text = request.POST.get("question_text", "").strip()
        category      = request.POST.get("category", "").strip()
        explanation   = request.POST.get("explanation", "").strip()
        section_ref   = request.POST.get("section_ref", "").strip()
        difficulty    = request.POST.get("difficulty", "basic")
        is_active     = bool(request.POST.get("is_active"))
        options       = request.POST.getlist("options[]")
        correct_index = request.POST.get("correct_option")

        if not all([question_text, category, explanation]):
            messages.error(request, "Please fill all required fields.")
            return redirect("questions-add")
        if correct_index in (None, ""):
            messages.error(request, "Please select the correct option.")
            return redirect("questions-add")
        if len(options) < 2:
            messages.error(request, "At least two options are required.")
            return redirect("questions-add")

        question = Question.objects.create(
            question_text=question_text, category=category, explanation=explanation,
            section_ref=section_ref, difficulty=difficulty, is_active=is_active,
        )
        for i, opt in enumerate(options):
            if opt.strip():
                Option.objects.create(
                    question=question, option_text=opt.strip(),
                    is_correct=(str(i) == correct_index),
                )
        messages.success(request, "Question added successfully.")
        return redirect("questions-add")

    return render(request, "Cpanel/question.html", {
        "url": "questions-add", "id": "", "question": None, "options": [],
    })


@login_required(login_url='Login')
def view_questions(request):
    questions = Question.objects.all().order_by("category", "id")
    return render(request, "Cpanel/view_questions.html", {"questions": questions})


@login_required(login_url='Login')
def edit_question(request, pk):
    question = get_object_or_404(Question, pk=pk)
    options  = list(question.options.all())

    if request.method == "POST":
        question.question_text = request.POST.get("question_text", "").strip()
        question.category      = request.POST.get("category", "").strip()
        question.explanation   = request.POST.get("explanation", "").strip()
        question.section_ref   = request.POST.get("section_ref", "").strip()
        question.difficulty    = request.POST.get("difficulty", "basic")
        question.is_active     = bool(request.POST.get("is_active"))
        question.save()

        option_texts  = request.POST.getlist("options[]")
        correct_index = request.POST.get("correct_option")
        for i, opt in enumerate(options):
            if i < len(option_texts):
                opt.option_text = option_texts[i].strip()
                opt.is_correct  = (str(i) == correct_index)
                opt.save()

        messages.success(request, "Question updated successfully.")
        return redirect("questions-list")

    return render(request, "Cpanel/question.html", {
        "question": question, "options": options,
        "url": "questions-edit", "id": question.id,
    })


@login_required(login_url='Login')
def delete_question(request, pk):
    question = get_object_or_404(Question, pk=pk)
    question.delete()
    messages.success(request, "Question deleted successfully.")
    return redirect("questions-list")


# ─────────────────────────────────────────────────────────────
# SEO
# ─────────────────────────────────────────────────────────────

@cache_page(60 * 60 * 24)
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /dashboard/",
        "Disallow: /admin/",
        "Disallow: /login/",
        "Disallow: /manage-blogs/",
        "Disallow: /add-blog/",
        "Disallow: /edit-blog/",
        "Disallow: /delete-blog/",
        "Disallow: /questions/add/",
        "Disallow: /questions/edit/",
        "Disallow: /questions/delete/",
        "Disallow: /add-tax-brackets/",
        "",
        "# Allow calculators — important for SEO",
        "Allow: /SalaryCalculator/",
        "Allow: /BusinessCalculator/",
        "Allow: /AOPCalculator/",
        "Allow: /PropertyCalculator/",
        "Allow: /TaxCalculator4C/",
        "",
        "Sitemap: https://www.taxbuddyumair.com/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def custom_404(request, exception=None):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)


def legacy_blog_redirect(request, slug):
    """
    301 redirect: old /<slug>/ URLs → /articles/<slug>/
    Preserves Google rankings for previously indexed blog URLs.
    """
    from django.shortcuts import redirect as django_redirect
    # Check if blog exists — if not, return proper 404
    blog = Blog.objects.filter(slug__iexact=slug, status='published', is_deleted=False).first()
    if blog:
        return django_redirect(f'/articles/{blog.slug}/', permanent=True)
    return render(request, '404.html', status=404)
