import mimetypes
from datetime import timezone, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
import requests
from django.http import HttpResponse, request, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.utils.text import slugify
from django.contrib import messages
from django.utils.timezone import now

from .models import Blogs, Comment, Contact, TaxBracket, Business_AOP_Slab, Property_Business_AOP_Slab, Question, Option


def index(request):
    try:
        result = Blogs.objects.filter(status=1, is_deleted=False)
        latest_blogs = Blogs.objects.filter(
            status=1,
            is_deleted=False,
            created_date__gte=now().date() - timedelta(days=3)
        ).order_by('-updated_date')[:3]
        print(latest_blogs)
        return render(request, 'index.html', {'result': result, 'latest_blogs': latest_blogs})
    except Exception as e:
        return HttpResponse(str(e))


def Login(request):
    try:
        if request.method == 'POST':
            username = request.POST['username']
            pwd = request.POST['password']
            user = authenticate(request, username=username, password=pwd)
            if user:
                print('user', user)
                login(request, user)
                request.session['username'] = username
                return redirect('Dashboard')

        return render(request, 'Login.html')
    except Exception as e:
        return HttpResponse(str(e))


@login_required(login_url='Login')  # redirect when user is not logged in
def Dashboard(request):
    try:
        return render(request, 'Cpanel/Dashboard.html')
    except Exception as e:
        print('Exception Dashboard:', str(e))
        return HttpResponse(str(e))


@login_required(login_url='Login')  # redirect when user is not logged in
def AddEditBlog(request, slug=None):
    try:
        blog = None  # default: no blog (create mode)
        # Only fetch if slug exists (edit mode)
        if slug:
            blog = get_object_or_404(Blogs, slug=slug, status=1, is_deleted=False)

        if request.method == 'POST':
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            blog_type = int(request.POST.get('type', 0))
            image = request.FILES.get('attachment')

            if not title or not description:
                return HttpResponse("Title and description are required.", status=400)

            # Unique slug
            new_slug = slugify(title)
            counter = 1
            while Blogs.objects.filter(slug=new_slug).exclude(pk=blog.pk if blog else None).exists():
                new_slug = f"{slugify(title)}-{counter}"
                counter += 1

            if blog:  # update mode
                blog.type = blog_type
                blog.title = title
                blog.slug = new_slug
                blog.description = description
                if image:
                    if image.content_type not in ["image/jpeg", "image/png", "image/webp", "application/pdf"]:
                        return HttpResponse("Invalid file format.", status=400)
                    blog.image = image
                blog.save()
            else:  # create mode
                if not image:
                    return HttpResponse("File is required for new blog.", status=400)
                if image.content_type not in ["image/jpeg", "image/png", "image/webp", "application/pdf"]:
                    return HttpResponse("Invalid file format.", status=400)
                blog = Blogs.objects.create(
                    title=title,
                    type=blog_type,
                    slug=new_slug,
                    description=description,
                    image=image,
                )

        return render(request, 'Cpanel/AddEditBlog.html', {'blog': blog})
    except Exception as e:
        print('Exception at Add Edit Blog Page :', str(e))
        return HttpResponse("Exception: " + str(e))


@login_required(login_url='Login')  # redirect when user is not logged in
def deleteBlog(request, slug=None):
    try:
        blogs = Blogs.objects.filter(status=1, slug=slug, is_deleted=False)
        for blog in blogs:
            blog.delete()
        return redirect('ManageBlogs')
    except Exception as e:
        print('Exception at Delete Details Page :', str(e))
        return HttpResponse(str('Exception at Delete Details Page :' + str(e)))


@login_required(login_url='Login')  # redirect when user is not logged in
def ManageBlogs(request):
    try:
        result = Blogs.objects.filter(status=1, is_deleted=False)
        return render(request, 'Cpanel/ManageBlogs.html', {'result': result})
    except Exception as e:
        print('Exception at Manage Blog Page :', str(e))
        return HttpResponse(str('Exception at Manage Blog Page :' + str(e)))


