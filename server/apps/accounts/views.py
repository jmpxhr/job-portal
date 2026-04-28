from django.http import HttpRequest
from django.shortcuts import render


def register(request: HttpRequest):
    return render(request, 'accounts/register.html')
