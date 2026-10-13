import datetime

from django.conf import settings
from django.utils import timezone
from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .nav import THEME_SWATCHES

from .forms import ComponentExampleForm


def index(request):
    if request.user.is_authenticated:
        return render(request, "home.html", home_context(request.user))
    return render(request, "landing.html")


@login_required
def account(request):
    """Settings: appearance (theme, grid density), account, export, log out.
    The appearance form posts back here and works without JS."""
    user = request.user
    if request.method == "POST":
        theme = request.POST.get("ui_theme", user.ui_theme)
        density = request.POST.get("ui_density", user.ui_density)
        if theme in dict(user.THEMES) and density in dict(user.DENSITIES):
            user.ui_theme, user.ui_density = theme, density
            user.save(update_fields=["ui_theme", "ui_density"])
            if request.headers.get("X-Requested-With") == "fetch":
                return HttpResponse(status=204)
            messages.success(request, "Settings saved.")
        return redirect(request.POST.get("next") if url_has_allowed_host_and_scheme(request.POST.get("next", ""), {request.get_host()}) else "account")
    kinds = [("rabbits", "Rabbits"), ("litters", "Litters"), ("weights", "Weights"), ("shows", "Show results"), ("costs", "Costs")]
    themes = [
        {"key": key, "label": label, "swatch": THEME_SWATCHES[key], "current": key == user.ui_theme}
        for key, label in user.THEMES
    ]
    return render(request, "pages/account.html", {"export_kinds": kinds, "themes": themes})


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


def day_label(when, today):
    if when == today:
        return "Today"
    if when == today - datetime.timedelta(days=1):
        return "Yesterday"
    return f"{when:%b} {when.day}" + (f", {when.year}" if when.year != today.year else "")


def home_context(user, limit=8):
    """Only real data: herd counts by status and the latest things that
    happened (rabbits added, photos added, deaths, archiving)."""
    from rabbits.models import Rabbit, RabbitPhoto
    from rabbits.tasks import open_items

    today = timezone.localdate()
    rabbits = list(Rabbit.objects.filter(owner=user))
    live = [r for r in rabbits if r.archived_at is None]
    active = [r for r in live if r.status != Rabbit.Status.DECEASED]
    statuses = [
        {"label": label, "count": sum(1 for r in active if r.status == value), "value": value}
        for value, label in Rabbit.Status.choices if value != Rabbit.Status.DECEASED
    ]
    events = []
    for r in rabbits:
        events.append((timezone.localtime(r.created_at).date(), 3, f"Added {r.name} to the herd", "", r))
        if r.status == Rabbit.Status.DECEASED and r.death_date:
            events.append((r.death_date, 2, f"{r.name} died", r.death_cause, r))
        if r.archived_at:
            events.append((timezone.localtime(r.archived_at).date(), 1, f"Archived {r.name}", "", r))
    for photo in RabbitPhoto.objects.filter(rabbit__owner=user).select_related("rabbit").order_by("-uploaded_at")[:limit]:
        events.append((timezone.localtime(photo.uploaded_at).date(), 0, f"Added a photo of {photo.rabbit.name}", "", photo.rabbit))
    events.sort(key=lambda e: (e[0], e[1]), reverse=True)
    recent = [
        {"title": title, "when": day_label(when, today), "note": note, "rabbit": rabbit}
        for when, _, title, note, rabbit in events[:limit]
    ]
    return {
        "wide": True,
        "herd": {
            "active": len(active),
            "does": sum(1 for r in active if r.sex == Rabbit.Sex.DOE),
            "bucks": sum(1 for r in active if r.sex == Rabbit.Sex.BUCK),
            "statuses": [s for s in statuses if s["count"]],
            "deceased": sum(1 for r in live if r.status == Rabbit.Status.DECEASED),
            "archived": len(rabbits) - len(live),
        },
        "recent": recent,
        "next_up": open_items(user, today)[:5],
    }
