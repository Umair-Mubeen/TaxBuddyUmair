import mimetypes
from datetime import timezone
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, request
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.utils.text import slugify
from django.contrib import messages

from .models import Blogs, Comment, Contact, TaxBracket


def index(request):
    try:
        result = Blogs.objects.filter(status=1, is_deleted=False)
        return render(request, 'index.html', {'result': result})
    except Exception as e:
        return HttpResponse(str(e))


def Login(request):
    try:
        if request.method == 'POST':
            username = request.POST['username']
            pwd = request.POST['password']
            user = authenticate(request, username=username, password=pwd)
            if user:
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


def AddEditBlog(request, slug=None):
    try:
        result = {'title': '', 'type': '', 'description': ''}
        if slug:
            result = get_object_or_404(Blogs, slug=slug, status=1, is_deleted=False)

        if request.method == 'POST':
            type = request.POST['type']
            title = request.POST['title']
            description = request.POST['description']
            image = request.FILES.get('attachment')
            new_slug = slugify(title)
            if slug:
                blog = get_object_or_404(Blogs, slug=slug, status=1, is_deleted=False)
                blog.type = type
                blog.title = title
                blog.slug = new_slug
                blog.description = description
                if image:
                    blog.image = image
                blog.save()
            else:
                # Validate uploaded file
                if not image:
                    return HttpResponse("No file uploaded.", status=400)

                file_type = mimetypes.guess_type(image.name)[0]
                if not file_type or (not file_type.startswith('image') and file_type != 'application/pdf'):
                    return HttpResponse("Uploaded file is not a valid image or PDF.", status=400)

                Blogs.objects.create(title=title, type=type, description=description, image=image, slug=new_slug)

        return render(request, 'Cpanel/AddEditBlog.html', {'result': result})
    except Exception as e:
        print('Exception at Add Edit Details Page :', str(e))
        return HttpResponse(str('Exception at Add Edit Details Page :' + str(e)))


def deleteBlog(request, slug=None):
    try:
        blogs = Blogs.objects.filter(status=1, slug=slug, is_deleted=False)
        for blog in blogs:
            blog.delete()
        return redirect('ManageBlogs')
    except Exception as e:
        print('Exception at Delete Details Page :', str(e))
        return HttpResponse(str('Exception at Delete Details Page :' + str(e)))


def ManageBlogs(request):
    try:
        result = Blogs.objects.filter(status=1, is_deleted=False)
        return render(request, 'Cpanel/ManageBlogs.html', {'result': result})
    except Exception as e:
        print('Exception at Manage Blog Page :', str(e))
        return HttpResponse(str('Exception at Manage Blog Page :' + str(e)))


def BlogDetails(request, slug=None):
    try:
        if slug:
            blog = get_object_or_404(Blogs, slug=slug, status=1, is_deleted=False)
            blogComments = Comment.objects.filter(status=1, slug=blog.slug)
            if not blogComments.exists():
                blogComments = {}
            blogList = Blogs.objects.filter(status=1, is_deleted=False).exclude(slug=slug)

        return render(request, 'partials/BlogDetails.html',
                      {'blog': blog, 'userComments': blogComments, 'length': len(blogComments), 'blogList': blogList})
    except Exception as e:
        print('Exception at Blog Details Page :', str(e))
        return HttpResponse(str('Exception at Blog Details Page :' + str(e)))


def userComments(request):
    try:
        if request.method == 'POST':
            user = request.POST['user']
            email = request.POST['email']
            comment = request.POST['comment']
            slug = request.POST['slug']
            print(slug)
            blog = get_object_or_404(Blogs, slug=slug)
            Comment.objects.create(blog=blog, name=user, email_address=email, comment=comment, slug=slug)
            return redirect(f'/BlogDetails/{slug}')  # or use reverse()

    except Exception as e:
        print('Exception :', str(e))
        return HttpResponse(str(e))


def contact(request):
    try:
        if request.method == 'POST':
            first_name = request.POST['first_name']
            last_name = request.POST['last_name']
            phone_number = request.POST['phone_number']
            email_address = request.POST['email_address']
            subject = request.POST['subject']
            additional_details = request.POST['additional_details']
            Contact.objects.create(first_name=first_name, last_name=last_name,
                                   phone_number=phone_number, email_address=email_address, subject=subject,
                                   additional_details=additional_details)
            messages.success(request, "Form submitted successfully!")

            return redirect('/')
    except Exception as e:
        print('Exception at Contact Page :', str(e))
        messages.error(request, f"Exception at Contact Page: {str(e)}")
        return redirect('/')


