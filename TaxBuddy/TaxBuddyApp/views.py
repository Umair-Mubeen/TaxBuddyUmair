from django.http import HttpResponse
from django.shortcuts import render


def index(request):
    try:
        print('TaxBuddy Umair')
        return render(request,'index.html')
    except Exception as e:
        return HttpResponse(str(e))


def Contact(request):
    try:
        return render(request,'contact.html')
    except Exception as e:
        return HttpResponse(str(e))


def TaxCalculator(request):
    try:
        if request.method == 'POST':
            income_type = request.POST.get('income_type')  # 'monthly' or 'yearly'
            income_amount = int(request.POST.get('income_amount'))  # Either monthly or yearly salary based on user
            taxpayer_type = request.POST.get('taxpayer_type')  # Either monthly or yearly salary based on user type
            print(taxpayer_type)

            # If monthly income, convert it to yearly income
            if income_type == 'Monthly':
                yearly_income = income_amount * 12
                print(yearly_income)
            else:
                yearly_income = income_amount  # Already yearly income
                print(yearly_income)

            # Define the tax brackets for 2023 and 2024
            tax_brackets_2023_2024_salaried = {
                (0, 600000): (0, 0),
                (600001, 1200000): (0.025, 600000),
                (1200001, 2400000): (0.125, 15000),
                (2400001, 3600000): (0.225, 165000),
                (3600001, 6000000): (0.275, 435000),
                (6000001, float('inf')): (0.35, 1095000)
            }

            tax_brackets_2024_2025_salaried = {
                (0, 600000): (0, 0),
                (600001, 1200000): (0.05, 600000),
                (1200001, 2200000): (0.15, 30000),
                (2200001, 3200000): (0.25, 180000),
                (3200001, 4100000): (0.30, 430000),
                (4100001, float('inf')): (0.35, 700000)
            }
            tax_brackets_business_2023_2024 = {
                (0, 600000): (0, 0),
                (600001, 800000): (0.075, 600000),  # Slightly higher than salaried
                (800001, 1200000): (0.15, 15000),
                (1200001, 2400000): (0.2, 75000),
                (2400001, 3000000): (0.25, 315000),  # Higher bracket percentages
                (3000001, 4000000): (0.3, 465000),  # Adjusted for higher business earnings
                (4000001, float('inf')): (0.35, 765000)

            }
            tax_brackets_business_2024_2025 = {
                (0, 600000): (0, 0),
                (600001, 1200000): (0.15, 600000),  # Slightly higher than salaried
                (1200001, 1600000): (0.2, 90000),
                (1600001, 3200000): (0.3, 170000),
                (3200001, 5600000): (0.4, 650000),  # Higher bracket percentages
                (5600001, float('inf')): (0.45, 1610000)
            }

            apply_surcharge_2023 = False
            apply_surcharge_2024 = True

            # Calculate taxes for both 2023 and 2024 based on yearly income
            if taxpayer_type == 'salaried':
                tax_2023 = calculate_tax(yearly_income, tax_brackets_2023_2024_salaried, apply_surcharge_2023)
                tax_2024 = calculate_tax(yearly_income, tax_brackets_2024_2025_salaried, apply_surcharge_2024)
            if taxpayer_type == 'business':
                tax_2023 = calculate_tax(yearly_income, tax_brackets_business_2023_2024, apply_surcharge_2023)
                tax_2024 = calculate_tax(yearly_income, tax_brackets_business_2024_2025, apply_surcharge_2024)

            # Calculate the percentage tax and growth between 2023 and 2024
            if yearly_income == 0:
                tax_2023_percentage = 0
                tax_2024_percentage = 0
            else:
                tax_2023_percentage = (tax_2023['total_tax'] / yearly_income) * 100 if tax_2023['total_tax'] > 0 else 0
                tax_2024_percentage = (tax_2024['total_tax'] / yearly_income) * 100 if tax_2024['total_tax'] > 0 else 0

                if tax_2023_percentage > 0 and tax_2024_percentage > 0:
                    growth_percentage = ((tax_2024_percentage - tax_2023_percentage) / tax_2023_percentage) * 100
                    growth_percentage = round(growth_percentage, 2)
                else:
                    growth_percentage = 0

            # Prepare the context for the template
            context = {
                'tax_2023_year': '2023 - 2024',
                'tax_2024_year': '2024 - 2025',
                'tax_2023': tax_2023,
                'tax_2024': tax_2024,
                'tax_2023_percentage': tax_2023_percentage,
                'tax_2024_percentage': tax_2024_percentage,
                'yearly_income': yearly_income,
                'monthly_income': income_amount if income_type == 'Monthly' else yearly_income,
                'growth_percentage': growth_percentage,
                'income_type': income_type,
                'taxpayer_type': taxpayer_type
            }
            return render(request, 'TaxCalculator.html', context)

            # Render an empty form when the page is loaded initially
        context = {
            'tax_2023_year': '2023 - 2024',
            'tax_2024_year': '2024 - 2025',
            'tax_2023': '',
            'tax_2024': '',
            'tax_2023_percentage': '',
            'tax_2024_percentage': '',
            'yearly_income': '',
            'growth_percentage': '',
            'income_type': '',
            'taxpayer_type': ''

        }

        return render(request,'TaxCalculator.html',context)
    except Exception as e:
        return HttpResponse(str(e))




