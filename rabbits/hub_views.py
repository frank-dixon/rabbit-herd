"""Herd-wide views behind the menu and tabs: weights, health and shows across
every rabbit, newest first. Each row links to the rabbit's own section."""

from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery
from django.shortcuts import render

from .models import HealthNote, Rabbit, ShowEntry, Weight


@login_required
def weights_hub(request):
    latest = Weight.objects.filter(rabbit=OuterRef("pk")).order_by("-date", "-pk")
    rabbits = (
        Rabbit.objects.filter(owner=request.user, archived_at__isnull=True)
        .exclude(status=Rabbit.Status.DECEASED)
        .annotate(last_grams=Subquery(latest.values("grams")[:1]), last_unit=Subquery(latest.values("unit")[:1]),
                  last_date=Subquery(latest.values("date")[:1]))
        .order_by("name")
    )
    from .models import prefs, weight_text

    unit = prefs(request.user).weight_unit
    rows = [{"rabbit": r, "text": weight_text(r.last_grams, unit) if r.last_grams else "", "date": r.last_date}
            for r in rabbits]
    rows.sort(key=lambda row: (row["date"] is not None, row["date"] or 0))
    recent = Weight.objects.filter(rabbit__owner=request.user).select_related("rabbit").order_by("-date", "-pk")[:12]
    return render(request, "hub/weights.html", {"rows": rows, "recent": recent, "wide": True})


@login_required
def health_list(request):
    notes = HealthNote.objects.filter(rabbit__owner=request.user).select_related("rabbit")[:100]
    return render(request, "hub/health.html", {"notes": notes})


@login_required
def show_list(request):
    entries = ShowEntry.objects.filter(rabbit__owner=request.user).select_related("rabbit")[:100]
    return render(request, "hub/shows.html", {"entries": entries})
