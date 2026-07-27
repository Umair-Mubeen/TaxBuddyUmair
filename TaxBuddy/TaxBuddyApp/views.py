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
    SuperTax4CRate, Category, Tag, WithholdingTaxRate,WHTRate, TaxGuide, FAQ, Instrument, Subscriber,GlossaryTerm
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

        # WHT Rates for homepage cards — top 6 sections
        wht_sections = ['236C', '236K', '151', '153', '150', '236Y']
        PREFERRED_WHT_YEAR = '2026-2027'
        wht_rates = {}
        for section in wht_sections:
            base = WithholdingTaxRate.objects.filter(
                section__iexact='Section ' + section,
                is_active=True,
                tax_year=PREFERRED_WHT_YEAR,  # strict — only this year
            )
            wht_rates[section] = base.order_by('order').first()  # None if not added yet

        return render(request, 'index.html', {
            'result': all_blogs,
            'latest_blogs': latest_blogs,
            'preview_questions': preview_questions,
            'faqs': faqs,
            'default_faqs': default_faqs,
            'wht_rates': wht_rates,
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
        tax_year       = request.GET.get('year', '2026-2027')

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
    print(years)
    context = {'content': content, 'title': 'Salary Individual', 'url': '/SalaryCalculator', 'years': years}

    if request.method == 'POST':
        income_amount, error = validate_income(request.POST)
        print('income_amount', income_amount)
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
    content = {
        "title": "Property / Rental Income Tax Calculator – Pakistan",
        "badge": "Section 15 · ITO 2001",
        "intro": "Calculate tax on rental income after Section 15A deductions, and compare across tax years.",
        "who": [
            "Individuals earning rental income from property",
            "Landlords with residential or commercial property",
            "Owners letting out buildings or shops",
            "Anyone declaring income from property under Section 15",
        ],
        "how": "Enter gross annual rent, claim allowable Section 15A deductions, and select two tax years.",
        "features": [
            "Net rental income after Section 15A deductions",
            "20% repair allowance applied automatically",
            "Compare rental tax across tax years",
            "Slab-based computation",
        ],
        "example": [
            "Gross annual rent: PKR 1,200,000",
            "Less 20% repair allowance: PKR 240,000",
            "Net taxable rent: PKR 960,000",
        ],
        "notes": [
            "Repair allowance is 1/5 (20%) of rent chargeable to tax — applied automatically",
            "Other Section 15A deductions are optional and require records",
            "Section 155 tax withheld by the tenant is adjustable against final liability",
        ],
    }

    years = list(TaxBracket.objects.values_list("year", flat=True).distinct().order_by("-year"))
    context = {'content': content, 'title': 'Rental Income', 'url': '/PropertyCalculator', 'years': years}

    if request.method == 'POST':
        gross_rent = to_int(request.POST.get('gross_rent', 0))
        if gross_rent <= 0:
            messages.error(request, "Please enter a valid gross rent amount.")
            return render(request, 'partials/property_rent.html', context)

        income_type = request.POST.get('income_type', 'Yearly')
        tax_year_1 = request.POST.get('tax_year_1')
        tax_year_2 = request.POST.get('tax_year_2')
        yearly_rent = gross_rent * 12 if income_type == 'Monthly' else gross_rent

        # ── Section 15A allowable deductions ──
        insurance_premium  = to_int(request.POST.get('insurance_premium'))
        local_taxes        = to_int(request.POST.get('local_taxes'))
        ground_rent        = to_int(request.POST.get('ground_rent'))
        borrowed_interest  = to_int(request.POST.get('borrowed_interest'))
        hbfc_payments      = to_int(request.POST.get('hbfc_payments'))
        mortgage_interest  = to_int(request.POST.get('mortgage_interest'))
        admin_expenses     = to_int(request.POST.get('admin_expenses'))
        legal_expenses     = to_int(request.POST.get('legal_expenses'))
        irrecoverable_rent = to_int(request.POST.get('irrecoverable_rent'))

        # Statutory repair allowance = 1/5 (20%) of rent chargeable.
        # Auto-apply when the user leaves it blank (it is allowed without proof).
        repairs_allowance = to_int(request.POST.get('repairs_allowance'))
        if repairs_allowance <= 0:
            repairs_allowance = round(yearly_rent * 0.20)

        total_deductions = (
            repairs_allowance + insurance_premium + local_taxes +
            ground_rent + borrowed_interest + hbfc_payments +
            mortgage_interest + admin_expenses + legal_expenses +
            irrecoverable_rent
        )
        net_rental_income = max(0, yearly_rent - total_deductions)

        try:
            result_context = FetchResult(tax_year_1, tax_year_2, 'Rental Income', net_rental_income)
            context.update(result_context)
            context.update({
                'income_type': income_type,
                'gross_rent': yearly_rent,
                'repairs_allowance': repairs_allowance,
                'total_deductions': total_deductions,
                'net_income_rental': net_rental_income,
            })
        except Exception:
            messages.error(request, "Could not calculate tax. Please check your inputs.")

    return render(request, 'partials/property_rent.html', context)


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
        tax_year   = request.GET.get('year', '2026-2027')
        rates = WithholdingTaxRate.objects.all().order_by('category', 'order')
        if active_cat and active_cat != 'all':
            rates = rates.filter(category=active_cat)
        rates = rates.filter(tax_year=tax_year)
        return render(request, 'Cpanel/manage_wht.html', {
            'rates': rates, 'active_cat': active_cat, 'tax_year': tax_year,
        })
    except Exception as e:
        return HttpResponse("Exception: " + str(e))


@staff_required
def add_wht_rate(request):
    try:
        if request.method == 'POST':
            WithholdingTaxRate.objects.create(
                category       = request.POST.get('category'),
                section        = request.POST.get('section', '').strip(),
                description    = request.POST.get('description', '').strip(),
                filer_rate     = request.POST.get('filer_rate', '').strip(),
                late_filer_rate=request.POST.get('late_filer_rate', '').strip(),
                non_filer_rate = request.POST.get('non_filer_rate', '').strip(),
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
    from django.utils.text import slugify
    blogs = Blog.objects.filter(status='published', is_deleted=False).order_by('title')
    if request.method == 'POST':
        title      = request.POST.get('title', '').strip()
        summary    = request.POST.get('summary', '').strip()
        category   = request.POST.get('category', 'income_tax')
        is_active  = request.POST.get('is_active') == '1'
        related_id = request.POST.get('related_blog', '')
        try:
            order = int(request.POST.get('order', 0))
        except (ValueError, TypeError):
            order = 0
        if title and summary:
            base_slug = slugify(title)
            slug = base_slug
            counter = 1
            while TaxGuide.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            guide = TaxGuide.objects.create(
                title=title,
                slug=slug,
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
            messages.success(request, f'Guide "{title}" added successfully.')
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
def ai_chat(request):
    if request.method != 'POST':
        return JsonResponse({'reply': 'Invalid request.'}, status=405)
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        history = data.get('history', [])

        if not user_message:
            return JsonResponse({'reply': 'Koi sawaal poochein.'})

        gemini_key = 'AIzaSyDhG5duRuW9mVELrvnAurne8PVysQYewM8'

        if not gemini_key:
            return JsonResponse({'reply': 'AI service abhi setup ho rahi hai. Thori der mein try karein.'})

        system_prompt = """You are an expert Pakistan tax educator assistant for TaxBuddy Umair (taxbuddyumair.com).
Answer ONLY Pakistan tax questions (income tax, sales tax, property tax, FBR, ITO 2001).
Reply in same language as user (Urdu Roman or English). Keep answers concise — 3-5 sentences.
Always mention relevant section numbers. Current tax year is 2025-26.

KEY RATES:
- Salary: 0% upto 600K, 1% upto 1.2M, 11%+6K upto 2.2M, 23%+116K upto 3.2M, 30%+346K upto 4.1M, 35%+616K above
- Property sale 236C: Filer 4.5%, Non-Filer 11.5%
- Property purchase 236K: Filer 1.5%, Non-Filer 10.5%
- Bank profit 151: Filer 20%, Non-Filer 40%
- GST: 18% standard rate
End response with: Aur koi sawaal? / Any other question?"""

        messages = []
        for msg in history[-6:]:
            role = "model" if msg.get("role") == "assistant" else "user"
            messages.append({"role": role, "parts": [{"text": msg["content"]}]})
        messages.append({"role": "user", "parts": [{"text": user_message}]})

        # url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
        # url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={gemini_key}"

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": messages,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 400}
        }

        response = http_requests.post(url, json=payload, timeout=15)
        result = response.json()

        # Debug — log response if error
        if response.status_code != 200:
            import logging
            logging.error(f"Gemini error: {result}")
            return JsonResponse({'reply': f'API error: {result.get("error", {}).get("message", "Unknown error")}'})

        reply = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        if not reply:
            reply = "Maafi chahta hoon, jawab nahi mil saka. Dobara try karein."

        return JsonResponse({'reply': reply})

    except http_requests.Timeout:
        return JsonResponse({'reply': 'Request timeout. Dobara try karein.'})
    except Exception as e:
        return JsonResponse({'reply': f'Error: {str(e)}'})



# ── NEW PAGES ─────────────────────────────────────────────────
def about_us(request):
    return render(request, 'about-us.html')


def atl_check(request):
    try:
        from .models import ATLRecord
        atl_total   = ATLRecord.objects.count()
        atl_updated = ATLRecord.objects.order_by('-updated_at').first()
    except Exception:
        atl_total   = 0
        atl_updated = None
    return render(request, 'atl-check.html', {
        'atl_total':   atl_total,
        'atl_updated': atl_updated,
    })


def atl_search_api(request):
    from django.http import JsonResponse
    try:
        from .models import ATLRecord
        query = request.GET.get('q', '').strip().replace('-', '').replace(' ', '')

        if not query or len(query) < 4:
            return JsonResponse({'found': False, 'error': 'Enter at least 4 digits'})

        record = None

        # 1. Exact match
        record = ATLRecord.objects.filter(ntn=query).first()

        # 2. Zero-padded — try 7,8,9,10 digit padding
        if not record:
            for pad in [7, 8, 9, 10]:
                padded = query.zfill(pad)
                record = ATLRecord.objects.filter(ntn=padded).first()
                if record:
                    break

        # 3. Strip leading zeros
        if not record:
            stripped = query.lstrip('0')
            if stripped:
                record = ATLRecord.objects.filter(ntn=stripped).first()

        # 4. Contains
        if not record:
            record = ATLRecord.objects.filter(ntn__icontains=query).first()

        if record:
            # Safe atl_type — field may not exist in old DB
            try:
                atl_type_display = record.get_atl_type_display()
            except Exception:
                atl_type_display = 'Income Tax'

            return JsonResponse({
                'found':    True,
                'ntn':      record.ntn,
                'name':     record.business_name or record.name or 'N/A',
                'tax_year': record.tax_year,
                'atl_type': atl_type_display,
            })

        return JsonResponse({
            'found':   False,
            'message': f'No record found for {query}. May be Non-Filer or ATL not updated yet.',
        })
    except Exception as e:
        return JsonResponse({'found': False, 'error': str(e)})


def tax_calendar(request):
    return render(request, 'tax-calendar.html')


def fbr_iris_guide(request):
    return render(request, 'fbr-iris-guide.html')


def redirect_to_mcqs(request, **kwargs):
    from django.http import HttpResponsePermanentRedirect
    return HttpResponsePermanentRedirect('/income-tax-mcqs-pakistan/')

# ── NEW PAGES ─────────────────────────────────────────────────
def about_us(request):
    return render(request, 'about-us.html')


def atl_check(request):
    try:
        from .models import ATLRecord
        atl_total   = ATLRecord.objects.count()
        atl_updated = ATLRecord.objects.order_by('-updated_at').first()
    except Exception:
        atl_total   = 0
        atl_updated = None
    return render(request, 'atl-check.html', {
        'atl_total':   atl_total,
        'atl_updated': atl_updated,
    })


def atl_search_api(request):
    from django.http import JsonResponse
    try:
        from .models import ATLRecord
        query = request.GET.get('q', '').strip().replace('-', '').replace(' ', '')
        if not query or len(query) < 4:
            return JsonResponse({'found': False, 'error': 'Enter at least 4 digits'})
        record = ATLRecord.objects.filter(ntn=query).first()
        if not record:
            for pad in [7, 8, 9, 10]:
                r = ATLRecord.objects.filter(ntn=query.zfill(pad)).first()
                if r:
                    record = r
                    break
        if not record:
            stripped = query.lstrip('0')
            if stripped:
                record = ATLRecord.objects.filter(ntn=stripped).first()
        if not record:
            record = ATLRecord.objects.filter(ntn__icontains=query).first()
        if record:
            try:
                atl_type_display = record.get_atl_type_display()
            except Exception:
                atl_type_display = 'Income Tax'
            return JsonResponse({
                'found':    True,
                'ntn':      record.ntn,
                'name':     record.business_name or record.name or 'N/A',
                'tax_year': record.tax_year,
                'atl_type': atl_type_display,
            })
        return JsonResponse({
            'found':   False,
            'message': f'No record found for {query}. May be Non-Filer or ATL not updated yet.',
        })
    except Exception as e:
        return JsonResponse({'found': False, 'error': str(e)})


def tax_calendar(request):
    return render(request, 'tax-calendar.html')


def fbr_iris_guide(request):
    return render(request, 'fbr-iris-guide.html')


def redirect_to_mcqs(request, **kwargs):
    from django.http import HttpResponsePermanentRedirect
    return HttpResponsePermanentRedirect('/income-tax-mcqs-pakistan/')


def Withholding_Tax_Card(request):
    """
    WHT Calculator page.
    Passes categories list to template for tab rendering.
    Actual rate data is loaded via /api/wht-rates/ JSON API.
    """
    try:
        tax_year = request.GET.get('year', '2025-2026')

        # Category list for tab buttons (static — matches DB cat values)
        categories = [
            {'key': 'property', 'label': '🏠 Property'},
            {'key': 'banking', 'label': '🏦 Banking'},
            {'key': 'dividends', 'label': '📈 Dividends'},
            {'key': 'imports', 'label': '📦 Imports'},
            {'key': 'goods', 'label': '🛒 Goods'},
            {'key': 'services', 'label': '💼 Services'},
            {'key': 'contracts', 'label': '📝 Contracts'},
            {'key': 'exports', 'label': '✈️ Exports'},
            {'key': 'rent', 'label': '🏢 Rent'},
            {'key': 'prizes', 'label': '🎁 Prizes'},
            {'key': 'vehicles', 'label': '🚗 Vehicles'},
            {'key': 'salary', 'label': '💰 Salary'},
            {'key': 'other', 'label': '📋 Other'},
        ]

        return render(request, 'partials/wht_calculator.html', {
            'categories': categories,
            'tax_year': tax_year,
            'meta_title': 'Withholding Tax Calculator Pakistan 2025-26 | TaxBuddy Umair',
            'meta_description': (
                'Free withholding tax & advance tax calculator Pakistan 2025-26. '
                'Calculate WHT for 80+ FBR sections — property, banking, services, '
                'imports, exports. Filer vs non-filer rates per Finance Act 2025.'
            ),
        })
    except Exception as e:
        return HttpResponse("Exception: " + str(e))


def wht_rates_api(request):
    try:
        tax_year = request.GET.get('year', '2025-26')

        rates_qs = WHTRate.objects.filter(
            is_active=True,
            tax_year=tax_year,
        ).order_by('sort_order', 'section')

        # Sections jahan late filer rate ALAG hoti hai
        LATE_FILER_DIFF_SECTIONS = {'236C', '236K'}

        data = []
        for r in rates_qs:
            # Late filer rate logic
            if r.section in LATE_FILER_DIFF_SECTIONS:
                late_filer_rate = float(r.late_filer)
            else:
                late_filer_rate = float(r.filer)  # Same as filer

            data.append({
                'id':         r.uid,
                'section':    r.section,
                'cat':        r.cat,
                'name':       r.name,
                'sub':        r.sub or '',
                'filer':      float(r.filer),
                'late_filer': late_filer_rate,   # ← corrected
                'non_filer':  float(r.non_filer),
                'filer_raw':  str(r.filer),
                'late_raw':   str(r.late_filer),
                'non_raw':    str(r.non_filer),
                'nature':     r.nature,
                'type':       r.tax_type,
                'notes':      r.notes or '',
                'threshold':  '',
                'isFixed':    r.rate_kind == 'fixed',
                'slab_min': r.slab_min,
                'slab_max': r.slab_max,
                'base_tax': float(r.base_tax) if r.base_tax else 0,
                'rate_kind': r.rate_kind,
            })

        return JsonResponse({
            'status':   'ok',
            'tax_year': tax_year,
            'rates':    data
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def SalaryCalculator2027(request):
    return render(request, 'salary-tax-calculator-2026-27.html')


def refund_analyzer(request):
    return render(request, 'partials/refund-analyzer.html')



import json
import base64

from django.shortcuts import render
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from django.conf import settings

import anthropic


MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB

# Template path — your live file is in partials/. Change here if it moves.
TEMPLATE_NAME = "partials/refund-analyzer.html"


# ---------------------------------------------------------------------------
# IRIS code reference — from the official FBR IRIS schedule screenshots.
# Helps Claude classify by code, not just by label.
# ---------------------------------------------------------------------------
IRIS_CODE_REFERENCE = """
KNOWN IRIS CODES (parent block -> section -> nature):

ADJUSTABLE TAX (parent 640000):
- 64020004 = Salary u/s 149 (adjustable)
- 64080001 = Rent of Immovable Property u/s 155 (adjustable)
- 64100101 = Cash withdrawal u/s 231AB (adjustable)
- 64151905 = Foreign remittance via card u/s 236Y (adjustable)
- 64150301 = Sale/Transfer of Immovable Property u/s 236C (adjustable; BUT minimum if acquired AND disposed within the same tax year)
- 64150302 = u/s 236C where property purchased AND sold within tax year (MINIMUM)
- 64150303 = u/s 236C where property purchased prior to current year (adjustable)
- 64151101 = Purchase/Transfer of Immovable Property u/s 236K (adjustable)
- 64150701 = Commodities by Distributors/Dealers/Wholesalers u/s 236G (adjustable)
- 64150803 = Purchase by Retailers u/s 236H (adjustable)
- 64060002/03/05/09 = Goods u/s 153(1)(a) (adjustable for company/listed; MINIMUM for individual/AOP)
- 64150001-05 = Telephone/Cellphone/Internet u/s 236 (adjustable)
- 64100301-326 = Motor Vehicle registration/sale u/s 231B (adjustable)
- 64130001-003 = Vehicle token tax u/s 234 (adjustable)

MINIMUM TAX (parent 64000102):
- 64010052-062 = Imports u/s 148 various rates (minimum)
- 64060151-172 = Services u/s 153(1)(b) various (minimum)
- 64120060-074 = Brokerage/Commission u/s 233 (minimum)
- 64140051-053 = Electricity bill u/s 235 commercial/industrial (minimum)

FINAL / FIXED TAX (parent 64000101 or 640001):
- 64330050-086 = Dividend u/s 150 various (final)
- 64040051-058 = Profit on Debt u/s 151 / 7B (final for individual >5M; MINIMUM if company OR 7B applies <=5M)
- 64070152-155 = Export Proceeds u/s 154 (final)
- 64090052-056 = Winnings: prize bond/raffle/lottery/quiz/sale promotion u/s 156 (final)
- 64220050-064 = Capital Gains on Immovable Property u/s 37(1A) (separate block)
- 64220112-119 = Capital Gains on Securities u/s 37A (final/separate)
- 64050050-098 = Payments to Non-Residents u/s 152 various (final)

OVERRIDE RULES (apply these, not just the label):
- 236C is MINIMUM (not adjustable) when property is acquired AND disposed within the SAME tax year.
- 153(1)(a) goods & 153(1)(c) contracts: adjustable for companies/listed; MINIMUM for individuals/AOPs.
- 153(1)(b) services: MINIMUM for all.
- 151 profit on debt: MINIMUM if company OR taxable under 7B (<=5M); FINAL for individual/AOP if profit exceeds 5M.
"""


EXTRACTION_PROMPT = """You are extracting data from a Pakistani FBR IRIS income tax return (114(1) acknowledgement / computation). Return ONLY valid JSON — no explanation, no markdown, no code fences.

Use the FBR codes printed in the return to locate values:
- Name, Registration No (NTN/CNIC), Tax Year, Residence Status: from the header.
- total_income        -> code 9000
- taxable_income      -> code 9100
- tax_chargeable      -> code 9200
- withholding_tax     -> code 9201
- refundable_reported -> code 9210   (may be 0 or absent)

Read EVERY block in the return:
- "Adjustable Tax" block (parent 640000): each row = adjustable deduction.
- "Minimum Tax" block (parent 64000102): each row = minimum-tax deduction.
- "Fixed / Final Tax" block (parent 64000101 or 640001): each row = final deduction.

Use this reference of known IRIS codes and their legal nature to classify accurately.
Do NOT rely on the label alone — apply the override rules at the end:
""" + IRIS_CODE_REFERENCE + """

For every deduction row capture:
- "code": the SECTION from the description ("Salary of Employees u/s 149" -> "149"; "u/s 236C" -> "236C"; "u/s 153(1)(b)" -> "153b").
- "amount": the "Tax Collected / Deducted" column (the tax).
- "taxable_value": the "Taxable Value" / "Receipts / Value" column (gross amount). Null if none.
- "block": "adjustable", "minimum", or "final" — by which block it sits in AND the override rules.

Return exactly this shape:
{
  "name": "<string or null>",
  "registration": "<string or null>",
  "tax_year": "<string or null>",
  "residence": "<Resident|Non-Resident|null>",
  "taxpayer": "individual",
  "total_income": <number or null>,
  "taxable_income": <number or null>,
  "tax_chargeable": <number or null>,
  "withholding_tax": <number or null>,
  "refundable_reported": <number or null>,
  "deductions": [
    {"code": "<section>", "amount": <number>, "taxable_value": <number or null>, "block": "adjustable|minimum|final"}
  ]
}

Rules:
- Numbers only — strip commas and "Rs"/"PKR". Null for missing (not 0).
- Read ALL blocks and ALL rows; skip nothing.
- Apply the override rules (236C same-year, 153, 151) when setting "block".
- Do not invent values. Output the JSON object only.
"""


def _client():
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured in settings.")
    return anthropic.Anthropic(api_key=api_key)


def _strip_fences(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: t.rfind("```")]
    return t.strip()


@require_GET
def refund_analyzer(request):
    return render(request, TEMPLATE_NAME)



@csrf_protect
@require_POST
def refund_analyzer_extract(request):
    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"ok": False, "error": "No file uploaded."}, status=400)

    if upload.content_type != "application/pdf":
        return JsonResponse({"ok": False, "error": "Please upload a PDF file."}, status=400)
    if upload.size > MAX_PDF_BYTES:
        return JsonResponse({"ok": False, "error": "File too large (max 10MB)."}, status=400)

    pdf_b64 = base64.standard_b64encode(upload.read()).decode("utf-8")

    try:
        client = _client()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document",
                     "source": {"type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64}},
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }],
        )
    except Exception as exc:
        print("CLAUDE API ERROR:", repr(exc))
        return JsonResponse(
            {"ok": False, "error": "Could not read the return right now. Please try again."},
            status=502,
        )

    raw = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
    raw = _strip_fences(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return JsonResponse(
            {"ok": False, "error": "The return could not be parsed. Enter figures manually."},
            status=422,
        )

    data.setdefault("taxpayer", "individual")
    data.setdefault("deductions", [])
    clean = []
    for d in data.get("deductions", []):
        try:
            code = str(d.get("code", "")).strip()
            amount = float(d.get("amount") or 0)
            block = d.get("block", "adjustable")
            tv = d.get("taxable_value")
            taxable_value = float(tv) if tv not in (None, "") else None
            if code and amount > 0:
                clean.append({"code": code, "amount": amount,
                              "taxable_value": taxable_value, "block": block})
        except (TypeError, ValueError):
            continue
    data["deductions"] = clean

    return JsonResponse({"ok": True, "data": data})


# ---------------------------------------------------------------------------
# URLs — add to urls.py
# ---------------------------------------------------------------------------
# from django.urls import path
# from . import views
#
# urlpatterns = [
#     path("refund-analyzer/",         views.refund_analyzer,         name="refund_analyzer"),
#     path("refund-analyzer/extract/", views.refund_analyzer_extract, name="refund_analyzer_extract"),
# ]


# ════════════════════════════════════════════════════════════
# 4. views.py — ADD this whole block
#
# Imports: tumhare views.py mein render, JsonResponse, Q, F,
# reverse, Paginator already imported hain. Sirf yeh do cheezein
# models import mein add karo:
#
#   from .models import ( Blog, ..., WHTRate, SearchQuery, TaxGuide, FAQ )
#                                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^
# (TaxGuide/FAQ agar pehle se import hain to sirf SearchQuery)
# ════════════════════════════════════════════════════════════

from django.db import connection


def _get_page_index():
    """Static tool/guide pages (DB mein nahi) — search results mein
    inhe bhi dikhana hai. URLs reverse() se, hardcode nahi."""
    return [
        {"title": "Salary Tax Calculator 2025-26", "url": reverse("SalaryCalculator"),
         "desc": "Calculate income tax on salary using FBR 2025-26 slabs.",
         "keywords": "salary tax calculator income slab monthly annual 2025"},
        {"title": "Proposed Salary Tax Calculator 2026-27", "url": reverse("SalaryCalculator2027"),
         "desc": "Post-budget proposed salary tax slabs for 2026-27.",
         "keywords": "salary tax calculator 2026 2027 budget proposed new slabs"},
        {"title": "Business Tax Calculator", "url": reverse("BusinessCalculator"),
         "desc": "Estimate tax for sole proprietors and small businesses.",
         "keywords": "business tax calculator sole proprietor individual"},
        {"title": "AOP Tax Calculator", "url": reverse("AOPCalculator"),
         "desc": "Tax liability for Association of Persons (partnership firms).",
         "keywords": "aop tax calculator partnership firm association persons"},
        {"title": "Property / Rental Income Calculator", "url": reverse("PropertyCalculator"),
         "desc": "Tax on rental income under Section 15.",
         "keywords": "property rental income tax calculator rent section 15"},
        {"title": "Super Tax 4C Calculator", "url": reverse("TaxCalculator4C"),
         "desc": "Super tax under Section 4C.",
         "keywords": "super tax 4c calculator section high income"},
        {"title": "Withholding & Advance Tax Calculator", "url": reverse("Withholding_Tax_Card"),
         "desc": "WHT on 80+ transaction types, filer vs non-filer.",
         "keywords": "withholding tax calculator advance wht 236 filer non filer card"},
        {"title": "ATL Check — Filer Status", "url": reverse("atl_check"),
         "desc": "Check active taxpayer (filer) status by NTN or CNIC.",
         "keywords": "atl check active taxpayer list filer status ntn cnic"},
        {"title": "Withholding Tax Rates 2025-26", "url": reverse("withholding_tax_rates"),
         "desc": "Full FBR WHT rate card — filer, late filer, non-filer.",
         "keywords": "withholding tax rates card 236c 236k 151 property bank filer"},
        {"title": "Income Tax Guides", "url": reverse("income_tax_guides"),
         "desc": "Guides on filing, filer status, ATL benefits and IRIS.",
         "keywords": "income tax guide return filing iris how to file"},
        {"title": "Sales Tax Guides", "url": reverse("sales_tax_guides"),
         "desc": "GST registration, monthly filing and withholding guides.",
         "keywords": "sales tax guide gst registration monthly return filing"},
        {"title": "FBR IRIS Guide", "url": reverse("fbr_iris_guide"),
         "desc": "Step-by-step FBR IRIS portal walkthrough.",
         "keywords": "fbr iris guide portal login registration password 181"},
        {"title": "Tax Calendar", "url": reverse("tax_calendar"),
         "desc": "All FBR filing deadlines and due dates.",
         "keywords": "tax calendar deadline due date filing last date"},
        {"title": "Tax MCQs Practice", "url": reverse("question_list"),
         "desc": "200+ income tax MCQs with explanations.",
         "keywords": "mcq quiz practice test income tax questions exam preparation"},
    ]


def _search_blogs_fulltext(q):
    """MySQL FULLTEXT, relevance-sorted, sirf published + not deleted."""
    table = Blog._meta.db_table
    sql = f"""
        SELECT id, title, slug,
               MATCH(title, content) AGAINST (%s IN NATURAL LANGUAGE MODE) AS relevance
        FROM `{table}`
        WHERE status = 'published' AND is_deleted = 0
          AND MATCH(title, content) AGAINST (%s IN NATURAL LANGUAGE MODE)
        ORDER BY relevance DESC
        LIMIT 50
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, [q, q])
            rows = cursor.fetchall()
        return [{"title": r[1], "slug": r[2]} for r in rows]
    except Exception:
        # index abhi nahi bana / sqlite local dev — fallback sambhal lega
        return []


def _search_blogs_fallback(q):
    """Short terms (7E, ATL, 115) FULLTEXT skip kar deta hai — LIKE catch karta hai."""
    qs = (Blog.objects
          .filter(status='published', is_deleted=False)
          .filter(Q(title__icontains=q) | Q(content__icontains=q))
          .values('title', 'slug')[:30])
    return list(qs)


def _search_pages(q):
    words = [w for w in q.lower().split() if len(w) >= 2]
    if not words:
        return []
    results = []
    for page in _get_page_index():
        haystack = (page["title"] + " " + page["keywords"]).lower()
        score = sum(1 for w in words if w in haystack)
        if score:
            results.append({**page, "score": score})
    results.sort(key=lambda p: p["score"], reverse=True)
    return results[:5]


def search(request):
    q = (request.GET.get("q") or "").strip()[:200]
    blog_hits, guide_hits, faq_hits, page_hits = [], [], [], []

    if len(q) >= 2:
        blog_hits = _search_blogs_fulltext(q)
        if not blog_hits:
            blog_hits = _search_blogs_fallback(q)

        page_hits = _search_pages(q)

        guide_hits = list(
            TaxGuide.objects.filter(is_active=True)
            .filter(Q(title__icontains=q) | Q(summary__icontains=q))
            .values('title', 'summary', 'category')[:4]
        )
        for g in guide_hits:
            g['url'] = reverse('income_tax_guides') if g['category'] == 'income_tax' \
                       else reverse('sales_tax_guides')

        faq_hits = list(
            FAQ.objects.filter(is_active=True)
            .filter(Q(question__icontains=q) | Q(answer__icontains=q))
            .values('question', 'answer')[:4]
        )

        total = len(blog_hits) + len(page_hits) + len(guide_hits) + len(faq_hits)

        # Query logging — kabhi search ko crash na kare
        try:
            obj, created = SearchQuery.objects.get_or_create(
                term=q.lower(), defaults={"results_found": total},
            )
            if not created:
                SearchQuery.objects.filter(pk=obj.pk).update(
                    count=F("count") + 1, results_found=total,
                )
        except Exception:
            pass
    else:
        total = 0

    paginator = Paginator(blog_hits, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "search.html", {
        "q": q,
        "page_hits": page_hits,
        "guide_hits": guide_hits,
        "faq_hits": faq_hits,
        "page_obj": page_obj,
        "total": total,
        "meta_title": f"Search: {q} | TaxBuddy Umair" if q else "Search | TaxBuddy Umair",
    })


# ════════════════════════════════════════════════════════════
# 5. urls.py — PUBLIC PAGES section mein add karo
#    (catch-all se bohat upar, koi bhi jagah theek hai wahan):
#
#    path('search/', views.search, name='search'),
# ════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════
# 3. views.py — ADD this whole block (TaxBuddyApp/views.py)
#
# Import line mein add karo:
#   from .models import ( ..., Instrument, Subscriber )
#
# In imports ki bhi zaroorat hai (jo pehle se nahi hain woh add):
#   from django.shortcuts import get_object_or_404, redirect
#   from django.contrib.auth.decorators import login_required
#   from django.contrib import messages
#   from django.core.validators import validate_email
#   from django.core.exceptions import ValidationError
#   from django.db.models import F
# ════════════════════════════════════════════════════════════


# ─── PUBLIC: SRO TRACKER ─────────────────────────────────────

def sro_list(request):
    qs = Instrument.objects.filter(is_active=True)

    active_type = request.GET.get('type', 'all')
    active_statute = request.GET.get('statute', 'all')
    active_year = request.GET.get('year', 'all')
    q = (request.GET.get('q') or '').strip()[:100]

    if active_type != 'all':
        qs = qs.filter(instrument_type=active_type)
    if active_statute != 'all':
        qs = qs.filter(statute=active_statute)
    if active_year != 'all' and active_year.isdigit():
        qs = qs.filter(issue_date__year=int(active_year))
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(subject__icontains=q) |
                       Q(related_sections__icontains=q))

    years = (Instrument.objects.filter(is_active=True)
             .dates('issue_date', 'year', order='DESC'))

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'sro_list.html', {
        'page_obj': page_obj,
        'total': qs.count(),
        'years': [d.year for d in years],
        'active_type': active_type,
        'active_statute': active_statute,
        'active_year': active_year,
        'q': q,
    })


def sro_detail(request, slug):
    instrument = get_object_or_404(Instrument, slug=slug, is_active=True)
    Instrument.objects.filter(pk=instrument.pk).update(view_count=F('view_count') + 1)

    related = (Instrument.objects.filter(is_active=True, statute=instrument.statute)
               .exclude(pk=instrument.pk)[:4])

    return render(request, 'sro_detail.html', {
        'i': instrument,
        'related': related,
    })


# ─── NEWSLETTER SUBSCRIBE ────────────────────────────────────

def subscribe(request):
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()[:254]
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Please enter a valid email address.')
        else:
            obj, created = Subscriber.objects.get_or_create(
                email=email, defaults={'source': request.POST.get('source', 'sro_page')[:50]})
            if created:
                messages.success(request, '✅ Subscribed! You will get every new SRO explained in plain English.')
            elif not obj.is_active:
                obj.is_active = True
                obj.save(update_fields=['is_active'])
                messages.success(request, '✅ Welcome back — subscription re-activated.')
            else:
                messages.info(request, 'You are already subscribed.')
    return redirect(request.POST.get('next') or 'sro_list')


# ─── ADMIN / CPANEL: MANAGE SROs ─────────────────────────────

@login_required(login_url='Login')
def manage_sros(request):
    qs = Instrument.objects.all()
    active_type = request.GET.get('type', 'all')
    if active_type != 'all':
        qs = qs.filter(instrument_type=active_type)
    return render(request, 'Cpanel/manage_sros.html', {
        'instruments': qs,
        'active_type': active_type,
        'subscriber_count': Subscriber.objects.filter(is_active=True).count(),
    })


@login_required(login_url='Login')
def add_edit_sro(request, pk=None):
    instrument = get_object_or_404(Instrument, pk=pk) if pk else None

    if request.method == 'POST':
        data = request.POST
        try:
            if instrument is None:
                instrument = Instrument()
            instrument.instrument_type = data.get('instrument_type', 'sro')
            instrument.number = data.get('number', '').strip()
            instrument.statute = data.get('statute', 'income_tax')
            instrument.issue_date = data.get('issue_date') or None
            instrument.effective_date = data.get('effective_date') or None
            instrument.subject = data.get('subject', '').strip()
            instrument.summary = data.get('summary', '').strip()
            instrument.who_affected = data.get('who_affected', '').strip()
            instrument.old_rule = data.get('old_rule', '').strip()
            instrument.new_rule = data.get('new_rule', '').strip()
            instrument.related_sections = data.get('related_sections', '').strip()
            instrument.fbr_link = data.get('fbr_link', '').strip()
            instrument.is_active = bool(data.get('is_active'))
            rb = data.get('related_blog')
            instrument.related_blog = Blog.objects.filter(pk=rb).first() if rb else None
            if request.FILES.get('pdf'):
                instrument.pdf = request.FILES['pdf']
            instrument.full_clean(exclude=['slug', 'effective_date', 'pdf'])
            instrument.save()
            messages.success(request, f'✅ {instrument.number} saved.')
            return redirect('manage_sros')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    blogs = Blog.objects.filter(is_deleted=False).order_by('-created_at')
    return render(request, 'Cpanel/add_sro.html', {
        'instrument': instrument,
        'blogs': blogs,
    })


@login_required(login_url='Login')
def delete_sro(request, pk):
    instrument = get_object_or_404(Instrument, pk=pk)
    number = instrument.number
    instrument.delete()
    messages.success(request, f'🗑 {number} deleted.')
    return redirect('manage_sros')


# ════════════════════════════════════════════════════════════
# 4. urls.py — ADD (PUBLIC PAGES section + ADMIN section):
#
#   # ── SRO TRACKER ───────────────────────────────────────
#   path('sros/', views.sro_list, name='sro_list'),
#   path('sros/<slug:slug>/', views.sro_detail, name='sro_detail'),
#   path('subscribe/', views.subscribe, name='subscribe'),
#
#   # ── SRO MANAGEMENT (admin section mein) ───────────────
#   path('manage-sros/', views.manage_sros, name='manage_sros'),
#   path('add-sro/', views.add_edit_sro, name='add_sro'),
#   path('edit-sro/<int:pk>/', views.add_edit_sro, name='edit_sro'),
#   path('delete-sro/<int:pk>/', views.delete_sro, name='delete_sro'),
#
# (Catch-all /<slug>/ se upar — 'sros/' prefix hai to koi clash
#  nahi, PUBLIC PAGES section mein hi daal do.)
# ════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════
# 2. views.py — ADD this whole block (TaxBuddyApp/views.py)
#
# Models import mein add: GlossaryTerm
# (baqi sab imports — get_object_or_404, redirect, login_required,
#  messages, F, Q — SRO wale kaam mein already add ho chuke)
# ════════════════════════════════════════════════════════════


# ─── PUBLIC: GLOSSARY ────────────────────────────────────────

def glossary_list(request):
    q = (request.GET.get('q') or '').strip()[:100]
    qs = GlossaryTerm.objects.filter(is_active=True)
    if q:
        qs = qs.filter(Q(term__icontains=q) | Q(short_meaning__icontains=q))

    # Group A-Z
    groups = {}
    for t in qs:
        groups.setdefault(t.first_letter, []).append(t)
    letters = sorted(groups.keys())

    return render(request, 'glossary_list.html', {
        'groups': [(l, groups[l]) for l in letters],
        'letters': letters,
        'total': qs.count(),
        'q': q,
    })


def glossary_detail(request, slug):
    term = get_object_or_404(GlossaryTerm, slug=slug, is_active=True)
    GlossaryTerm.objects.filter(pk=term.pk).update(view_count=F('view_count') + 1)

    # Related term objects (agar related_terms mein likhe naam DB mein exist karein)
    related_objs = GlossaryTerm.objects.filter(
        is_active=True, term__in=term.related_terms_list) if term.related_terms_list else []

    return render(request, 'glossary_detail.html', {
        't': term,
        'related_objs': related_objs,
    })


# ─── ADMIN / CPANEL: MANAGE GLOSSARY ─────────────────────────

@login_required(login_url='Login')
def manage_glossary(request):
    return render(request, 'Cpanel/manage_glossary.html', {
        'terms': GlossaryTerm.objects.all(),
    })


@login_required(login_url='Login')
def add_edit_glossary(request, pk=None):
    term = get_object_or_404(GlossaryTerm, pk=pk) if pk else None

    if request.method == 'POST':
        data = request.POST
        try:
            if term is None:
                term = GlossaryTerm()
            term.term = data.get('term', '').strip()
            term.short_meaning = data.get('short_meaning', '').strip()
            term.explanation = data.get('explanation', '').strip()
            term.legal_definition = data.get('legal_definition', '').strip()
            term.section_ref = data.get('section_ref', '').strip()
            term.example = data.get('example', '').strip()
            term.related_terms = data.get('related_terms', '').strip()
            term.related_url = data.get('related_url', '').strip()
            term.related_url_label = data.get('related_url_label', '').strip()
            term.is_active = bool(data.get('is_active'))
            rb = data.get('related_blog')
            term.related_blog = Blog.objects.filter(pk=rb).first() if rb else None
            term.full_clean(exclude=['slug'])
            term.save()
            messages.success(request, f'✅ "{term.term}" saved.')
            return redirect('manage_glossary')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    blogs = Blog.objects.filter(is_deleted=False).order_by('-created_at')
    return render(request, 'Cpanel/add_glossary.html', {
        'term': term,
        'blogs': blogs,
    })


@login_required(login_url='Login')
def delete_glossary(request, pk):
    term = get_object_or_404(GlossaryTerm, pk=pk)
    name = term.term
    term.delete()
    messages.success(request, f'🗑 "{name}" deleted.')
    return redirect('manage_glossary')


# ════════════════════════════════════════════════════════════
# 3. urls.py — ADD:
#
# PUBLIC (SRO TRACKER lines ke neeche):
#   # ── GLOSSARY ──────────────────────────────────────────
#   path('glossary/', views.glossary_list, name='glossary_list'),
#   path('glossary/<slug:slug>/', views.glossary_detail, name='glossary_detail'),
#
# ADMIN (SRO Management ke neeche):
#   # Glossary Management
#   path('manage-glossary/',           views.manage_glossary,  name='manage_glossary'),
#   path('add-glossary/',              views.add_edit_glossary, name='add_glossary'),
#   path('edit-glossary/<int:pk>/',    views.add_edit_glossary, name='edit_glossary'),
#   path('delete-glossary/<int:pk>/',  views.delete_glossary,  name='delete_glossary'),
# ════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════
# RATE HISTORY — views.py ADD (Product Bible Tier 2 #9)
# Data source: tumhara existing TaxBracket model (Add Tax Brackets
# se jo salary slabs har saal dalte ho) — koi naya model nahi.
#
# Import: TaxBracket already imported hai views.py mein.
# ════════════════════════════════════════════════════════════

SAMPLE_ANNUAL_INCOMES = [600_000, 1_200_000, 1_800_000, 2_400_000,
                         3_600_000, 6_000_000, 12_000_000]


def _tax_for(income, brackets):
    """base_tax + (income - base_income) * rate — first matching slab."""
    for b in brackets:
        if income >= b.income_min and (b.income_max is None or income <= b.income_max):
            return round(float(b.base_tax) + (income - float(b.base_income)) * float(b.rate))
    return None


def salary_rate_history(request):
    all_years = list(
        TaxBracket.objects
        .values_list('year', flat=True).distinct().order_by('-year'))

    if not all_years:
        return render(request, 'rate_history.html', {'no_data': True})

    # Comparison pair (?y1=2025-2026&y2=2026-2027), default: latest two
    y1 = request.GET.get('y1') if request.GET.get('y1') in all_years else (all_years[1] if len(all_years) > 1 else all_years[0])
    y2 = request.GET.get('y2') if request.GET.get('y2') in all_years else all_years[0]

    def slabs(year):
        return list(TaxBracket.objects.filter(year=year)
                    .order_by('income_min'))

    b1, b2 = slabs(y1), slabs(y2)

    comparison = []
    for inc in SAMPLE_ANNUAL_INCOMES:
        t1, t2 = _tax_for(inc, b1), _tax_for(inc, b2)
        diff = (t2 - t1) if (t1 is not None and t2 is not None) else None
        comparison.append({
            'income': inc, 'monthly': round(inc / 12),
            't1': t1, 't2': t2, 'diff': diff,
            'm1': round(t1 / 12) if t1 is not None else None,
            'm2': round(t2 / 12) if t2 is not None else None,
        })

    # Full slab tables per year (history section)
    history = [(y, slabs(y)) for y in all_years]

    return render(request, 'rate_history.html', {
        'years': all_years, 'y1': y1, 'y2': y2,
        'slabs1': b1, 'slabs2': b2,
        'comparison': comparison,
        'history': history,
    })


# ════════════════════════════════════════════════════════════
# urls.py — PUBLIC PAGES mein ADD (glossary lines ke neeche):
#
#   path('salary-tax-slabs-history/', views.salary_rate_history,
#        name='salary_rate_history'),
#
# sitemaps.py — StaticSitemap ki pages list mein
#   '/salary-tax-slabs-history/' add karo.
#
# navbar — Calculators dropdown mein:
#   <a href="{% url 'salary_rate_history' %}" role="menuitem">📊 Slabs History & Budget Comparison</a>
# ════════════════════════════════════════════════════════════