# def SalarySlab_old(request):
#     try:
#         if request.method == 'POST':
#             income_type = request.POST.get('income_type')  # 'monthly' or 'yearly'
#             income_amount = int(request.POST.get('income_amount'))  # Either monthly or yearly salary based on user
#             taxpayer_type = request.POST.get('taxpayer_type')  # Either monthly or yearly salary based on user type
#             print(taxpayer_type)
#
#             # If monthly income, convert it to yearly income
#             if income_type == 'Monthly':
#                 yearly_income = income_amount * 12
#                 print(yearly_income)
#             else:
#                 yearly_income = income_amount  # Already yearly income
#                 print(yearly_income)
#
#             # Define the tax brackets for 2023 and 2024
#             tax_brackets_2023_2024_salaried = {
#                 (0, 600000): (0, 0),
#                 (600001, 1200000): (0.025, 600000),
#                 (1200001, 2400000): (0.125, 15000),
#                 (2400001, 3600000): (0.225, 165000),
#                 (3600001, 6000000): (0.275, 435000),
#                 (6000001, float('inf')): (0.35, 1095000)
#             }
#
#             tax_brackets_2024_2025_salaried = {
#                 (0, 600000): (0, 0),
#                 (600001, 1200000): (0.05, 600000),
#                 (1200001, 2200000): (0.15, 30000),
#                 (2200001, 3200000): (0.25, 180000),
#                 (3200001, 4100000): (0.30, 430000),
#                 (4100001, float('inf')): (0.35, 700000)
#             }
#             tax_brackets_business_2023_2024 = {
#                 (0, 600000): (0, 0),
#                 (600001, 800000): (0.075, 600000),  # Slightly higher than salaried
#                 (800001, 1200000): (0.15, 15000),
#                 (1200001, 2400000): (0.2, 75000),
#                 (2400001, 3000000): (0.25, 315000),  # Higher bracket percentages
#                 (3000001, 4000000): (0.3, 465000),  # Adjusted for higher business earnings
#                 (4000001, float('inf')): (0.35, 765000)
#
#             }
#             tax_brackets_business_2024_2025 = {
#                 (0, 600000): (0, 0),
#                 (600001, 1200000): (0.15, 600000),  # Slightly higher than salaried
#                 (1200001, 1600000): (0.2, 90000),
#                 (1600001, 3200000): (0.3, 170000),
#                 (3200001, 5600000): (0.4, 650000),  # Higher bracket percentages
#                 (5600001, float('inf')): (0.45, 1610000)
#             }
#
#
#             apply_surcharge_2023 = False
#             apply_surcharge_2024 = True
#
#             # Calculate taxes for both 2023 and 2024 based on yearly income
#             if taxpayer_type == 'salaried':
#                 tax_2023 = calculate_tax(yearly_income, tax_brackets_2023_2024_salaried, apply_surcharge_2023)
#                 print('tax_2023', tax_2023)
#
#                 tax_2024 = calculate_tax(yearly_income, tax_brackets_2024_2025_salaried, apply_surcharge_2024)
#             if taxpayer_type == 'business':
#                 tax_2023 = calculate_tax(yearly_income, tax_brackets_business_2023_2024, apply_surcharge_2023)
#                 tax_2024 = calculate_tax(yearly_income, tax_brackets_business_2024_2025, apply_surcharge_2024)
#
#             # Calculate the percentage tax and growth between 2023 and 2024
#             if yearly_income == 0:
#                 tax_2023_percentage = 0
#                 tax_2024_percentage = 0
#             else:
#                 tax_2023_percentage = (tax_2023['total_tax'] / yearly_income) * 100 if tax_2023['total_tax'] > 0 else 0
#                 tax_2024_percentage = (tax_2024['total_tax'] / yearly_income) * 100 if tax_2024['total_tax'] > 0 else 0
#
#                 if tax_2023_percentage > 0 and tax_2024_percentage > 0:
#                     growth_percentage = ((tax_2024_percentage - tax_2023_percentage) / tax_2023_percentage) * 100
#                     growth_percentage = round(growth_percentage, 2)
#                 else:
#                     growth_percentage = 0
#
#             # Prepare the context for the template
#             context = {
#                 'tax_2023_year': '2023 - 2024',
#                 'tax_2024_year': '2024 - 2025',
#                 'tax_2023': tax_2023,
#                 'tax_2024': tax_2024,
#                 'tax_2023_percentage': tax_2023_percentage,
#                 'tax_2024_percentage': tax_2024_percentage,
#                 'yearly_income': yearly_income,
#                 'monthly_income': income_amount if income_type == 'Monthly' else yearly_income,
#                 'growth_percentage': growth_percentage,
#                 'income_type': income_type,
#                 'taxpayer_type': taxpayer_type
#             }
#             print(context)
#             return render(request, 'partials/salary_slab.html', context=context)
#
#         context = {
#             'tax_2023_year': '2023 - 2024',
#             'tax_2024_year': '2024 - 2025',
#             'tax_2023': '',
#             'tax_2024': '',
#             'tax_2023_percentage': '',
#             'tax_2024_percentage': '',
#             'yearly_income': '',
#             'growth_percentage': '',
#             'income_type': '',
#             'taxpayer_type': ''
#
#         }
#         return render(request, 'partials/salary_slab.html',context=context)
#     except Exception as e:
#         print("Exception at Salary Slab Page :", str(e))
#         return HttpResponse('Exception at Salary Slab Page')
#
#
# def calculate_tax_old(income, tax_brackets,apply_surcharge):
#     try:
#         surcharge_threshold = 10000000
#         surcharge_rate = 0.10
#         for (lower, upper), (rate, base_tax) in tax_brackets.items():
#             if lower <= income <= upper:
#                 month = 0
#                 if rate == 0:
#                     tax = 0
#                 else:
#                     amount_exceeding = income - lower
#                     tax_on_exceeding = amount_exceeding * rate
#                     print(tax_on_exceeding)
#
#                     if lower == 600001 and upper == 1200000:
#                         tax = round(tax_on_exceeding)  # No base tax added
#                         month = round(tax / 12)
#                     elif lower == 600001 and upper == 800000:
#                         tax = round(tax_on_exceeding)  # No base tax added
#                         month = tax / 12
#
#                     else:
#                         tax = round(base_tax + tax_on_exceeding)
#
#                         month = round(tax / 12)
#                 total_tax_with_surcharge = 0
#                 surcharge = 0
#                 if apply_surcharge and income > surcharge_threshold:
#                     surcharge = round(tax * surcharge_rate)
#                     print("Tax Before 10% surcharge", str(tax))
#                     print("Surcharge 10% (Base Tax + Tax on Exceeding amount)", str(surcharge))
#                     print(f"{tax} + {surcharge} = {tax + surcharge}")
#                     tax = tax + surcharge
#                     total_tax_with_surcharge = round(tax)
#                     print("tax + surcharge", str(total_tax_with_surcharge))
#                     month = round(total_tax_with_surcharge / 12)
#
#                 return {
#                         'income': income,
#                         'lower': lower,
#                         'upper': upper,
#                         'base_tax': base_tax,
#                         'amount_exceeding': amount_exceeding if rate != 0 else 0,
#                         'rate': rate * 100,
#                         'tax_on_exceeding': round(tax_on_exceeding) if rate != 0 else 0,
#                         'total_tax': tax,
#                         'per_month' : month,
#                         'total_tax_with_surcharge' : total_tax_with_surcharge,
#                         'surcharge' : surcharge
#                     }
#         return None
#     except Exception as e:
#         print(str(e))