def BlogDetails(request, slug=None):
    try:
        blog = None
        blogComments = []
        blogList = []

        if not slug:
            raise Http404("Blog slug not provided")

        blog = get_object_or_404(
            Blogs,
            slug=slug,
            status=1,
            is_deleted=False
        )

        blogComments = Comment.objects.filter(
            status=1,
            slug=blog.slug
        )

        blogList = Blogs.objects.filter(
            status=1,
            is_deleted=False
        ).exclude(slug=slug).order_by('-created_date')

        return render(
            request,
            'partials/BlogDetails.html',
            {
                'blog': blog,
                'userComments': blogComments,
                'length': blogComments.count(),
                'blogList': blogList,
            }
        )

    except Http404:
        raise  # let Django handle 404 properly

    except Exception as e:
        print('Exception at Blog Details Page :', str(e))
        raise Http404("Something went wrong")


def viewBlogs(request, slug=None):
    try:
        type_map = {"income-tax": 1, "sales-tax": 2}
        if slug in type_map:
            # blogs = Blogs.objects.filter(type=type_map[slug], status=1, is_deleted=False)
            blogs = Blogs.objects.filter(
                type=type_map[slug],
                status=1,
                is_deleted=False
            ).order_by('-created_date')

        else:
            raise Http404("Invalid category")
        return render(request, "partials/viewBlogs.html", {"blogs": blogs})
    except Exception as e:
        print('Exception at Blog Details Page :', str(e))
        return HttpResponse(str('Exception at View Blogs Details Page :' + str(e)))


def userComments(request):
    try:
        if request.method == 'POST':
            user = request.POST['user']
            email = request.POST['email']
            comment = request.POST['comment']
            slug = request.POST['slug']
            blog = get_object_or_404(Blogs, slug=slug)
            Comment.objects.create(blog=blog, name=user, email_address=email, comment=comment, slug=slug)
            return redirect(f'/{slug}')  # or use reverse()

    except Exception as e:
        print('Exception :', str(e))
        return HttpResponse(str(e))


def contact(request):
    if request.method == "POST":
        try:
            token = request.POST.get('g-recaptcha-response')
            print("TOKEN:", request.POST.get('g-recaptcha-response'))

            data = {
                'secret': '6LesUD4sAAAAADDLaRxJpqYYXWkXygQasHX7sMFT',
                'response': token
            }

            r = requests.post(
                'https://www.google.com/recaptcha/api/siteverify',
                data=data
            )
            result = r.json()
            print("RECAPTCHA RESPONSE:", result)

            if not result.get('success') or result.get('score', 0) < 0.5:
                messages.error(request, "Captcha verification failed.")
                return redirect('/#contact')

            Contact.objects.create(
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                phone_number=request.POST.get('phone_number'),
                email_address=request.POST.get('email_address'),
                subject=request.POST.get('subject'),
                additional_details=request.POST.get('additional_details')
            )

            messages.success(request, "Thank you! We will contact you shortly.")
            return redirect('/#contact')

        except Exception as e:
            print("Contact form error:", e)
            messages.error(request, "Something went wrong. Please try again.")
            return redirect('/#contact')

    return redirect('/')


