import mimetypes
from datetime import timezone
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, request
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.utils.text import slugify
from django.contrib import messages

from .models import Blogs, Comment, Contact, TaxBracket, Business_AOP_Slab,Property_Business_AOP_Slab


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

def AOPCalculator(request):
    try:
        if request.method == 'POST':
            income_type = request.POST.get('income_type')  # 'Monthly' or 'Yearly'
            income_amount = int(request.POST.get('income_amount'))
            tax_year_1 = request.POST.get('tax_year_1')  # 'Monthly' or 'Yearly'
            tax_year_2 = request.POST.get('tax_year_2')  # 'Monthly' or 'Yearly'

            if income_type == 'Monthly':
                yearly_income = income_amount * 12
            else:
                yearly_income = income_amount  # Already yearly income

            context = FetchResult(tax_year_1, tax_year_2, 'AOP', yearly_income)
            context.update({
                'income_type': income_type,
                'url': '/AOPCalculator',
                'title': 'AOP'
            })
            return render(request, 'partials/aop_slab.html', context)
        return render(request, 'partials/aop_slab.html',{'title' : 'AOP','url': '/AOPCalculator'})
    except Exception as e:
        print("Exception / Error at AOP Tax Calculator : " + str(e))
        return HttpResponse("Exception / Error at AOP Tax Calculator : " + str(e))


def BusinessCalculator(request):
    try:
        if request.method == 'POST':
            income_type = request.POST.get('income_type')  # 'Monthly' or 'Yearly'
            income_amount = int(request.POST.get('income_amount'))
            tax_year_1 = request.POST.get('tax_year_1')  # 'Monthly' or 'Yearly'
            tax_year_2 = request.POST.get('tax_year_2')  # 'Monthly' or 'Yearly'

            if income_type == 'Monthly':
                yearly_income = income_amount * 12
            else:
                yearly_income = income_amount  # Already yearly income

            context = FetchResult(tax_year_1, tax_year_2, 'Business Individual', yearly_income)
            context.update({
                'income_type' : income_type,
                'url': '/BusinessCalculator',
                'title': 'Business Individual'
            })
            return render(request, 'partials/business_slab.html', context)
        return render(request, 'partials/business_slab.html', {'title' : 'Business Individual','url' : '/BusinessCalculator'})

    except Exception as e:
        print("Exception / Error at Business Tax Calculator : " + str(e))
        return HttpResponse("Exception / Error at Business Tax Calculator : " + str(e))


def SalaryCalculator(request):
    try:
        if request.method == 'POST':
            tax_year_1 = request.POST.get('tax_year_1')  # 'Monthly' or 'Yearly'
            tax_year_2 = request.POST.get('tax_year_2')  # 'Monthly' or 'Yearly'
            income_type = request.POST.get('income_type')
            income_amount = int(request.POST.get('income_amount'))

            if income_type == 'Monthly':
                yearly_income = income_amount * 12
            else:
                yearly_income = income_amount  # Already yearly income

            context = FetchResult(tax_year_1, tax_year_2, 'Salary Individual', yearly_income)
            context.update({'income_type': income_type,'url': '/SalaryCalculator','title': 'Salary Individual'})
            return render(request, 'partials/salary_slab.html', context)
        return render(request, 'partials/salary_slab.html',{'title' : 'Salary Individual','url' : '/SalaryCalculator'})

    except Exception as e:
        print("Exception / Error at Salary Tax Calculator : " + str(e))
        return HttpResponse("Exception / Error at Salary Tax Calculator : " + str(e))


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
                'net_income_rental' : net_rental_income,
                'total_deductions' : total_deductions,
                'yearly_income' : yearly_income
            })
            #return HttpResponse(str(context))
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
                    year=tax_year,income_min=income_min,income_max=None if income_max == float('inf') else income_max,
                    rate=Decimal(str(rate)), base_income=base_income,base_tax=base_tax)
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
        elif taxpayer_type == 'Business Individual' or taxpayer_type == 'AOP' :
            tax_brackets_result_one = Business_AOP_Slab.objects.filter(year=tax_year_1)
            tax_brackets_result_two = Business_AOP_Slab.objects.filter(year=tax_year_2)
        else:
            tax_brackets_result_one = Property_Business_AOP_Slab.objects.filter(year=tax_year_1)
            tax_brackets_result_two = Property_Business_AOP_Slab.objects.filter(year=tax_year_2)

        brackets_tax_year_1 = { (float(s.income_min), float(s.income_max) if s.income_max else float('inf')):
                    (float(s.rate), float(s.base_income), float(s.base_tax)) for s in tax_brackets_result_one
        }

        brackets_tax_year_2 = { (float(s.income_min), float(s.income_max) if s.income_max else float('inf')):
                    (float(s.rate), float(s.base_income), float(s.base_tax)) for s in tax_brackets_result_two
        }

        surcharge_rates = { "2024-2025": 0.10, "2025-2026": 0.09}

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
