from datetime import timedelta
from decimal import Decimal
import random
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

def staff_required(view_func):
    """Decorator: requires user to be logged in AND is_staff=True."""
    @login_required(login_url='Login')
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden(
                '<h2 style="font-family:sans-serif;text-align:center;margin-top:100px;color:#0A2647">'
                '403 — Access Denied</h2>'
                '<p style="text-align:center;color:#666">You do not have permission to access this page.</p>'
                '<p style="text-align:center"><a href="/" style="color:#0D9E72">← Back to Home</a></p>'
            )
        return view_func(request, *args, **kwargs)
    return wrapped


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
    SuperTax4CRate, Category, Tag, WithholdingTaxRate
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

        # 3 random income tax blogs
        income_tax_blogs = list(Blog.objects.filter(
            status='published',
            is_deleted=False,
            type='income_tax'
        ).order_by('?')[:3])

        # 3 random sales tax blogs
        sales_tax_blogs = list(Blog.objects.filter(
            status='published',
            is_deleted=False,
            type='sales_tax'
        ).order_by('?')[:3])

        # Combined — 6 blogs for homepage (3 income + 3 sales)
        latest_blogs = income_tax_blogs + sales_tax_blogs
        random.shuffle(latest_blogs)

        all_blogs = Blog.objects.filter(
            status='published',
            is_deleted=False
        ).order_by('-created_at')

        # FAQs — DB first, fallback to default rates FAQs
        try:
            from .models import FAQ
            faqs = FAQ.objects.filter(is_active=True).order_by('category', 'order')
        except Exception:
            faqs = []

        default_faqs = [
            (
                "What is the advance tax rate on property sale for filers in 2025-26?",
                "Under Section 236C, filers pay 4.5%, late filers pay 7.5%, and non-filers pay 11.5% advance tax on the sale of immovable property."
            ),
            (
                "What is the advance tax rate on property purchase for filers in 2025-26?",
                "Under Section 236K, filers pay 1.5%, late filers pay 4.5%, and non-filers pay 10.5% advance tax on the purchase of immovable property."
            ),
            (
                "What is the withholding tax rate on bank profit (Section 151)?",
                "Under Section 151, filers pay 20% and non-filers pay 40% withholding tax on profit on debt, including bank savings accounts and term deposits."
            ),
            (
                "What is the withholding tax rate on dividends (Section 150)?",
                "Under Section 150, filers pay 15% and non-filers pay 30% withholding tax on dividend income from companies and mutual funds."
            ),
            (
                "What are the salary income tax slabs for 2025-26?",
                "For tax year 2025-26: Up to Rs.600,000 = 0%, Rs.600,001-1,200,000 = 1%, Rs.1,200,001-2,200,000 = Rs.6,000 + 11%, Rs.2,200,001-3,200,000 = Rs.116,000 + 23%, Rs.3,200,001-4,100,000 = Rs.346,000 + 30%, Above Rs.4,100,000 = Rs.616,000 + 35%."
            ),
            (
                "What is the advance tax rate on international card payments (Section 236Y)?",
                "Under Section 236Y, filers pay 5% and non-filers pay 10% advance tax on international payments made through Pakistani credit, debit, or prepaid cards."
            ),
            (
                "What is the withholding tax rate for goods and services (Section 153)?",
                "Under Section 153, for supply of goods: filers pay 4%, non-filers pay 8%. For services: filers pay 8%, non-filers pay 16%. For contracts: filers pay 7%, non-filers pay 14%."
            ),
            (
                "What is the advance tax on cash withdrawal (Section 231A)?",
                "Under Section 231A, filers pay 0% (completely exempt) while non-filers pay 0.6% on cash withdrawals exceeding Rs.50,000 per day from a bank."
            ),
            (
                "What is the standard GST rate in Pakistan under Sales Tax Act 1990?",
                "The standard General Sales Tax (GST) rate in Pakistan is 18% under Section 3 of the Sales Tax Act, 1990. Zero-rated supplies (exports) are taxed at 0%, and exempt supplies listed in the Sixth Schedule carry no GST."
            ),
            (
                "How do I check my ATL (Active Taxpayer List) status?",
                "You can check your ATL status by visiting FBR's website at www.fbr.gov.pk or by sending your CNIC number (without dashes) as an SMS to 9966. The ATL is updated every Monday."
            ),
        ]

        return render(request, 'index.html', {
            'result': all_blogs,
            'latest_blogs': latest_blogs,
            'preview_questions': preview_questions,
            'faqs': faqs,
            'default_faqs': default_faqs,
        })
    except Exception as e:
        return HttpResponse(str(e))