def TaxSlab(request):
    try:
        if request.method == 'POST':
            income_type = request.POST.get('income_type')  # 'monthly' or 'yearly'
            income_amount = int(request.POST.get('income_amount'))  # Either monthly or yearly salary based on user
            taxpayer_type = request.POST.get('taxpayer_type')  # Either monthly or yearly salary based on user type
            print(taxpayer_type)

            # If monthly income, convert it to yearly income
            if income_type == 'Monthly':
                yearly_income = income_amount * 12
                print(yearly_income)
            else:
                yearly_income = income_amount  # Already yearly income
                print(yearly_income)

            # Define the tax brackets for 2023 and 2024
            tax_brackets_2023_2024_salaried = {
                (0, 600000): (0, 0),
                (600001, 1200000): (0.025, 600000),
                (1200001, 2400000): (0.125, 15000),
                (2400001, 3600000): (0.225, 165000),
                (3600001, 6000000): (0.275, 435000),
                (6000001, float('inf')): (0.35, 1095000)
            }

            tax_brackets_2024_2025_salaried = {
                (0, 600000): (0, 0),
                (600001, 1200000): (0.05, 600000),
                (1200001, 2200000): (0.15, 30000),
                (2200001, 3200000): (0.25, 180000),
                (3200001, 4100000): (0.30, 430000),
                (4100001, float('inf')): (0.35, 700000)
            }
            tax_brackets_business_2023_2024 = {
                (0, 600000): (0, 0),
                (600001, 800000): (0.075, 600000),  # Slightly higher than salaried
                (800001, 1200000): (0.15, 15000),
                (1200001, 2400000): (0.2, 75000),
                (2400001, 3000000): (0.25, 315000),  # Higher bracket percentages
                (3000001, 4000000): (0.3, 465000),  # Adjusted for higher business earnings
                (4000001, float('inf')): (0.35, 765000)

            }
            tax_brackets_business_2024_2025 = {
                (0, 600000): (0, 0),
                (600001, 1200000): (0.15, 600000),  # Slightly higher than salaried
                (1200001, 1600000): (0.2, 90000),
                (1600001, 3200000): (0.3, 170000),
                (3200001, 5600000): (0.4, 650000),  # Higher bracket percentages
                (5600001, float('inf')): (0.45, 1610000)
            }

            apply_surcharge_2023 = False
            apply_surcharge_2024 = True

            # Calculate taxes for both 2023 and 2024 based on yearly income
            if taxpayer_type == 'salaried':
                tax_2023 = calculate_tax(yearly_income, tax_brackets_2023_2024_salaried, apply_surcharge_2023)
                tax_2024 = calculate_tax(yearly_income, tax_brackets_2024_2025_salaried, apply_surcharge_2024)
            if taxpayer_type == 'business':
                tax_2023 = calculate_tax(yearly_income, tax_brackets_business_2023_2024, apply_surcharge_2023)
                tax_2024 = calculate_tax(yearly_income, tax_brackets_business_2024_2025, apply_surcharge_2024)

            # Calculate the percentage tax and growth between 2023 and 2024
            if yearly_income == 0:
                tax_2023_percentage = 0
                tax_2024_percentage = 0
            else:
                tax_2023_percentage = (tax_2023['total_tax'] / yearly_income) * 100 if tax_2023['total_tax'] > 0 else 0
                tax_2024_percentage = (tax_2024['total_tax'] / yearly_income) * 100 if tax_2024['total_tax'] > 0 else 0

                if tax_2023_percentage > 0 and tax_2024_percentage > 0:
                    growth_percentage = ((tax_2024_percentage - tax_2023_percentage) / tax_2023_percentage) * 100
                    growth_percentage = round(growth_percentage, 2)
                else:
                    growth_percentage = 0

            # Prepare the context for the template
            context = {
                'tax_2023_year': '2023 - 2024',
                'tax_2024_year': '2024 - 2025',
                'tax_2023': tax_2023,
                'tax_2024': tax_2024,
                'tax_2023_percentage': tax_2023_percentage,
                'tax_2024_percentage': tax_2024_percentage,
                'yearly_income': yearly_income,
                'monthly_income': income_amount if income_type == 'Monthly' else yearly_income,
                'growth_percentage': growth_percentage,
                'income_type': income_type,
                'taxpayer_type': taxpayer_type
            }
            return render(request, 'TaxSlab.html', context)

        # Render an empty form when the page is loaded initially
        context = {
            'tax_2023_year': '2023 - 2024',
            'tax_2024_year': '2024 - 2025',
            'tax_2023': '',
            'tax_2024': '',
            'tax_2023_percentage': '',
            'tax_2024_percentage': '',
            'yearly_income': '',
            'growth_percentage': '',
            'income_type': '',
            'taxpayer_type': ''

        }
        return render(request, 'TaxSlab.html', context)

    except Exception as e:
        print(str(e))
        return HttpResponse(str(e))