def AOPCalculator(request):
    try:
        if request.method == 'POST':
            # Get inputs
            income_type = request.POST.get('income_type')  # 'Monthly' or 'Yearly'
            income_amount = int(request.POST.get('income_amount'))
            taxpayer_type = request.POST.get('taxpayer_type')  # 'business'

            if income_type == 'Monthly':
                yearly_income = income_amount * 12
                print(yearly_income)
            else:
                yearly_income = income_amount  # Already yearly income
                print(yearly_income)

            tax_brackets_business_2023_2024 = {
                (0, 600000): (0, 0, 0),
                (600001, 800000): (0.075, 600000, 0),
                (800001, 1200000): (0.15, 800000, 15000),
                (1200001, 2400000): (0.2, 1200000, 75000),
                (2400001, 3000000): (0.25, 2400000, 315000),
                (3000001, 4000000): (0.3, 3000000, 465000),
                (4000001, float('inf')): (0.35, 4000000, 765000)
            }

            tax_brackets_business_2024_2025 = {
                (0, 600000): (0, 0, 0),
                (600001, 1200000): (0.15, 600000, 0),
                (1200001, 1600000): (0.20, 1200000, 90000),
                (1600001, 3200000): (0.30, 1600000, 170000),
                (3200001, 5600000): (0.40, 3200000, 650000),
                (5600001, float('inf')): (0.45, 5600000, 1610000)
            }

            # Calculate tax for both years
            tax_2023_2024 = calculate_tax(yearly_income, tax_brackets_business_2023_2024, 0)  # 0% surcharge
            tax_2025_2026 = calculate_tax(yearly_income, tax_brackets_business_2024_2025, 0.10)  # 10% surcharge

            # Tax percentages
            tax_2023_2024_percentage = (tax_2023_2024['total_tax'] / yearly_income) * 100 if yearly_income > 0 else 0
            tax_2025_2026_percentage = (tax_2025_2026['total_tax'] / yearly_income) * 100 if yearly_income > 0 else 0
            growth_percentage = ((tax_2025_2026_percentage - tax_2023_2024_percentage) / tax_2023_2024_percentage * 100
                                 if tax_2023_2024_percentage > 0 else 0)

            # Template context
            context = {
                'taxpayer_type': taxpayer_type,
                'tax_2023_2024_year': '2023 - 2024',
                'tax_2025_2026_year': '2024 - 2025',
                'tax_2023_2024': tax_2023_2024,
                'tax_2025_2026': tax_2025_2026,
                'monthly_income': int(income_amount) if income_type == 'Monthly' else int(yearly_income / 12),
                'tax_2024_2025_percentage': round(tax_2023_2024_percentage, 2),
                'tax_2025_2026_percentage': round(tax_2025_2026_percentage, 2),
                'yearly_income': yearly_income,
                'growth_percentage': round(growth_percentage, 2),
                'income_type': income_type,
            }
            return render(request, 'partials/aop_slab.html', context)

        # GET request (empty form)
        else:
            context = {
                'taxpayer_type': 'AOP',
                'tax_2023_2024_year': '2023 - 2024',
                'tax_2025_2026_year': '2024 - 2025',
                'tax_2023_2024': '',
                'tax_2025_2026': '',
                'monthly_income': '',
                'tax_2023_2024_percentage': '',
                'tax_2025_2026_percentage': '',
                'yearly_income': '',
                'growth_percentage': '',
                'income_type': '',
            }
        print(context)
        return render(request, 'partials/aop_slab.html', context)

    except Exception as e:
        print(str(e))
        return HttpResponse(str(e))


