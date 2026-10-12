from django.conf import settings
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .forms import ComponentExampleForm


def index(request):
    if request.user.is_authenticated:
        return render(request, "home.html")
    return render(request, "landing.html")


@login_required
def account(request):
    """Who is signed in, password and passkey, and log out."""
    return render(request, "pages/account.html")


def components(request):
    """Show every partial. Staff only, or anyone while DEBUG is on."""
    if not settings.DEBUG and not request.user.is_staff:
        raise Http404()
    invalid = ComponentExampleForm(
        data={
            "name": "",
            "email": "not-an-email",
            "password": "",
            "notes": "",
            "status": "",
            "born": "yesterday",
        }
    )
    invalid.is_valid()
    return render(
        request,
        "pages/components.html",
        {
            "example_form": ComponentExampleForm(),
            "invalid_form": invalid,
            "list_items": ["Clover", "Thistle"],
            "empty_items": [],
            "table_columns": ["Name", "Sex"],
            "table_rows": [["Clover", "Doe"]],
            "empty_rows": [],
        },
    )