def Login(request):
    try:
        # Already logged in staff — redirect to dashboard
        if request.user.is_authenticated and request.user.is_staff:
            return redirect('Dashboard')

        if request.method == 'POST':
            username = request.POST.get('username', '').strip()
            pwd = request.POST.get('password', '')
            user = authenticate(request, username=username, password=pwd)
            if user:
                if not user.is_staff:
                    messages.error(request, "You do not have admin access.")
                    return render(request, 'Login.html')
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
        # No slug = show all published blogs
        if not slug:
            blogs = Blog.objects.filter(
                status='published',
                is_deleted=False
            ).order_by('-created_at')
            paginator = Paginator(blogs, 12)
            page_obj = paginator.get_page(request.GET.get('page'))
            return render(request, "clone.html", {
                "blogs": page_obj,
                "page_obj": page_obj,
                "category_name": "All Posts",
            })

        category_name = slug.replace('-', ' ')

        blogs = Blog.objects.filter(
            category__iexact=category_name,
            status='published',
            is_deleted=False
        ).order_by('-created_at')

        # Fallback: filter by Blog.type field
        if not blogs.exists():
            type_map = {
                'income-tax': 'income_tax',
                'sales-tax':  'sales_tax',
                'freelancer': 'freelancer',
                'general':    'general',
            }
            blog_type = type_map.get(slug)
            if blog_type:
                blogs = Blog.objects.filter(
                    type=blog_type,
                    status='published',
                    is_deleted=False
                ).order_by('-created_at')

        if not blogs.exists():
            raise Http404("No blogs found for this category")

        paginator = Paginator(blogs, 12)
        page_obj = paginator.get_page(request.GET.get('page'))
        return render(request, "clone.html", {
            "blogs": page_obj,
            "page_obj": page_obj,
            "category_name": category_name.title(),
        })

    except Http404:
        raise
    except Exception as e:
        return HttpResponse('Exception at View Blogs Page: ' + str(e))



def blog_index(request):
    """Blog index — shows all published posts, no category filter."""
    try:
        blogs = Blog.objects.filter(
            status='published',
            is_deleted=False
        ).order_by('-created_at')
        return render(request, "clone.html", {"blogs": blogs, "category_name": "All Posts"})
    except Exception as e:
        return HttpResponse('Exception at Blog Index: ' + str(e))

@staff_required
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
            # Honeypot — bots fill this hidden field
            if request.POST.get('website_url', ''):
                return redirect('/')

            token = request.POST.get('g-recaptcha-response', '')
            recaptcha_secret = getattr(settings, 'RECAPTCHA_SECRET_KEY', '')

            if recaptcha_secret and token:
                try:
                    r = requests.post(
                        'https://www.google.com/recaptcha/api/siteverify',
                        data={'secret': recaptcha_secret, 'response': token},
                        timeout=5
                    )
                    result = r.json()

                    if not result.get('success'):
                        messages.error(request, "Captcha verification failed. Please try again.")
                        return redirect('/#contact')

                    # v3 has score, v2 does not — handle both
                    score = result.get('score')
                    if score is not None and score < 0.3:
                        messages.error(request, "Captcha verification failed. Please try again.")
                        return redirect('/#contact')

                except requests.RequestException:
                    pass  # reCAPTCHA API down — allow form

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