def BusinessCalculator(request):
    try:
        if request.method == 'POST':
            # Get inputs
            income_type = request.POST.get('income_type')  # 'Monthly' or 'Yearly'
            income_amount = int(request.POST.get('income_amount'))
            taxpayer_type = request.POST.get('taxpayer_type')  # 'business'

            # Convert monthly to yearly if needed
            if income_type == 'Monthly':
                yearly_income = income_amount * 12
                print(yearly_income)
            else:
                yearly_income = income_amount  # Already yearly income
                print(yearly_income)

            tax_brackets_business_2023_2024 = {
                (0, 600000): (0, 0, 0),
                (600001, 800000): (0.075, 600000, 0),
                (800001, 1200000): (0.15, 800000, 15000),
                (1200001, 2400000): (0.2, 1200000, 75000),
                (2400001, 3000000): (0.25, 2400000, 315000),
                (3000001, 4000000): (0.3, 3000000, 465000),
                (4000001, float('inf')): (0.35, 4000000, 765000)
            }

            tax_brackets_business_2024_2025 = {
                (0, 600000): (0, 0, 0),
                (600001, 1200000): (0.15, 600000, 0),
                (1200001, 1600000): (0.20, 1200000, 90000),
                (1600001, 3200000): (0.30, 1600000, 170000),
                (3200001, 5600000): (0.40, 3200000, 650000),
                (5600001, float('inf')): (0.45, 5600000, 1610000)
            }

            # Calculate tax for both years
            tax_2023_2024 = calculate_tax(yearly_income, tax_brackets_business_2023_2024, 0)  # 0% surcharge
            tax_2025_2026 = calculate_tax(yearly_income, tax_brackets_business_2024_2025, 0.10)  # 10% surcharge

            # Tax percentages
            tax_2023_2024_percentage = (tax_2023_2024['total_tax'] / yearly_income) * 100 if yearly_income > 0 else 0
            tax_2025_2026_percentage = (tax_2025_2026['total_tax'] / yearly_income) * 100 if yearly_income > 0 else 0
            growth_percentage = ((tax_2025_2026_percentage - tax_2023_2024_percentage) / tax_2023_2024_percentage * 100
                                 if tax_2023_2024_percentage > 0 else 0)

            # Template context
            context = {
                'taxpayer_type': taxpayer_type,
                'tax_2023_2024_year': '2023 - 2024',
                'tax_2025_2026_year': '2024 - 2025',
                'tax_2023_2024': tax_2023_2024,
                'tax_2025_2026': tax_2025_2026,
                'monthly_income': int(income_amount) if income_type == 'Monthly' else int(yearly_income / 12),
                'tax_2024_2025_percentage': round(tax_2023_2024_percentage, 2),
                'tax_2025_2026_percentage': round(tax_2025_2026_percentage, 2),
                'yearly_income': yearly_income,
                'growth_percentage': round(growth_percentage, 2),
                'income_type': income_type,
            }
            return render(request, 'partials/business_slab.html', context)

        # GET request (empty form)
        else:
            context = {
                'taxpayer_type': 'Business Individual',
                'tax_2023_2024_year': '2023 - 2024',
                'tax_2025_2026_year': '2024 - 2025',
                'tax_2023_2024': '',
                'tax_2025_2026': '',
                'monthly_income': '',
                'tax_2023_2024_percentage': '',
                'tax_2025_2026_percentage': '',
                'yearly_income': '',
                'growth_percentage': '',
                'income_type': '',
            }
        print(context)
        return render(request, 'partials/business_slab.html', context)

    except Exception as e:
        print(str(e))
        return HttpResponse(str(e))