def AOPCalculator(request):
    try:
        content = {
            "title": "AOP Income Tax Calculator – Pakistan",
            "badge": "Multi-Year Tax Comparison",
            "intro": "This AOP income tax calculator helps partnerships and firms calculate and compare their tax liability across different tax years under the Income Tax Ordinance, 2001.",
            "who": [
                "Registered partnership firms",
                "Unregistered partnership firms",
                "Joint ventures",
                "Businesses classified as Association of Persons (AOP)"
            ],
            "how": "Enter the taxable income of the AOP and select one or more tax years. The calculator applies applicable AOP tax slabs for each selected year and provides a clear comparison of tax payable.",
            "features": [
                "Compare AOP tax across multiple tax years",
                "Yearly tax calculation based on AOP slabs",
                "Accurate slab-based computation",
                "Instant comparison results"
            ],
            "example": [
                "Monthly income: PKR 400,000",
                "Annual income: PKR 4,800,000",
                "Tax comparison across selected tax years"
            ],
            "notes": [
                "Partners’ share of profit may be taxed separately",
                "Withholding tax adjustments are not included",
                "Actual tax liability may vary after assessment"
            ]
        }

        # Base context (ALWAYS sent)
        context = {
            'content': content,
            'title': 'AOP',
            'url': '/AOPCalculator'
        }

        if request.method == 'POST':
            income_type = request.POST.get('income_type')
            income_amount = int(request.POST.get('income_amount'))
            tax_year_1 = request.POST.get('tax_year_1')
            tax_year_2 = request.POST.get('tax_year_2')

            yearly_income = income_amount * 12 if income_type == 'Monthly' else income_amount

            result_context = FetchResult(
                tax_year_1,
                tax_year_2,
                'AOP',
                yearly_income
            )

            context.update(result_context)
            context.update({
                'income_type': income_type
            })

        return render(request, 'partials/aop_slab.html', context)

    except Exception as e:
        print("Exception / Error at AOP Tax Calculator :", e)
        return HttpResponse("Exception / Error at AOP Tax Calculator")


def BusinessCalculator(request):
    try:
        content = {
            "title": "Business Income Tax Calculator – Pakistan",
            "badge": "Monthly & Yearly Comparison",
            "intro": "This business income tax calculator allows individuals and sole proprietors to calculate and compare their business tax across different tax years. Results can be viewed on monthly or yearly basis using applicable tax rules.",
            "who": [
                "Sole proprietors",
                "Freelancers earning business income",
                "Small and medium business owners",
                "Service providers and traders"
            ],
            "how": "Enter your net business income and select one or more tax years. The calculator applies applicable business income tax rates and provides a clear comparison of tax payable.",
            "features": [
                "Compare business tax across tax years",
                "Monthly and yearly tax calculation",
                "Net income based calculation",
                "Instant comparison results"
            ],
            "example": [
                "Monthly profit: PKR 200,000",
                "Annual profit: PKR 2,400,000",
                "Tax comparison across selected tax years"
            ],
            "notes": [
                "Allowable business expenses reduce taxable income",
                "Advance and withholding tax not included",
                "Sales tax is excluded from this calculation"
            ]
        }

        # Base context (ALWAYS sent)
        context = {
            'content': content,
            'title': 'Business Individual',
            'url': '/BusinessCalculator'
        }

        if request.method == 'POST':
            income_type = request.POST.get('income_type')
            income_amount = int(request.POST.get('income_amount'))
            tax_year_1 = request.POST.get('tax_year_1')
            tax_year_2 = request.POST.get('tax_year_2')

            yearly_income = income_amount * 12 if income_type == 'Monthly' else income_amount

            result_context = FetchResult(
                tax_year_1,
                tax_year_2,
                'Business Individual',
                yearly_income
            )

            context.update(result_context)
            context.update({
                'income_type': income_type
            })

        return render(request, 'partials/business_slab.html', context)

    except Exception as e:
        print("Exception / Error at Business Tax Calculator :", e)
        return HttpResponse("Exception / Error at Business Tax Calculator")