def legacy_blog_redirect(request, slug):
    """Redirect old blog URLs /<slug>/ to new /articles/<slug>/"""
    from django.shortcuts import redirect
    return redirect('BlogDetails', slug=slug, permanent=True)

def disclaimer(request):
    try:
        return render(request, 'partials/disclaimer.html')
    except Exception as e:
        return HttpResponse("Exception: " + str(e))

def income_tax_guides(request):
    try:
        from .models import TaxGuide
        guides = TaxGuide.objects.filter(
            category='income_tax',
            is_active=True
        ).order_by('order')
        return render(request, 'income-tax-guides.html', {
            'guides': guides,
            'meta_description': 'Complete income tax guides for Pakistan — salary tax, property tax, business income, withholding tax and filer vs non-filer rates. Updated per Finance Act 2025.',
        })
    except Exception as e:
        return HttpResponse(str(e))


def sales_tax_guides(request):
    try:
        from .models import TaxGuide
        guides = TaxGuide.objects.filter(
            category='sales_tax',
            is_active=True
        ).order_by('order')
        return render(request, 'sales-tax-guides.html', {
            'guides': guides,
            'meta_description': 'Complete sales tax guides for Pakistan — GST 18%, zero-rated goods, exempt goods, input tax, output tax, Tier-1 retailers and SRO 350/2024. Updated per Sales Tax Act 1990.',
        })
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
            "meta_description": f"Income tax rates Pakistan {selected_year} — salary slabs, business tax, AOP and company rates. FBR notified slabs updated per Finance Act 2025.",
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
        active_section = request.GET.get('section', 'property')
        tax_year       = request.GET.get('year', '2025-2026')

        all_rates = WithholdingTaxRate.objects.filter(
            is_active=True, tax_year=tax_year
        )

        categories = {
            'property': all_rates.filter(category='property').order_by('order'),
            'banking':  all_rates.filter(category='banking').order_by('order'),
            'salary':   all_rates.filter(category='salary').order_by('order'),
            'business': all_rates.filter(category='business').order_by('order'),
            'advance':  all_rates.filter(category='advance').order_by('order'),
            'other':    all_rates.filter(category='other').order_by('order'),
        }

        categories_meta = [
            ('property', 'Property Sale & Purchase',   'WHT on sale/purchase of immovable property under Section 236C/236K.'),
            ('banking',  'Banking & Finance',           'WHT on cash withdrawals, profit on debt, dividends and foreign card payments.'),
            ('salary',   'Salary & Employment',         'Monthly salary deduction under Section 149 and vehicle registration under 231B.'),
            ('business', 'Business & Contracts',        'WHT on payments for goods, services and contracts under Section 153.'),
            ('advance',  'Advance Tax',                 'Advance tax collected at source on various transactions.'),
            ('other',    'Other Payments',              'WHT on prizes, imports, educational remittances and more.'),
        ]

        return render(request, 'partials/withholding-tax-rates.html', {
            'active_section':  active_section,
            'categories':      categories,
            'categories_meta': categories_meta,
            'tax_year':        tax_year,
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

    years = list(TaxBracket.objects.values_list("year", flat=True).distinct().order_by("-year"))
    context = {'content': content, 'title': 'AOP', 'url': '/AOPCalculator', 'years': years}

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

    years = list(TaxBracket.objects.values_list("year", flat=True).distinct().order_by("-year"))
    context = {'content': content, 'title': 'Business Individual', 'url': '/BusinessCalculator', 'years': years}

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

    years = list(TaxBracket.objects.values_list("year", flat=True).distinct().order_by("-year"))
    context = {'content': content, 'title': 'Salary Individual', 'url': '/SalaryCalculator', 'years': years}

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
                return render(request, 'partials/property_rent.html', {
            'meta_description': 'Free AOP income tax calculator Pakistan 2025-26. Calculate tax liability for Association of Persons, partnership firms and joint ventures based on FBR notified slabs.',
            'meta_description': 'Free business income tax calculator Pakistan 2025-26. Calculate net business tax for sole proprietors, freelancers and traders based on FBR notified slabs.',
            'meta_description': 'Free salary income tax calculator Pakistan 2025-26. Calculate monthly and yearly salary tax based on FBR notified slabs. Compare tax across multiple tax years.','years': list(TaxBracket.objects.values_list("year", flat=True).distinct().order_by("-year"))})

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
                'years': list(TaxBracket.objects.values_list('year', flat=True).distinct().order_by('-year')),
            })
            return render(request, 'partials/property_rent.html', context)

        return render(request, 'partials/property_rent.html', {'years': list(TaxBracket.objects.values_list('year', flat=True).distinct().order_by('-year'))})

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