def calculate_tax(income, tax_brackets, apply_surcharge):
    try:
        surcharge_threshold = 10000000
        surcharge_rate = 0.10
        for (lower, upper), (rate, base_tax) in tax_brackets.items():
            if lower <= income <= upper:
                month = 0
                if rate == 0:
                    tax = 0
                else:
                    amount_exceeding = income - lower
                    tax_on_exceeding = amount_exceeding * rate

                    if lower == 600001 and upper == 1200000:
                        tax = round(tax_on_exceeding)  # No base tax added
                        month = round(tax / 12)
                    elif lower == 600001 and upper == 800000:
                        tax = round(tax_on_exceeding)  # No base tax added
                        month = tax / 12

                    else:
                        tax = round(base_tax + tax_on_exceeding)
                        month = round(tax / 12)
                total_tax_with_surcharge = 0
                surcharge = 0
                if apply_surcharge and income > surcharge_threshold:
                    surcharge = round(tax * surcharge_rate)
                    total_tax_with_surcharge = round(tax + surcharge)
                    print('surcharge =>', surcharge)
                    month = round(total_tax_with_surcharge / 12)

                return {
                    'income': income,
                    'lower': lower,
                    'upper': upper,
                    'base_tax': base_tax,
                    'amount_exceeding': amount_exceeding if rate != 0 else 0,
                    'rate': rate * 100,
                    'tax_on_exceeding': round(tax_on_exceeding) if rate != 0 else 0,
                    'total_tax': tax,
                    'per_month': month,
                    'total_tax_with_surcharge': total_tax_with_surcharge,
                    'surcharge': surcharge
                }
        return None
    except Exception as e:
        print(str(e))