def SalaryCalculator(request):
    try:
        if request.method == 'POST':
            # Get inputs
            tax_year_1 = request.POST.get('tax_year_1')  # 'Monthly' or 'Yearly'
            tax_year_2 = request.POST.get('tax_year_2')  # 'Monthly' or 'Yearly'
            income_amount = int(request.POST.get('income_amount'))
            taxpayer_type = request.POST.get('taxpayer_type')  # 'salaried'

            # Convert monthly to yearly if needed
            yearly_income = income_amount * 12

            # Tax brackets format: (rate, base_threshold, fixed_tax)
            # tax_brackets_2024_2025_salaried = {
            #     (0, 600000): (0.00, 0, 0),
            #     (600001, 1200000): (0.05, 600000, 0),
            #     (1200001, 2200000): (0.15, 1200000, 30000),
            #     (2200001, 3200000): (0.25, 2200000, 180000),
            #     (3200001, 4100000): (0.30, 3200000, 430000),
            #     (4100001, float('inf')): (0.35, 4100000, 700000)
            # }
            #
            # tax_brackets_2025_2026_salaried = {
            #     (0, 600000): (0.00, 0, 0),
            #     (600001, 1200000): (0.01, 600000, 0),
            #     (1200001, 2200000): (0.11, 1200000, 6000),
            #     (2200001, 3200000): (0.23, 2200000, 116000),
            #     (3200001, 4100000): (0.30, 3200000, 346000),
            #     (4100001, float('inf')): (0.35, 4100000, 616000)
            # }

            # Fetch tax slabs from DB for each selected year
            tax_brackets_result_one = TaxBracket.objects.filter(year=tax_year_1)
            tax_brackets_result_two = TaxBracket.objects.filter(year=tax_year_2)

            # Convert DB rows to dicts
            brackets_tax_year_1 = {
                (float(s.income_min), float(s.income_max) if s.income_max else float('inf')):
                    (float(s.rate), float(s.base_income), float(s.base_tax))
                for s in tax_brackets_result_one
            }

            brackets_tax_year_2 = {
                (float(s.income_min), float(s.income_max) if s.income_max else float('inf')):
                    (float(s.rate), float(s.base_income), float(s.base_tax))
                for s in tax_brackets_result_two
            }

            surcharge_rates = {
                "2024-2025": 0.10,
                "2025-2026": 0.09,
            }

            # Pick surcharge if year exists, otherwise 0
            surcharge_year_1 = surcharge_rates.get(tax_year_1, 0)
            surcharge_year_2 = surcharge_rates.get(tax_year_2, 0)

            tax_2024_2025 = calculate_tax(yearly_income, brackets_tax_year_1, surcharge_year_1)  # 10% surcharge
            tax_2025_2026 = calculate_tax(yearly_income, brackets_tax_year_2, surcharge_year_2)  # 9% surcharge

            # Tax percentages
            tax_2024_2025_percentage = (tax_2024_2025['total_tax'] / yearly_income) * 100 if yearly_income > 0 else 0
            tax_2025_2026_percentage = (tax_2025_2026['total_tax'] / yearly_income) * 100 if yearly_income > 0 else 0
            growth_percentage = ((tax_2025_2026_percentage - tax_2024_2025_percentage) / tax_2024_2025_percentage * 100
                                 if tax_2024_2025_percentage > 0 else 0)

            # Template context
            context = {
                'tax_2024_2025_year': tax_year_1,
                'tax_2025_2026_year': tax_year_2,
                'tax_2024_2025': tax_2024_2025,
                'tax_2025_2026': tax_2025_2026,
                'monthly_income': income_amount,
                'tax_2024_2025_percentage': round(tax_2024_2025_percentage, 2),
                'tax_2025_2026_percentage': round(tax_2025_2026_percentage, 2),
                'yearly_income': yearly_income,
                'growth_percentage': round(growth_percentage, 2),
                'taxpayer_type': taxpayer_type,
                'surcharge_year_1' : surcharge_year_1 * 100,
                'surcharge_year_2' : surcharge_year_2 * 100
            }
            return render(request, 'partials/salary_slab.html', context)

        # GET request (empty form)
        context = {
            'tax_2024_2025_year': '2024 - 2025',
            'tax_2025_2026_year': '2025 - 2026',
            'tax_2024_2025': '',
            'tax_2025_2026': '',
            'monthly_income': '',
            'tax_2024_2025_percentage': '',
            'tax_2025_2026_percentage': '',
            'yearly_income': '',
            'growth_percentage': '',
            'taxpayer_type': '',
            'surcharge_year_1': '',
            'surcharge_year_2': ''

        }
        return render(request, 'partials/salary_slab.html', context)

    except Exception as e:
        print(str(e))
        return HttpResponse(str(e))