def SalaryCalculator(request):
    try:
        content = {
            "title": "Salary Income Tax Calculator – Pakistan",
            "badge": "Compare Tax by Year",
            "intro": "This salary income tax calculator allows you to calculate and compare your tax liability across different tax years. You can view tax results on a monthly or yearly basis using the latest FBR tax slabs.",
            "who": [
                "Government employees",
                "Private sector employees",
                "Contract-based salaried individuals",
                "Individuals earning salary income in Pakistan"
            ],
            "how": "Enter your salary and select one or more tax years. The calculator converts your income into annual salary and applies the relevant tax slabs for each selected year, allowing easy comparison of tax amounts.",
            "features": [
                "Compare tax for multiple tax years",
                "Monthly and yearly tax calculation",
                "Based on FBR notified tax slabs",
                "Instant comparison results"
            ],
            "example": [
                "Monthly salary: PKR 100,000",
                "Tax Year 2025 vs Tax Year 2026 comparison",
                "Monthly and annual tax difference displayed"
            ],
            "notes": [
                "Tax credits and exemptions are not included",
                "Allowances may be taxable depending on law",
                "Final tax may vary based on individual profile"
            ]
        }

        # Base context (ALWAYS SENT)
        context = {
            'content': content,
            'title': 'Salary Individual',
            'url': '/SalaryCalculator'
        }

        if request.method == 'POST':
            tax_year_1 = request.POST.get('tax_year_1')
            tax_year_2 = request.POST.get('tax_year_2')
            income_type = request.POST.get('income_type')
            income_amount = int(request.POST.get('income_amount'))

            yearly_income = income_amount * 12 if income_type == 'Monthly' else income_amount

            result_context = FetchResult(
                tax_year_1,
                tax_year_2,
                'Salary Individual',
                yearly_income
            )

            context.update(result_context)
            context.update({
                'income_type': income_type
            })

        return render(request, 'partials/salary_slab.html', context)

    except Exception as e:
        print("Exception / Error at Salary Tax Calculator :", e)
        return HttpResponse("Exception / Error at Salary Tax Calculator")


def PropertyCalculator(request):
    try:
        if request.method == 'POST':
            tax_year_1 = request.POST.get('tax_year_1')  #
            tax_year_2 = request.POST.get('tax_year_2')  #
            income_type = request.POST.get('income_type')  # 'Monthly' or 'Yearly'

            gross_rent = int(request.POST.get('gross_rent', 0))
            repairs_allowance = to_int(request.POST.get('repairs_allowance'))
            insurance_premium = to_int(request.POST.get('insurance_premium'))
            local_taxes = to_int(request.POST.get('local_taxes'))
            ground_rent = to_int(request.POST.get('ground_rent'))
            borrowed_interest = to_int(request.POST.get('borrowed_interest'))
            hbfc_payments = to_int(request.POST.get('hbfc_payments'))
            mortgage_interest = to_int(request.POST.get('mortgage_interest'))
            admin_expenses = to_int(request.POST.get('admin_expenses'))
            legal_expenses = to_int(request.POST.get('legal_expenses'))
            irrecoverable_rent = to_int(request.POST.get('irrecoverable_rent'))
            # Total deductions
            total_deductions = (
                    repairs_allowance + insurance_premium + local_taxes +
                    ground_rent + borrowed_interest + hbfc_payments +
                    mortgage_interest + admin_expenses + legal_expenses + irrecoverable_rent
            )
            if income_type == 'Monthly':
                yearly_income = gross_rent * 12
            else:
                yearly_income = gross_rent  # Already yearly income

            # Net rental income
            net_rental_income = yearly_income - total_deductions
            print(net_rental_income)
            context = FetchResult(tax_year_1, tax_year_2, 'Rental Income', net_rental_income)
            context.update({
                'net_income_rental': net_rental_income,
                'total_deductions': total_deductions,
                'yearly_income': yearly_income
            })
            # return HttpResponse(str(context))
            return render(request, 'partials/property_rent.html', context)

        else:
            return render(request, 'partials/property_rent.html')

    except Exception as e:
        print(f'Error {e}')

        return HttpResponse(f"Error: {str(e)}")


def Logout(request):
    logout(request)
    return redirect('/')


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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

            if taxpayer_type == 'ind_aop_person':
                Business_AOP_Slab.objects.create(
                    year=tax_year, income_min=income_min, income_max=None if income_max == float('inf') else income_max,
                    rate=Decimal(str(rate)), base_income=base_income, base_tax=base_tax)
            else:

                TaxBracket.objects.create(
                    year=tax_year, income_min=income_min, income_max=None if income_max == float('inf') else income_max,
                    rate=Decimal(str(rate)), base_income=base_income, base_tax=base_tax)
            return render(request, 'Cpanel/add_salary_tax_brackets.html')

        else:
            return render(request, 'Cpanel/add_salary_tax_brackets.html')
    except Exception as e:
        print(f'Error {e}')
        return HttpResponse(f"Error: {str(e)}")