@staff_required
def manage_wht_rates(request):
    try:
        active_cat = request.GET.get('cat', 'all')
        tax_year   = request.GET.get('year', '2025-2026')
        rates = WithholdingTaxRate.objects.all().order_by('category', 'order')
        if active_cat and active_cat != 'all':
            rates = rates.filter(category=active_cat)
        rates = rates.filter(tax_year=tax_year)

        # Category stats for dashboard
        from django.db.models import Count
        cat_counts = WithholdingTaxRate.objects.filter(
            tax_year=tax_year, is_active=True
        ).values('category').annotate(count=Count('id'))
        cat_map = {c['category']: c['count'] for c in cat_counts}
        categories_stats = [
            ('property', {'name': '🏠 Property', 'count': cat_map.get('property', 0)}),
            ('banking',  {'name': '🏦 Banking',  'count': cat_map.get('banking',  0)}),
            ('salary',   {'name': '💼 Salary',   'count': cat_map.get('salary',   0)}),
            ('business', {'name': '🏢 Business', 'count': cat_map.get('business', 0)}),
            ('advance',  {'name': '📊 Advance',  'count': cat_map.get('advance',  0)}),
            ('other',    {'name': '📋 Other',    'count': cat_map.get('other',    0)}),
        ]

        return render(request, 'Cpanel/manage_wht.html', {
            'rates': rates,
            'active_cat': active_cat,
            'tax_year': tax_year,
            'categories_stats': categories_stats,
        })
    except Exception as e:
        return HttpResponse(str(e))


def add_wht_rate(request):
    try:
        if request.method == 'POST':
            WithholdingTaxRate.objects.create(
                category       = request.POST.get('category'),
                section        = request.POST.get('section', '').strip(),
                description    = request.POST.get('description', '').strip(),
                filer_rate     = request.POST.get('filer_rate', '').strip(),
                non_filer_rate=request.POST.get('non_filer_rate', '').strip(),
                late_filer_rate = request.POST.get('late_filer_rate', '').strip(),
                who_deducts    = request.POST.get('who_deducts', '').strip(),
                threshold      = request.POST.get('threshold', '').strip(),
                notes          = request.POST.get('notes', '').strip(),
                order          = int(request.POST.get('order', 0) or 0),
                is_active      = bool(request.POST.get('is_active')),
                tax_year       = request.POST.get('tax_year', '2025-2026'),
            )
            messages.success(request, 'Rate added successfully!')
            return redirect('manage_wht_rates')
        return render(request, 'Cpanel/add_wht_rate.html', {'rate': None})
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return render(request, 'Cpanel/add_wht_rate.html', {'rate': None})


@staff_required
def edit_wht_rate(request, pk):
    try:
        rate = get_object_or_404(WithholdingTaxRate, pk=pk)
        if request.method == 'POST':
            rate.category       = request.POST.get('category')
            rate.section        = request.POST.get('section', '').strip()
            rate.description    = request.POST.get('description', '').strip()
            rate.filer_rate     = request.POST.get('filer_rate', '').strip()
            rate.late_filer_rate = request.POST.get('late_filer_rate', '').strip()
            rate.non_filer_rate = request.POST.get('non_filer_rate', '').strip()
            rate.who_deducts    = request.POST.get('who_deducts', '').strip()
            rate.threshold      = request.POST.get('threshold', '').strip()
            rate.notes          = request.POST.get('notes', '').strip()
            rate.order          = int(request.POST.get('order', 0) or 0)
            rate.is_active      = bool(request.POST.get('is_active'))
            rate.tax_year       = request.POST.get('tax_year', '2025-2026')
            rate.save()
            messages.success(request, 'Rate updated successfully!')
            return redirect('manage_wht_rates')
        return render(request, 'Cpanel/add_wht_rate.html', {'rate': rate})
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('manage_wht_rates')


