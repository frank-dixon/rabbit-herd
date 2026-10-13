import datetime

from django.conf import settings
from django.utils import timezone
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
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
    from .nav import DESTINATIONS, MAX_TABS, clean_tabs

    current = clean_tabs(user.tab_bar)
    slots = [{"index": i + 1, "value": current[i] if i < len(current) else "", "required": i < 3} for i in range(MAX_TABS)]
    destinations = [(key, label) for key, (label, _url, _q) in DESTINATIONS.items()]
    return render(request, "pages/account.html", {"export_kinds": kinds, "themes": themes,
                                                  "tab_slots": slots, "tab_destinations": destinations})


@login_required
def tabs(request):
    """Save the phone bottom bar: 3 to 5 destinations in order. Posted by the
    edit mode on the bar (JSON reply) or the Settings form (redirect)."""
    from .nav import DEFAULT_TABS, DESTINATIONS, MAX_TABS, MIN_TABS

    if request.method == "POST":
        if request.POST.get("reset"):
            keys = list(DEFAULT_TABS)
        else:
            keys = [k for k in request.POST.getlist("tab") if k]
        valid = (MIN_TABS <= len(keys) <= MAX_TABS and len(set(keys)) == len(keys)
                 and all(k in DESTINATIONS for k in keys))
        cleaned = keys if valid else []
        if valid:
            request.user.tab_bar = cleaned
            request.user.save(update_fields=["tab_bar"])
        if request.headers.get("X-Requested-With") == "fetch":
            return JsonResponse({"ok": bool(valid), "tabs": cleaned}, status=200 if valid else 400)
        if valid:
            messages.success(request, "Bottom bar saved.")
        else:
            messages.error(request, "Pick 3 to 5 different tabs.")
    return redirect(reverse("account") + "#tabs")


@login_required
def menu(request):
    """The menu panel as a page, for browsers without JS."""
    return render(request, "pages/menu.html")


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
    items = open_items(user, today)
    week_end = today + datetime.timedelta(days=7)
    return {
        "wide": True,
        "today": today,
        "due_now": [i for i in items if i["date"] <= today],
        "this_week": [i for i in items if today < i["date"] <= week_end],
        "litters": active_litters(user, today),
        "watch": watch_list(user, today),
        "herd": {
            "active": len(active),
            "does": sum(1 for r in active if r.sex == Rabbit.Sex.DOE),
            "bucks": sum(1 for r in active if r.sex == Rabbit.Sex.BUCK),
            "statuses": [s for s in statuses if s["count"]],
            "deceased": sum(1 for r in live if r.status == Rabbit.Status.DECEASED),
            "archived": len(rabbits) - len(live),
        },
        "recent": recent,
        "next_up": items[:5],
    }


UNDER_AVERAGE = 0.85  # a kit under 85% of its litter's average is watched


def kit_weights(litter):
    """Each surviving kit with its latest weight, and the litter average."""
    kits = []
    for kit in litter.kits.all():
        if kit.archived_at or kit.status == "deceased":
            continue
        weights = list(kit.weights.all())
        kits.append({"rabbit": kit, "weight": weights[-1] if weights else None})
    weighed = [k["weight"].grams for k in kits if k["weight"]]
    average = round(sum(weighed) / len(weighed)) if weighed else None
    for kit in kits:
        kit["behind"] = bool(average and kit["weight"] and kit["weight"].grams < average * UNDER_AVERAGE)
    return kits, average


def active_litters(user, today):
    """Kindled litters not yet processed, youngest first, with kit age and weights."""
    from rabbits.models import Litter, weight_text

    rows = []
    litters = (Litter.objects.filter(owner=user, kindled_on__isnull=False, processed=False)
               .select_related("pairing__doe", "pairing__buck").prefetch_related("kits__weights"))
    for litter in litters:
        age = (today - litter.kindled_on).days
        if age > Litter.PROCESS_AGE + 30:
            continue
        kits, average = kit_weights(litter)
        rows.append({"litter": litter, "age": age, "kits": len(kits) or litter.survivors or 0,
                     "behind": sum(1 for k in kits if k["behind"]), "average": average,
                     "average_text": weight_text(average, next(k["weight"].unit for k in kits if k["weight"])) if average else ""})
    rows.sort(key=lambda row: row["age"])
    return rows


def watch_list(user, today):
    """Health follow-ups that are still open, and kits well under their litter's average."""
    from rabbits.models import HealthNote

    items = []
    notes = (HealthNote.objects.filter(rabbit__owner=user, follow_up_on__isnull=False, task__done_at__isnull=True,
                                       follow_up_on__lte=today + datetime.timedelta(days=7))
             .select_related("rabbit", "task").order_by("follow_up_on"))
    for note in notes:
        days = (note.follow_up_on - today).days
        when = "recheck today" if days == 0 else (f"recheck overdue {-days} day{'s' if days != -1 else ''}" if days < 0
                                                  else f"recheck {note.follow_up_on:%a}")
        items.append({"title": f"{note.rabbit.name} · {note.get_kind_display().lower()}",
                      "detail": f"Noted {note.date:%b} {note.date.day} · {when}", "urgent": days <= 0,
                      "url": f"/rabbits/{note.rabbit_id}/#health", "task": note.task})
    for row in active_litters(user, today):
        kits, average = kit_weights(row["litter"])
        for kit in kits:
            if kit["behind"]:
                under = round(100 - kit["weight"].grams * 100 / average)
                items.append({"title": kit["rabbit"].name, "detail": f"{kit['weight'].text} · {under}% under litter average",
                              "urgent": True, "url": f"/rabbits/{kit['rabbit'].pk}/#weights", "task": None})
    return items