def FetchResult(tax_year_1, tax_year_2, taxpayer_type, yearly_income):
    try:

        if taxpayer_type == 'Salary Individual':
            tax_brackets_result_one = TaxBracket.objects.filter(year=tax_year_1)
            tax_brackets_result_two = TaxBracket.objects.filter(year=tax_year_2)
        elif taxpayer_type == 'Business Individual' or taxpayer_type == 'AOP':
            tax_brackets_result_one = Business_AOP_Slab.objects.filter(year=tax_year_1)
            tax_brackets_result_two = Business_AOP_Slab.objects.filter(year=tax_year_2)
        else:
            tax_brackets_result_one = Property_Business_AOP_Slab.objects.filter(year=tax_year_1)
            tax_brackets_result_two = Property_Business_AOP_Slab.objects.filter(year=tax_year_2)

        brackets_tax_year_1 = {(float(s.income_min), float(s.income_max) if s.income_max else float('inf')):
                                   (float(s.rate), float(s.base_income), float(s.base_tax)) for s in
                               tax_brackets_result_one
                               }

        brackets_tax_year_2 = {(float(s.income_min), float(s.income_max) if s.income_max else float('inf')):
                                   (float(s.rate), float(s.base_income), float(s.base_tax)) for s in
                               tax_brackets_result_two
                               }

        surcharge_rates = {"2024-2025": 0.10, "2025-2026": 0.09}

        # Pick surcharge if year exists, otherwise 0
        surcharge_year_1 = surcharge_rates.get(tax_year_1, 0)
        surcharge_year_2 = surcharge_rates.get(tax_year_2, 0)
        print(surcharge_year_1, surcharge_year_2)

        surcharge_label_1 = f"Surcharge {int(surcharge_year_1 * 100)}%" if surcharge_year_1 else None
        surcharge_label_2 = f"Surcharge {int(surcharge_year_2 * 100)}%" if surcharge_year_2 else None

        print(surcharge_label_1, surcharge_label_2)

        tax_year_1_result = calculate_tax(yearly_income, brackets_tax_year_1, surcharge_year_1)  # 10% surcharge
        tax_year_2_result = calculate_tax(yearly_income, brackets_tax_year_2, surcharge_year_2)  # 9% surcharge

        context = {
            'taxpayer_type': taxpayer_type,
            'tax_year_1': tax_year_1,
            'tax_year_2': tax_year_2,
            'tax_year_1_result': tax_year_1_result,
            'tax_year_2_result': tax_year_2_result,
            'monthly_income': int(yearly_income / 12),
            'yearly_income': yearly_income,
            'surcharge_label_1': surcharge_label_1,
            'surcharge_label_2': surcharge_label_2
        }
        print(context)
        return context
    except Exception as e:
        print(f'Error is :  {e}')
        return HttpResponse(f"Error: {str(e)}")


def calculate_tax(income, tax_brackets, surcharge_rate):
    try:
        print(surcharge_rate)
        surcharge_threshold = 10000000  # 10 million

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

                month = round(tax / 12)
                surcharge = 0
                total_tax_with_surcharge = tax

                if income > surcharge_threshold:
                    surcharge = round(tax * surcharge_rate)
                    total_tax_with_surcharge = tax + surcharge
                    month = round(total_tax_with_surcharge / 12)

                return {
                    'income': income,
                    'lower': lower,
                    'upper': upper,
                    'base_threshold': base_threshold,
                    'fixed_tax': fixed_tax,
                    'amount_exceeding': amount_exceeding,
                    'rate': rate * 100,
                    'tax_on_exceeding': round(tax_on_exceeding),
                    'total_tax': tax,
                    'per_month': month,
                    'total_tax_with_surcharge': total_tax_with_surcharge,
                    'surcharge': surcharge
                }
        return None
    except Exception as e:
        print(str(e))


