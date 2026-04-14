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
from .models import (
    Blog, Comment, Contact, TaxBracket, Business_AOP_Slab,
    Property_Business_AOP_Slab, Question, Option,
    SuperTax4CRate, Category, Tag
)
from django.core.paginator import Paginator


# ─────────────────────────────────────────────────────────────
# UTILITY HELPERS
# ─────────────────────────────────────────────────────────────

def to_int(value, default=0):
    """Safely convert a value to int, return default on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_income(request_post, field='income_amount'):
    """
    Parse income_amount from POST data.
    Returns (amount_int, error_message_or_None).
    """
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


        questions = Question.objects.filter(
            is_active=True
        ).prefetch_related("options")

        questions_list = list(questions)
        preview_questions = random.sample(questions_list, min(len(questions_list), 3))

        # FIX: removed redundant `result` query that was never used properly
        latest_blogs = Blog.objects.filter(
            status='published',
            is_deleted=False,
            created_at__gte=now().date() - timedelta(days=3)
        ).order_by('-updated_at')[:3]

        all_blogs = Blog.objects.filter(
            status='published',
            is_deleted=False
        ).order_by('-created_at')

        context = {
                "badges": [
                "✓ 10,000+ followers",
                "✓ Active FBR officer",
                "✓ Tax Year 2026"
            ],

        "hero_stats": [
            ("10K+", "Followers"),
            ("30+", "Guides"),
            ("5", "Calculators"),
            ("2026", "Updated"),
        ],

        "hero_tags": [
            "ITO 2001",
            "STA 1990",
            "IRIS Portal",
            "FBR Compliance"
        ],

        "quick_links": [
            ("income_tax_guides", "Income Tax Guides"),
            ("sales_tax_guides", "Sales Tax Guides"),
            ("income_tax_rates", "Tax Rates"),
            ("question_list", "MCQs"),
            ("SalaryCalculator", "Salary Calculator"),
        ],

        "contact_items": [
            ("📱", "WhatsApp", "+92 333 2482742", "tel:+923332482742"),
            ("📧", "Email", "umair.mubeenir@gmail.com", "mailto:umair.mubeenir@gmail.com"),
            ("📍", "Location", "Gulshan-e-Iqbal, Karachi", "#"),
        ],
            'result': all_blogs,
            'latest_blogs': latest_blogs,
            'preview_questions': preview_questions,
        },

        return render(request, 'index.html', {'context' : context})
    except Exception as e:
        return HttpResponse(str(e))


def Login(request):
    try:
        if request.method == 'POST':
            username = request.POST.get('username', '').strip()
            pwd = request.POST.get('password', '')
            user = authenticate(request, username=username, password=pwd)
            if user:
                login(request, user)
                request.session['username'] = username
                return redirect('Dashboard')
            else:
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
        Blog,
        slug__iexact=slug.strip(),
        status='published',
        is_deleted=False
    )

    # FIX: Track view count safely using F() to avoid race conditions
    Blog.objects.filter(pk=blog.pk).update(
        view_count=F('view_count') + 1
    ) if hasattr(blog, 'view_count') else None

    tags_list = []
    if blog.tag:
        tags_list = [t.strip() for t in blog.tag.split(',') if t.strip()]

    blog_comments = Comment.objects.filter(
        status=1,
        slug=blog.slug
    )

    related_blogs = Blog.objects.filter(
        status='published',
        is_deleted=False
    ).exclude(slug=slug).order_by('-created_at')[:5]

    return render(request, 'partials/BlogDetails.html', {
        'blog': blog,
        'userComments': blog_comments,
        'length': blog_comments.count(),
        'blogList': related_blogs,
        'tags_list': tags_list,
    })


def viewBlogs(request, slug=None):
    try:
        if not slug:
            raise Http404("Category not found")

        category_name = slug.replace('-', ' ').strip()

        blogs = Blog.objects.filter(
            category__iexact=category_name,
            status='published',
            is_deleted=False
        ).order_by('-created_at')

        # safer fallback instead of hard crash
        if not blogs.exists():
            raise Http404("No blogs found in this category")

        calculators = [
            ("Salary Calculator", "SalaryCalculator"),
            ("Business Calculator", "BusinessCalculator"),
            ("AOP Calculator", "AOPCalculator"),
            ("Property Calculator", "PropertyCalculator"),
        ]

        return render(request, "clone.html", {
            "blogs": blogs,
            "calculators": calculators,
            "category_name": category_name
        })

    except Http404:
        raise
    except Exception as e:
        return render(request, "error.html", {
            "error": str(e)
        })

def userComments(request):
    try:
        if request.method == 'POST':
            user = request.POST.get('user', '').strip()
            email = request.POST.get('email', '').strip()
            comment = request.POST.get('comment', '').strip()
            slug = request.POST.get('slug', '').strip()

            if not all([user, email, comment, slug]):
                messages.error(request, "All fields are required.")
                return redirect(reverse('BlogDetails', kwargs={'slug': slug}) if slug else '/')

            blog = get_object_or_404(Blog, slug=slug)
            Comment.objects.create(
                blog=blog,
                name=user,
                email_address=email,
                comment=comment,
                slug=slug
            )
            # FIX: use reverse() instead of f-string to avoid double-slash
            return redirect(reverse('BlogDetails', kwargs={'slug': slug}))

    except Exception as e:
        return HttpResponse(str(e))


def contact(request):
    if request.method == "POST":
        try:
            token = request.POST.get('g-recaptcha-response', '')

            # FIX: secret key must be in settings.py / .env — NEVER hardcoded
            # Add to settings.py: RECAPTCHA_SECRET_KEY = env('RECAPTCHA_SECRET_KEY')
            recaptcha_secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', '')

            r = requests.post(
                'https://www.google.com/recaptcha/api/siteverify',
                data={'secret': recaptcha_secret, 'response': token},
                timeout=5  # FIX: add timeout to prevent hanging
            )
            result = r.json()

            if not result.get('success') or result.get('score', 0) < 0.5:
                messages.error(request, "Captcha verification failed. Please try again.")
                return redirect('/#contact')

            Contact.objects.create(
                first_name=request.POST.get('first_name', '').strip(),
                last_name=request.POST.get('last_name', '').strip(),
                phone_number=request.POST.get('phone_number', '').strip(),
                email_address=request.POST.get('email_address', '').strip(),
                subject=request.POST.get('subject', '').strip(),
                additional_details=request.POST.get('additional_details', '').strip(),
            )

            messages.success(request, "Thank you! We will contact you shortly.")
            return redirect('/#contact')

        except requests.RequestException as e:
            # FIX: handle network errors from reCAPTCHA separately
            messages.error(request, "Could not verify captcha. Please try again.")
            return redirect('/#contact')
        except Exception as e:
            messages.error(request, "Something went wrong. Please try again.")
            return redirect('/#contact')

    return redirect('/')


def privacy_policy(request):
    try:
        return render(request, 'partials/privacy_policy.html')
    except Exception as e:
        return HttpResponse("Exception: " + str(e))


def terms_and_conditions(request):
    try:
        return render(request, 'partials/terms_conditions.html')
    except Exception as e:
        return HttpResponse("Exception: " + str(e))


def income_tax_guides(request):
    try:
        return render(request, 'income-tax-guides.html')
    except Exception as e:
        return HttpResponse(str(e))


def sales_tax_guides(request):
    try:
        return render(request, 'sales-tax-guides.html')
    except Exception as e:
        return HttpResponse(str(e))


def income_tax_rates(request):
    try:
        active_section = request.GET.get('section', 'salary')
        selected_year = request.GET.get("year")

        salary_years = list(TaxBracket.objects.values_list("year", flat=True).distinct())
        business_years = list(Business_AOP_Slab.objects.values_list("year", flat=True).distinct())
        years = sorted(set(salary_years + business_years), reverse=True)

        if not selected_year:
            selected_year = years[0] if years else None

        salary_brackets = TaxBracket.objects.filter(year=selected_year).order_by("income_min")
        business_aop_brackets = Business_AOP_Slab.objects.filter(year=selected_year).order_by("income_min")

        for bracket in salary_brackets:
            bracket.rate_percent = bracket.rate * 100

        for bracket in business_aop_brackets:
            bracket.rate_percent = bracket.rate * 100

        # FIX: keys were arithmetic expressions (2024-2025 = -1). Use strings.
        company_tax_rates = {
            "2024-2025": {
                "Banking Company": 44,
                "Small Company": 20,
                "Any Other Company": 29,
            },
            "2025-2026": {
                "Banking Company": 43,
                "Small Company": 20,
                "Any Other Company": 29,
            },
            "2026-2027": {
                "Banking Company": 42,
                "Small Company": 20,
                "Any Other Company": 29,
            },
        }

        return render(request, "partials/income_tax_rates.html", {
            "salary_brackets": salary_brackets,
            "business_brackets": business_aop_brackets,
            "aop_brackets": business_aop_brackets,
            "years": years,
            "selected_year": selected_year,
            "active_section": active_section,
            "company_tax_rates": company_tax_rates,
        })

    except Exception as e:
        return HttpResponse("Exception: " + str(e))


def withholding_tax_rates(request):
    try:
        active_section = request.GET.get('section', 'sale')
        return render(request, 'partials/withholding-tax-rates.html', {
            'active_section': active_section
        })
    except Exception as e:
        return HttpResponse("Exception: " + str(e))


def online_services(request):
    try:
        return render(request, "partials/online_services.html")
    except Exception as e:
        return HttpResponse("Exception: " + str(e))


def layout(request):
    try:
        blogs = Blog.objects.filter(status='published', is_deleted=False)
        return render(request, 'layout.html', {"blogs": blogs})
    except Exception as e:
        return HttpResponse("Exception: " + str(e))


def test(request):
    return render(request, 'test.html')


# ─────────────────────────────────────────────────────────────
# CALCULATORS
# ─────────────────────────────────────────────────────────────

def AOPCalculator(request):
    content = {
        "title": "AOP Income Tax Calculator – Pakistan",
        "badge": "Multi-Year Tax Comparison",
        "intro": "Calculate and compare AOP tax liability across different tax years under ITO 2001.",
        "who": [
            "Registered partnership firms",
            "Unregistered partnership firms",
            "Joint ventures",
            "Businesses classified as Association of Persons (AOP)",
        ],
        "how": "Enter the taxable income of the AOP and select one or more tax years.",
        "features": [
            "Compare AOP tax across multiple tax years",
            "Yearly tax calculation based on AOP slabs",
            "Accurate slab-based computation",
            "Instant comparison results",
        ],
        "example": [
            "Monthly income: PKR 400,000",
            "Annual income: PKR 4,800,000",
            "Tax comparison across selected tax years",
        ],
        "notes": [
            "Partners' share of profit may be taxed separately",
            "Withholding tax adjustments are not included",
            "Actual tax liability may vary after assessment",
        ],
    }

    context = {'content': content, 'title': 'AOP', 'url': '/AOPCalculator'}

    if request.method == 'POST':
        # FIX: validate income before processing
        income_amount, error = validate_income(request.POST)
        if error:
            messages.error(request, error)
            return render(request, 'partials/aop_slab.html', context)

        income_type = request.POST.get('income_type', 'Yearly')
        tax_year_1 = request.POST.get('tax_year_1')
        tax_year_2 = request.POST.get('tax_year_2')
        yearly_income = income_amount * 12 if income_type == 'Monthly' else income_amount

        try:
            result_context = FetchResult(tax_year_1, tax_year_2, 'AOP', yearly_income)
            context.update(result_context)
            context['income_type'] = income_type
        except Exception as e:
            messages.error(request, "Could not calculate tax. Please check your inputs.")

    return render(request, 'partials/aop_slab.html', context)


def BusinessCalculator(request):
    content = {
        "title": "Business Income Tax Calculator – Pakistan",
        "badge": "Monthly & Yearly Comparison",
        "intro": "Calculate and compare business income tax across different tax years.",
        "who": [
            "Sole proprietors",
            "Freelancers earning business income",
            "Small and medium business owners",
            "Service providers and traders",
        ],
        "how": "Enter your net business income and select one or more tax years.",
        "features": [
            "Compare business tax across tax years",
            "Monthly and yearly tax calculation",
            "Net income based calculation",
            "Instant comparison results",
        ],
        "example": [
            "Monthly profit: PKR 200,000",
            "Annual profit: PKR 2,400,000",
            "Tax comparison across selected tax years",
        ],
        "notes": [
            "Allowable business expenses reduce taxable income",
            "Advance and withholding tax not included",
            "Sales tax is excluded from this calculation",
        ],
    }

    context = {'content': content, 'title': 'Business Individual', 'url': '/BusinessCalculator'}

    if request.method == 'POST':
        income_amount, error = validate_income(request.POST)
        if error:
            messages.error(request, error)
            return render(request, 'partials/business_slab.html', context)

        income_type = request.POST.get('income_type', 'Yearly')
        tax_year_1 = request.POST.get('tax_year_1')
        tax_year_2 = request.POST.get('tax_year_2')
        yearly_income = income_amount * 12 if income_type == 'Monthly' else income_amount

        try:
            result_context = FetchResult(tax_year_1, tax_year_2, 'Business Individual', yearly_income)
            context.update(result_context)
            context['income_type'] = income_type
        except Exception as e:
            messages.error(request, "Could not calculate tax. Please check your inputs.")

    return render(request, 'partials/business_slab.html', context)


def SalaryCalculator(request):
    content = {
        "title": "Salary Income Tax Calculator – Pakistan",
        "badge": "Compare Tax by Year",
        "intro": "Calculate and compare salary tax liability across different FBR tax years.",
        "who": [
            "Government employees",
            "Private sector employees",
            "Contract-based salaried individuals",
            "Individuals earning salary income in Pakistan",
        ],
        "how": "Enter your salary and select one or more tax years.",
        "features": [
            "Compare tax for multiple tax years",
            "Monthly and yearly tax calculation",
            "Based on FBR notified tax slabs",
            "Instant comparison results",
        ],
        "example": [
            "Monthly salary: PKR 100,000",
            "Tax Year 2025 vs Tax Year 2026 comparison",
            "Monthly and annual tax difference displayed",
        ],
        "notes": [
            "Tax credits and exemptions are not included",
            "Allowances may be taxable depending on law",
            "Final tax may vary based on individual profile",
        ],
    }

    context = {'content': content, 'title': 'Salary Individual', 'url': '/SalaryCalculator'}

    if request.method == 'POST':
        income_amount, error = validate_income(request.POST)
        if error:
            messages.error(request, error)
            return render(request, 'partials/salary_slab.html', context)

        income_type = request.POST.get('income_type', 'Yearly')
        tax_year_1 = request.POST.get('tax_year_1')
        tax_year_2 = request.POST.get('tax_year_2')
        yearly_income = income_amount * 12 if income_type == 'Monthly' else income_amount

        try:
            result_context = FetchResult(tax_year_1, tax_year_2, 'Salary Individual', yearly_income)
            context.update(result_context)
            context['income_type'] = income_type
        except Exception as e:
            messages.error(request, "Could not calculate tax. Please check your inputs.")

    return render(request, 'partials/salary_slab.html', context)


def PropertyCalculator(request):
    try:
        if request.method == 'POST':
            tax_year_1 = request.POST.get('tax_year_1')
            tax_year_2 = request.POST.get('tax_year_2')
            income_type = request.POST.get('income_type', 'Yearly')

            gross_rent = to_int(request.POST.get('gross_rent', 0))
            if gross_rent <= 0:
                messages.error(request, "Please enter a valid gross rent amount.")
                return render(request, 'partials/property_rent.html')

            repairs_allowance   = to_int(request.POST.get('repairs_allowance'))
            insurance_premium   = to_int(request.POST.get('insurance_premium'))
            local_taxes         = to_int(request.POST.get('local_taxes'))
            ground_rent         = to_int(request.POST.get('ground_rent'))
            borrowed_interest   = to_int(request.POST.get('borrowed_interest'))
            hbfc_payments       = to_int(request.POST.get('hbfc_payments'))
            mortgage_interest   = to_int(request.POST.get('mortgage_interest'))
            admin_expenses      = to_int(request.POST.get('admin_expenses'))
            legal_expenses      = to_int(request.POST.get('legal_expenses'))
            irrecoverable_rent  = to_int(request.POST.get('irrecoverable_rent'))

            total_deductions = (
                repairs_allowance + insurance_premium + local_taxes +
                ground_rent + borrowed_interest + hbfc_payments +
                mortgage_interest + admin_expenses + legal_expenses +
                irrecoverable_rent
            )

            yearly_income = gross_rent * 12 if income_type == 'Monthly' else gross_rent
            net_rental_income = max(0, yearly_income - total_deductions)

            context = FetchResult(tax_year_1, tax_year_2, 'Rental Income', net_rental_income)
            context.update({
                'net_income_rental': net_rental_income,
                'total_deductions': total_deductions,
                'yearly_income': yearly_income,
            })
            return render(request, 'partials/property_rent.html', context)

        return render(request, 'partials/property_rent.html')

    except Exception as e:
        return HttpResponse(f"Error: {str(e)}")


# ─────────────────────────────────────────────────────────────
# TAX CALCULATION CORE
# ─────────────────────────────────────────────────────────────

def FetchResult(tax_year_1, tax_year_2, taxpayer_type, yearly_income):
    """
    Fetch tax brackets for two years, calculate tax, and return a context dict.
    Raises exceptions — callers should catch them.
    """
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

    brackets_1 = build_brackets(qs1)
    brackets_2 = build_brackets(qs2)

    surcharge_rates = {
        "2024-2025": 0.10,
        "2025-2026": 0.09,
    }

    surcharge_1 = surcharge_rates.get(tax_year_1, 0)
    surcharge_2 = surcharge_rates.get(tax_year_2, 0)

    surcharge_label_1 = f"Surcharge {int(surcharge_1 * 100)}%" if surcharge_1 else None
    surcharge_label_2 = f"Surcharge {int(surcharge_2 * 100)}%" if surcharge_2 else None

    result_1 = calculate_tax(yearly_income, brackets_1, surcharge_1)
    result_2 = calculate_tax(yearly_income, brackets_2, surcharge_2)

    return {
        'taxpayer_type': taxpayer_type,
        'tax_year_1': tax_year_1,
        'tax_year_2': tax_year_2,
        'tax_year_1_result': result_1,
        'tax_year_2_result': result_2,
        'monthly_income': int(yearly_income / 12),
        'yearly_income': yearly_income,
        'surcharge_label_1': surcharge_label_1,
        'surcharge_label_2': surcharge_label_2,
    }


def calculate_tax(income, tax_brackets, surcharge_rate):
    """
    Calculate tax for a given income using bracket dict.
    FIX: returns a zero-tax dict instead of None when no bracket matches.
    """
    SURCHARGE_THRESHOLD = 10_000_000  # PKR 10 million

    for (lower, upper), (rate, base_threshold, fixed_tax) in tax_brackets.items():
        if lower <= income <= upper:
            if rate == 0:
                tax = 0
                tax_on_exceeding = 0
                amount_exceeding = 0
            else:
                amount_exceeding = income - base_threshold
                tax_on_exceeding = amount_exceeding * rate
                tax = round(fixed_tax + tax_on_exceeding)

            surcharge = 0
            total_tax_with_surcharge = tax

            if income > SURCHARGE_THRESHOLD:
                surcharge = round(tax * surcharge_rate)
                total_tax_with_surcharge = tax + surcharge

            monthly_tax = round(total_tax_with_surcharge / 12)

            return {
                'income': income,
                'lower': lower,
                'upper': upper,
                'base_threshold': base_threshold,
                'fixed_tax': fixed_tax,
                'amount_exceeding': round(amount_exceeding),
                'rate': rate * 100,
                'tax_on_exceeding': round(tax_on_exceeding),
                'total_tax': tax,
                'per_month': monthly_tax,
                'total_tax_with_surcharge': total_tax_with_surcharge,
                'surcharge': surcharge,
            }

    # FIX: return zero-tax dict instead of None to prevent template crashes
    return {
        'income': income,
        'lower': 0,
        'upper': 0,
        'base_threshold': 0,
        'fixed_tax': 0,
        'amount_exceeding': 0,
        'rate': 0,
        'tax_on_exceeding': 0,
        'total_tax': 0,
        'per_month': 0,
        'total_tax_with_surcharge': 0,
        'surcharge': 0,
    }


# ─────────────────────────────────────────────────────────────
# MCQ / QUIZ VIEWS
# ─────────────────────────────────────────────────────────────

def tax_knowledge_quiz(request):
    questions = (
        Question.objects
        .filter(is_active=True)
        .select_related("category")
        .prefetch_related("options")
        .order_by("category__order", "id")
    )
    return render(request, "tax-knowledge-quizz.html", {"questions": questions})


def question_list(request, category_slug=None):
    try:
        OPTION_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        questions = Question.objects.prefetch_related("options").order_by("id")
        selected_category = None

        if category_slug:
            # FIX: more efficient category lookup
            all_categories = (
                Question.objects
                .exclude(category__isnull=True)
                .exclude(category='')
                .values_list("category", flat=True)
                .distinct()
            )
            for c in all_categories:
                if slugify(c.strip()) == category_slug:
                    selected_category = c.strip()
                    break

            if selected_category:
                questions = questions.filter(category=selected_category)

        paginator = Paginator(questions, 10)
        page_obj = paginator.get_page(request.GET.get("page"))

        # FIX: efficient single-query distinct category list
        raw_categories = (
            Question.objects
            .exclude(category__isnull=True)
            .exclude(category='')
            .values_list("category", flat=True)
            .distinct()
        )
        categories = [
            {"name": c.strip(), "slug": slugify(c.strip())}
            for c in sorted(set(raw_categories))
        ]

        score_rows = [
            ("Answered", "0 / 0", "answered"),
            ("Correct", "0", "correct"),
            ("Wrong", "0", "wrong"),
            ("Score", "—", "score"),

        ]


        return render(request, "partials/mcq-layout.html", {
            "page_obj": page_obj,
            "categories": categories,
            "selected_category": selected_category,
            "seo_category": selected_category,
            "category_slug": category_slug,
            'score_rows' : score_rows,
            "option_labels" : OPTION_LABELS
        })

    except Exception as e:
        return HttpResponse("Exception: " + str(e))


def TaxCalculator4C(request):
    try:
        return render(request, 'TaxCalculator4C.html')
    except Exception as e:
        return HttpResponse("Exception: " + str(e))


def section_4c_rate_view(request):
    try:
        income = int(float(request.GET.get("income", 0)))
        tax_year = int(request.GET.get("tax_year"))
    except (TypeError, ValueError):
        return JsonResponse({"rate": 0, "rate_percent": 0, "error": "Invalid income or tax year"}, status=400)

    slab = (
        SuperTax4CRate.objects
        .filter(tax_year=tax_year, income_from__lte=income)
        .filter(Q(income_to__gte=income) | Q(income_to__isnull=True))
        .order_by("income_from")
        .first()
    )

    rate = float(slab.rate) if slab else 0.0
    return JsonResponse({
        "tax_year": tax_year,
        "income": income,
        "rate": rate,
        "rate_percent": round(rate * 100, 2),
    })


# ─────────────────────────────────────────────────────────────
# ADMIN / CPANEL VIEWS
# ─────────────────────────────────────────────────────────────

@login_required(login_url='Login')
def Dashboard(request):
    try:
        return render(request, 'Cpanel/Dashboard.html')
    except Exception as e:
        return HttpResponse(str(e))


@login_required
def AddEditBlog(request, slug=None):
    blog = None
    if slug:
        blog = get_object_or_404(Blog, slug=slug, is_deleted=False)

    if request.method == "POST":
        tag = request.POST.get("tag", "")

        if blog:
            blog.title = request.POST.get("title", "").strip()
            blog.type = request.POST.get("type")
            blog.content = request.POST.get("content")
            blog.status = request.POST.get("status")
            blog.meta_title = request.POST.get("meta_title", "").strip()
            blog.meta_description = request.POST.get("meta_description", "").strip()
            blog.tag = tag
            blog.category = request.POST.get("category")
        else:
            blog = Blog(
                title=request.POST.get("title", "").strip(),
                type=request.POST.get("type"),
                content=request.POST.get("content"),
                status=request.POST.get("status"),
                meta_title=request.POST.get("meta_title", "").strip(),
                meta_description=request.POST.get("meta_description", "").strip(),
                author=request.user,
                tag=tag,
                category=request.POST.get("category"),
            )

        if request.FILES.get("featured_image"):
            blog.featured_image = request.FILES["featured_image"]

        blog.save()
        messages.success(request, "Blog saved successfully.")
        return redirect("ManageBlogs")

    return render(request, "Cpanel/AddEditBlog.html", {"blog": blog})


@login_required(login_url='Login')
def deleteBlog(request, slug=None):
    """
    FIX: soft delete using is_deleted flag instead of hard delete.
    Also fixed: was filtering status=1 (int) on a string field.
    """
    try:
        blog = get_object_or_404(Blog, slug=slug, is_deleted=False)
        blog.is_deleted = True
        blog.deleted_at = now()
        blog.save()
        messages.success(request, "Blog deleted successfully.")
        return redirect('ManageBlogs')
    except Exception as e:
        return HttpResponse('Exception at Delete Blog: ' + str(e))


@login_required(login_url='Login')
def ManageBlogs(request):
    try:
        result = Blog.objects.filter(is_deleted=False).order_by('-id')
        return render(request, 'Cpanel/ManageBlogs.html', {'result': result})
    except Exception as e:
        return HttpResponse('Exception at Manage Blog Page: ' + str(e))


@login_required(login_url='Login')
def add_salary_tax_brackets(request):
    try:
        if request.method == 'POST':
            tax_year = request.POST.get('tax_year')
            income_min = request.POST.get('income_min')
            income_max = request.POST.get('income_max')
            rate = request.POST.get('rate')
            base_income = request.POST.get('base_income')
            base_tax = request.POST.get('base_tax')
            taxpayer_type = request.POST.get('taxpayer_type')

            income_max_val = None if income_max in ('', None, 'inf') else income_max

            if taxpayer_type == 'ind_aop_person':
                Business_AOP_Slab.objects.create(
                    year=tax_year,
                    income_min=income_min,
                    income_max=income_max_val,
                    rate=Decimal(str(rate)),
                    base_income=base_income,
                    base_tax=base_tax,
                )
            else:
                TaxBracket.objects.create(
                    year=tax_year,
                    income_min=income_min,
                    income_max=income_max_val,
                    rate=Decimal(str(rate)),
                    base_income=base_income,
                    base_tax=base_tax,
                )
            messages.success(request, "Tax bracket added successfully.")

        return render(request, 'Cpanel/add_salary_tax_brackets.html')

    except Exception as e:
        return HttpResponse(f"Error: {str(e)}")


@login_required(login_url='Login')
def add_question(request):
    if request.method == "POST":
        question_text = request.POST.get("question_text", "").strip()
        category = request.POST.get("category", "").strip()
        explanation = request.POST.get("explanation", "").strip()
        section_ref = request.POST.get("section_ref", "").strip()
        difficulty = request.POST.get("difficulty", "basic")
        is_active = bool(request.POST.get("is_active"))
        options = request.POST.getlist("options[]")
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
            question_text=question_text,
            category=category,
            explanation=explanation,
            section_ref=section_ref,
            difficulty=difficulty,
            is_active=is_active,
        )

        for i, opt in enumerate(options):
            if opt.strip():
                Option.objects.create(
                    question=question,
                    option_text=opt.strip(),
                    is_correct=(str(i) == correct_index),
                )

        messages.success(request, "Question added successfully.")
        return redirect("questions-add")

    return render(request, "Cpanel/question.html", {
        "url": "questions-add",
        "id": "",
        "question": None,
        "options": [],
    })


@login_required(login_url='Login')
def view_questions(request):
    questions = Question.objects.all().order_by("category", "id")
    return render(request, "Cpanel/view_questions.html", {"questions": questions})


@login_required(login_url='Login')
def edit_question(request, pk):
    question = get_object_or_404(Question, pk=pk)
    options = list(question.options.all())

    if request.method == "POST":
        question.question_text = request.POST.get("question_text", "").strip()
        question.category = request.POST.get("category", "").strip()
        question.explanation = request.POST.get("explanation", "").strip()
        question.section_ref = request.POST.get("section_ref", "").strip()
        question.difficulty = request.POST.get("difficulty", "basic")
        question.is_active = bool(request.POST.get("is_active"))
        question.save()

        option_texts = request.POST.getlist("options[]")
        correct_index = request.POST.get("correct_option")

        for i, opt in enumerate(options):
            if i < len(option_texts):
                opt.option_text = option_texts[i].strip()
                opt.is_correct = (str(i) == correct_index)
                opt.save()

        messages.success(request, "Question updated successfully.")
        return redirect("view-questions")

    return render(request, "Cpanel/question.html", {
        "question": question,
        "options": options,
        "url": "questions-edit",
        "id": question.id,
    })


@login_required(login_url='Login')
def delete_question(request, pk):
    question = get_object_or_404(Question, pk=pk)
    question.delete()
    messages.success(request, "Question deleted successfully.")
    return redirect("questions-list")


# ─────────────────────────────────────────────────────────────
# SEO / UTILITY
# ─────────────────────────────────────────────────────────────

from django.views.decorators.cache import cache_page

@cache_page(60 * 60 * 24)
def robots_txt(request):
    """Serve robots.txt — add to urls.py: path('robots.txt', views.robots_txt)"""
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /Cpanel/",
        "Disallow: /admin/",
        "Disallow: /Login/",
        f"Sitemap: https://www.taxbuddyumair.com/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def custom_404(request, exception=None):
    """Custom 404 page. Register in urls.py: handler404 = 'yourapp.views.custom_404'"""
    return render(request, '404.html', status=404)


def custom_500(request):
    """Custom 500 page. Register in urls.py: handler500 = 'yourapp.views.custom_500'"""
    return render(request, '500.html', status=500)