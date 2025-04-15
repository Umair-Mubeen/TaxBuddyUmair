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
        print('Contact')
        return render(request,'contact.html')
    except Exception as e:
        return HttpResponse(str(e))
