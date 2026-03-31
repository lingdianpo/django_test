from django.shortcuts import render
from django.http import HttpResponse

def notify(request):
    print(request.POST)
    return HttpResponse("POST Notify")
