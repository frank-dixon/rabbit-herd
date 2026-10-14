"""Herd-wide views behind the menu and tabs: weights, health and shows across
every rabbit, newest first. Each row links to the rabbit's own section."""

from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery
from django.shortcuts import render

from .models import HealthNote, Rabbit, ShowEntry, Weight


WEIGHT_SORTS = [("due", "Last weighed"), ("name", "Name"), ("weight", "Weight"), ("change", "Change")]


def weight_rows(user, sort):
    """One row per active rabbit: its latest weight, when, and the change
    since the weigh-in before. Sorted by `sort` (see WEIGHT_SORTS)."""
    from .models import prefs, weight_text

    latest = Weight.objects.filter(rabbit=OuterRef("pk")).order_by("-date", "-pk")
    rabbits = (
        Rabbit.objects.filter(owner=user, archived_at__isnull=True)
        .exclude(status=Rabbit.Status.DECEASED)
        .annotate(last_grams=Subquery(latest.values("grams")[:1]), last_date=Subquery(latest.values("date")[:1]),
                  prev_grams=Subquery(latest.values("grams")[1:2]))
        .order_by("name").prefetch_related("photos")
    )
    unit = prefs(user).weight_unit
    rows = []
    for r in rabbits:
        change = r.last_grams - r.prev_grams if r.last_grams is not None and r.prev_grams is not None else None
        change_text = ""
        if change is not None:
            size = weight_text(abs(change), unit)
            change_text = "No change" if size in ("0 oz", "0 kg") else ("+" if change > 0 else "−") + size
        rows.append({"rabbit": r, "text": weight_text(r.last_grams, unit) if r.last_grams else "", "date": r.last_date,
                     "grams": r.last_grams, "change": change, "change_text": change_text})
    if sort == "name":
        pass  # already by name
    elif sort == "weight":
        rows.sort(key=lambda row: (row["grams"] is None, -(row["grams"] or 0)))
    elif sort == "change":
        rows.sort(key=lambda row: (row["change"] is None, -(row["change"] or 0)))
    else:
        rows.sort(key=lambda row: (row["date"] is not None, row["date"] or 0))
    return rows


SORT_HINTS = {"due": "Longest since a weigh-in comes first.", "name": "A to Z.",
              "weight": "Heaviest first.", "change": "Biggest gain since the weigh-in before comes first."}


@login_required
def weights_hub(request):
    sort = request.GET.get("sort", "due")
    if sort not in dict(WEIGHT_SORTS):
        sort = "due"
    rows = weight_rows(request.user, sort)
    options = [{"href": "?" if key == "due" else f"?sort={key}", "label": label, "selected": key == sort}
               for key, label in WEIGHT_SORTS]
    recent = Weight.objects.filter(rabbit__owner=request.user).select_related("rabbit").order_by("-date", "-pk")[:12]
    return render(request, "hub/weights.html", {"rows": rows, "recent": recent, "wide": True, "sort_options": options,
                                                "sort_hint": SORT_HINTS[sort]})


@login_required
def health_list(request):
    notes = HealthNote.objects.filter(rabbit__owner=request.user).select_related("rabbit").prefetch_related("rabbit__photos")[:100]
    return render(request, "hub/health.html", {"notes": notes})


@login_required
def show_list(request):
    entries = ShowEntry.objects.filter(rabbit__owner=request.user).select_related("rabbit").prefetch_related("rabbit__photos")[:100]
    return render(request, "hub/shows.html", {"entries": entries})