from django.shortcuts import render
from .models import Question


def tax_knowledge_quiz(request):
    questions = (
        Question.objects
        .filter(is_active=True)
        .select_related("category")
        .prefetch_related("options")
        .order_by("category__order", "id")
    )

    return render(
        request,
        "tax-knowledge-quizz.html",
        {
            "questions": questions,
        }
    )

def online_services(request):
    try:
        return render(request, "partials/online_services.html")
    except Exception as e:
        return HttpResponse("Exception  :" + str(e))


def question_list(request):
    try:
        questions = Question.objects.prefetch_related("options").order_by("-updated_at")
        return render(request, "tax-knowledge-quizz.html", {"questions": questions})
    except Exception as e:
        return HttpResponse("Exception at Blog Details Page :" + str(e))

@login_required(login_url='Login')
def add_question(request):
    if request.method == "POST":
        question_text = request.POST.get("question_text")
        category = request.POST.get("category")
        explanation = request.POST.get("explanation")
        section_ref = request.POST.get("section_ref", "")
        difficulty = request.POST.get("difficulty", "basic")
        is_active = True if request.POST.get("is_active") else False

        options = request.POST.getlist("options[]")
        correct_index = request.POST.get("correct_option")

        # Validation
        if not question_text or not category or not explanation:
            messages.error(request, "Please fill all required fields.")
            return redirect("questions-add")

        if correct_index in [None, ""]:
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
            is_active=is_active
        )

        for i, opt in enumerate(options):
            Option.objects.create(
                question=question,
                option_text=opt,
                is_correct=(str(i) == correct_index)
            )

        messages.success(request, "Question added successfully.")
        return redirect("questions-add")

    # IMPORTANT: pass question & options
    return render(
        request,
        "Cpanel/question.html",
        {
            "url": "questions-add",
            "id": "",
            "question": None,
            "options": []
        }
    )



@login_required(login_url='Login')  # redirect when user is not logged in
def view_questions(request):
    questions = Question.objects.all().order_by("category", "id")
    return render(request, "Cpanel/view_questions.html", {"questions": questions})


@login_required(login_url='Login')
def edit_question(request, pk):
    question = get_object_or_404(Question, pk=pk)
    options = list(question.options.all())

    if request.method == "POST":
        question.question_text = request.POST.get("question_text")
        question.category = request.POST.get("category")
        question.explanation = request.POST.get("explanation")
        question.section_ref = request.POST.get("section_ref", "")
        question.difficulty = request.POST.get("difficulty", "basic")
        question.is_active = True if request.POST.get("is_active") else False
        question.save()

        option_texts = request.POST.getlist("options[]")
        correct_index = request.POST.get("correct_option")

        for i, opt in enumerate(options):
            if i < len(option_texts):
                opt.option_text = option_texts[i]
                opt.is_correct = (str(i) == correct_index)
                opt.save()

        messages.success(request, "Question updated successfully.")
        return redirect("view-questions")

    return render(
        request,
        "Cpanel/question.html",
        {
            "question": question,
            "options": options,
            "url": "questions-edit",
            "id": question.id
        }
    )



# DELETE QUESTION
@login_required(login_url='Login')
def delete_question(request, pk):
    question = get_object_or_404(Question, pk=pk)
    question.delete()
    messages.success(request, "Question deleted successfully.")
    return redirect("questions-list")


def privacy_policy(request):
    try:
        return render(request, 'partials/privacy_policy.html')

    except Exception as e:
        return HttpResponse(str("Exception : " + str(e)))


def terms_and_conditions(request):
    try:
        return render(request, 'partials/terms_conditions.html')

    except Exception as e:
        return HttpResponse(str("Exception : " + str(e)))