@staff_required
def delete_wht_rate(request, pk):
    try:
        rate = get_object_or_404(WithholdingTaxRate, pk=pk)
        rate.delete()
        messages.success(request, 'Rate deleted.')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    return redirect('manage_wht_rates')

def question_list(request, category_slug=None):
    try:
        print(category_slug)
        questions = Question.objects.prefetch_related("options").order_by("id")
        print(questions)
        selected_category = None
        category_not_found = False

        if category_slug:
            all_categories = (
                Question.objects
                .exclude(category__isnull=True)
                .exclude(category='')
                .values_list("category", flat=True)
                .distinct()
            )

            print(all_categories)
            # Exact slug match first
            for c in all_categories:
                if slugify(c.strip()) == category_slug:
                    selected_category = c.strip()
                    break

            if selected_category:
                questions = questions.filter(category=selected_category)
            else:
                # Partial match fallback
                slug_words = category_slug.replace('-', ' ').lower()
                for c in all_categories:
                    if slug_words in c.lower() or c.lower() in slug_words:
                        selected_category = c.strip()
                        questions = questions.filter(category=selected_category)
                        break
                else:
                    # No match — show all questions, flag for template
                    category_not_found = True

        paginator = Paginator(questions, 10)
        page_obj = paginator.get_page(request.GET.get("page"))

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

        return render(request, "partials/mcq-layout.html", {
            "meta_description": "Practice free income tax and sales tax MCQs for Pakistan. Test your knowledge of ITO 2001, Sales Tax Act 1990, FBR procedures and withholding tax sections. Updated 2025-26.",
            "page_obj": page_obj,
            "categories": categories,
            "selected_category": selected_category,
            "seo_category": selected_category,
            "category_slug": category_slug,
            "category_not_found": category_not_found,
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

@staff_required
def Dashboard(request):
    try:
        total_wht_rates = WithholdingTaxRate.objects.filter(is_active=True).count()
        return render(request, 'Cpanel/Dashboard.html')
    except Exception as e:
        return HttpResponse(str(e))


@staff_required
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

    return render(request, "Cpanel/AddEditBlog.html", {
            'meta_description': 'Free Super Tax calculator Pakistan 2025-26. Calculate Section 4C super tax for companies and individuals with income above Rs. 150 million.',"blog": blog})


@staff_required
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


@staff_required
def ManageBlogs(request):
    try:
        result = Blog.objects.filter(is_deleted=False).order_by('-id')
        return render(request, 'Cpanel/ManageBlogs.html', {'result': result})
    except Exception as e:
        return HttpResponse('Exception at Manage Blog Page: ' + str(e))


@staff_required
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


@staff_required
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


@staff_required
def view_questions(request):
    questions = Question.objects.all().order_by("category", "id")
    return render(request, "Cpanel/view_questions.html", {"questions": questions})


@staff_required
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


@staff_required
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


# ─── FAQ MANAGEMENT ───────────────────────────────────────────────────────────

@staff_required
def manage_faqs(request):
    from .models import FAQ
    faqs = FAQ.objects.all().order_by('order', 'id')
    return render(request, 'Cpanel/manage_faqs.html', {'faqs': faqs})


@staff_required
def add_faq(request):
    from .models import FAQ
    if request.method == 'POST':
        question = request.POST.get('question', '').strip()
        answer   = request.POST.get('answer', '').strip()
        order    = request.POST.get('order', 0)
        is_active = request.POST.get('is_active') == '1'
        category = request.POST.get('category', 'general')
        if question and answer:
            FAQ.objects.create(
                question=question,
                answer=answer,
                category=category,
                order=int(order),
                is_active=is_active,
            )
            messages.success(request, 'FAQ added successfully.')
            return redirect('manage_faqs')
        else:
            messages.error(request, 'Question and Answer are required.')
    return render(request, 'Cpanel/add_faq.html', {'faq': None})


@staff_required
def edit_faq(request, pk):
    from .models import FAQ
    faq = get_object_or_404(FAQ, pk=pk)
    if request.method == 'POST':
        faq.question  = request.POST.get('question', '').strip()
        faq.answer    = request.POST.get('answer', '').strip()
        faq.category  = request.POST.get('category', 'general')
        faq.order     = int(request.POST.get('order', 0))
        faq.is_active = request.POST.get('is_active') == '1'
        faq.save()
        messages.success(request, 'FAQ updated successfully.')
        return redirect('manage_faqs')
    return render(request, 'Cpanel/add_faq.html', {'faq': faq})


@staff_required
def delete_faq(request, pk):
    from .models import FAQ
    faq = get_object_or_404(FAQ, pk=pk)
    faq.delete()
    messages.success(request, 'FAQ deleted.')
    return redirect('manage_faqs')


# ─── TAX GUIDE MANAGEMENT ─────────────────────────────────────────────────────

@staff_required
def manage_guides(request):
    from .models import TaxGuide
    income_guides = TaxGuide.objects.filter(category='income_tax').order_by('order')
    sales_guides  = TaxGuide.objects.filter(category='sales_tax').order_by('order')
    return render(request, 'Cpanel/manage_guides.html', {
        'income_guides': income_guides,
        'sales_guides': sales_guides,
    })


@staff_required
def add_guide(request):
    from .models import TaxGuide, Blog
    blogs = Blog.objects.filter(status='published', is_deleted=False).order_by('title')
    if request.method == 'POST':
        title       = request.POST.get('title', '').strip()
        summary     = request.POST.get('summary', '').strip()
        category    = request.POST.get('category', 'income_tax')
        order       = int(request.POST.get('order', 0))
        is_active   = request.POST.get('is_active') == '1'
        related_id  = request.POST.get('related_blog', '')
        if title and summary:
            guide = TaxGuide.objects.create(
                title=title,
                summary=summary,
                category=category,
                order=order,
                is_active=is_active,
            )
            if related_id:
                try:
                    guide.related_blog = Blog.objects.get(pk=related_id)
                    guide.save()
                except Blog.DoesNotExist:
                    pass
            messages.success(request, 'Guide added successfully.')
            return redirect('manage_guides')
        else:
            messages.error(request, 'Title and Summary are required.')
    return render(request, 'Cpanel/add_guide.html', {'guide': None, 'blogs': blogs})


@staff_required
def edit_guide(request, pk):
    from .models import TaxGuide, Blog
    guide = get_object_or_404(TaxGuide, pk=pk)
    blogs = Blog.objects.filter(status='published', is_deleted=False).order_by('title')
    if request.method == 'POST':
        guide.title     = request.POST.get('title', '').strip()
        guide.summary   = request.POST.get('summary', '').strip()
        guide.category  = request.POST.get('category', 'income_tax')
        guide.order     = int(request.POST.get('order', 0))
        guide.is_active = request.POST.get('is_active') == '1'
        related_id      = request.POST.get('related_blog', '')
        if related_id:
            try:
                guide.related_blog = Blog.objects.get(pk=related_id)
            except Blog.DoesNotExist:
                guide.related_blog = None
        else:
            guide.related_blog = None
        guide.save()
        messages.success(request, 'Guide updated successfully.')
        return redirect('manage_guides')
    return render(request, 'Cpanel/add_guide.html', {'guide': guide, 'blogs': blogs})


@staff_required
def delete_guide(request, pk):
    from .models import TaxGuide
    guide = get_object_or_404(TaxGuide, pk=pk)
    guide.delete()
    messages.success(request, 'Guide deleted.')
    return redirect('manage_guides')


# ── Paste this entire block at the END of views.py ────────────

import json
import requests as http_requests

@csrf_exempt
def search_knowledge_base(query):
    """RAG — Search aap ke DB se relevant content"""
    from .models import Blog, WithholdingTaxRate, TaxGuide, FAQ
    from django.db.models import Q
    results = []
    query_lower = query.lower()

    # ── 1. WHT Rates — exact match ──────────────────────────
    rates = WithholdingTaxRate.objects.filter(
        is_active=True, tax_year='2025-2026'
    ).filter(
        Q(section__icontains=query) |
        Q(description__icontains=query)
    )[:5]
    for r in rates:
        results.append(
            f"[WHT Rate] {r.section} — {r.description} | "
            f"Filer: {r.filer_rate} | Late Filer: {r.late_filer_rate or 'Same'} | "
            f"Non-Filer: {r.non_filer_rate} | Who deducts: {r.who_deducts}"
        )

    # ── 2. MCQs ──────────────────────────────────────────────
    from .models import Question, Option
    questions = Question.objects.filter(is_active=True).filter(
        Q(question_text__icontains=query) |
        Q(explanation__icontains=query) |
        Q(section_ref__icontains=query)
    )[:4]
    for q in questions:
        correct = q.options.filter(is_correct=True).first()
        correct_text = correct.option_text if correct else ''
        mcq_text = "[MCQ] Q: " + str(q.question_text)
        if correct_text:
            mcq_text += " | Correct Answer: " + correct_text
        if q.explanation:
            mcq_text += " | Explanation: " + str(q.explanation[:300])
        if q.section_ref:
            mcq_text += " | Section: " + str(q.section_ref)
        results.append(mcq_text)

    # ── 3. FAQs ──────────────────────────────────────────────
    faqs = FAQ.objects.filter(is_active=True).filter(
        Q(question__icontains=query) |
        Q(answer__icontains=query)
    )[:3]
    for f in faqs:
        results.append("[FAQ] Q: " + str(f.question) + "\nA: " + str(f.answer))

    # ── 3. Tax Guides ────────────────────────────────────────
    guides = TaxGuide.objects.filter(is_active=True).filter(
        Q(title__icontains=query) |
        Q(summary__icontains=query)
    )[:2]
    for g in guides:
        import re
        clean = re.sub(r'<[^>]+>', '', g.summary)
        results.append(f"[Guide] {g.title}: {clean[:600]}")

    # ── 4. Blog posts ────────────────────────────────────────
    blogs = Blog.objects.filter(
        status='published', is_deleted=False
    ).filter(
        Q(title__icontains=query) |
        Q(content__icontains=query) |
        Q(meta_description__icontains=query)
    )[:2]
    for b in blogs:
        import re
        clean = re.sub(r'<[^>]+>', '', b.content)
        results.append("[Blog] " + b.title + ": " + clean[:800])

    # ── 5. MCQs ──────────────────────────────────────────────
    from .models import Question, Option
    questions = Question.objects.filter(is_active=True).filter(
        Q(question_text__icontains=query) |
        Q(explanation__icontains=query) |
        Q(section_ref__icontains=query) |
        Q(category__icontains=query)
    )[:5]
    for q in questions:
        correct = q.options.filter(is_correct=True).first()
        correct_text = correct.option_text if correct else "N/A"
        mcq_entry = "[MCQ] Q: " + q.question_text
        mcq_entry += " | Correct Answer: " + correct_text
        if q.explanation:
            mcq_entry += " | Explanation: " + q.explanation[:200]
        if q.section_ref:
            mcq_entry += " | Section: " + q.section_ref
        results.append(mcq_entry)

    return results


def ai_chat(request):
    if request.method != 'POST':
        return JsonResponse({'reply': 'Invalid request.'}, status=405)
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        history = data.get('history', [])

        if not user_message:
            return JsonResponse({'reply': 'Koi sawaal poochein.'})

        gemini_key = getattr(settings, 'GEMINI_API_KEY', '').strip()
        # Fallback: check environment variable directly
        if not gemini_key:
            import os
            gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
        if not gemini_key:
            return JsonResponse({'reply': 'AI service abhi setup ho rahi hai. Settings mein GEMINI_API_KEY add karein.'})

        # ── RAG — DB se relevant content fetch karo ─────────
        kb_results = search_knowledge_base(user_message)
        knowledge_context = ""
        if kb_results:
            knowledge_context = "\n\nRELEVANT TAXBUDDY DATABASE CONTENT:\n" + "\n\n".join(kb_results)

        # ── System Prompt ────────────────────────────────────
        system_prompt = f"""You are TaxBuddy AI — an expert Pakistan tax educator assistant for taxbuddyumair.com.

STRICT RULES:
1. Answer ONLY Pakistan tax questions (ITO 2001, Sales Tax Act 1990, FBR rules)
2. Reply in SAME language as user (Urdu Roman or English)
3. ALWAYS prefer the database content below over your own knowledge
4. If database has the answer — use it EXACTLY, do not guess
5. If database does NOT have the answer — say "Please verify from FBR portal: fbr.gov.pk"
6. Keep answers concise — 3-5 sentences max
7. Always cite correct Section numbers
8. NEVER give wrong section numbers — if unsure, say "verify from FBR"

CORRECT SECTIONS (ITO 2001):
- Section 114: Who must file return
- Section 118: Due date 30 September
- Section 149: Salary withholding
- Section 150: Dividends (15%/30%)
- Section 151: Bank profit (20%/40%)
- Section 153: Goods/Services/Contracts WHT
- Section 155: Rent
- Section 236C: Property sale advance tax
- Section 236K: Property purchase advance tax
- Section 7B: Profit on debt
- Section 7E: Deemed income from property
- Section 4C: Super Tax
- Section 182: Penalty for non-filing

KEY RATES 2025-26:
- Salary: 0% upto 600K | 1% upto 1.2M | Rs.6K+11% upto 2.2M | Rs.116K+23% upto 3.2M | Rs.346K+30% upto 4.1M | Rs.616K+35% above
- Property sale 236C: Filer 4.5%, Late Filer 7.5%, Non-Filer 11.5%
- Property purchase 236K: Filer 1.5%, Late Filer 4.5%, Non-Filer 10.5%
- Bank profit 151: Filer 20%, Non-Filer 40%
- Dividends 150: Filer 15%, Non-Filer 30%
- GST: 18% standard, Further Tax 4%
- ATL surcharge: Rs.1,000
- Return deadline: 30 September (Section 118){knowledge_context}"""

        # ── Build messages ───────────────────────────────────
        messages = []
        for msg in history[-6:]:
            role = "model" if msg.get("role") == "assistant" else "user"
            messages.append({"role": role, "parts": [{"text": msg["content"]}]})
        messages.append({"role": "user", "parts": [{"text": user_message}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={gemini_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": messages,
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500}
        }

        # Retry logic — 3 attempts with backoff
        import time
        response = None
        for attempt in range(3):
            response = http_requests.post(url, json=payload, timeout=15)
            if response.status_code == 429:
                if attempt < 2:
                    time.sleep(35)  # wait 35 seconds and retry
                    continue
                else:
                    return JsonResponse({'reply': 'AI abhi bohat busy hai. Thori der baad try karein ya WhatsApp karein: +92 333 248 2742'})
            break

        result = response.json()
        if response.status_code != 200:
            err = result.get('error', {}).get('message', 'Unknown error')
            return JsonResponse({'reply': 'Kuch masla hua. Dobara try karein.'})

        reply = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        if not reply:
            reply = "Maafi chahta hoon, jawab nahi mil saka. Dobara try karein."

        # Return KB source info too
        source = "DB" if kb_results else "General"
        return JsonResponse({'reply': reply, 'source': source})

    except http_requests.Timeout:
        return JsonResponse({'reply': 'Request timeout. Dobara try karein.'})
    except Exception as e:
        return JsonResponse({'reply': f'Error: {str(e)}'})