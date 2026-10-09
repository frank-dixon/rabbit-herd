from django.shortcuts import render


def index(request):
    if request.user.is_authenticated:
        return render(request, "home.html")
    return render(request, "landing.html")