def calculate_tax(income, tax_brackets, surcharge_rate):
    try:
        surcharge_threshold = 10000000  # 10 million
        print('business :', income)
        print('tax brackets :', tax_brackets.items())

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


def PropertyCalculator(request):
    try:
        if request.method == 'POST':
            # Convert all numeric inputs to float
            gross_rent = int(request.POST.get('gross_rent', 0))

            # Deduction fields
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

            print(irrecoverable_rent)
            # Total deductions
            total_deductions = (
                    repairs_allowance + insurance_premium + local_taxes +
                    ground_rent + borrowed_interest + hbfc_payments +
                    mortgage_interest + admin_expenses + legal_expenses + irrecoverable_rent
            )
            print(total_deductions)

            # Net rental income
            net_rental_income = gross_rent - total_deductions
            print('net_rental_income', round(net_rental_income))
            # Tax calculation based on slabs
            if net_rental_income <= 300000:
                tax = 0

            elif net_rental_income > 300000 and net_rental_income <= 600000:
                tax = 0.05 * (net_rental_income - 300000)
                print(f'gross rent greater than {300000} :', tax)

            elif net_rental_income > 600000 and net_rental_income <= 2000000:
                tax = 15000 + 0.10 * (net_rental_income - 600000)
                print(f'gross rent greater than {600000} :', tax)

            else:
                tax = 155000 + 0.25 * (net_rental_income - 2000000)
                print(f'gross rent greater than {net_rental_income} :', tax)

            # Pass data to template
            context = {
                'gross_rent': round(gross_rent),
                'total_deductions': round(total_deductions),
                'net_rent': round(net_rental_income),
                'tax': round(tax)
            }
            print(context)

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

            TaxBracket.objects.create(
                year=tax_year,income_min=income_min,income_max=None if income_max == float('inf') else income_max,
                rate=Decimal(str(rate)), base_income=base_income,base_tax=base_tax)
            return render(request, 'Cpanel/add_salary_tax_brackets.html')

        else:
            return render(request, 'Cpanel/add_salary_tax_brackets.html')
    except Exception as e:
        print(f'Error {e}')
        return HttpResponse(f"Error: {str(e)}")
