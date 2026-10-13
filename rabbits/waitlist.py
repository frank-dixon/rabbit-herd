"""Waitlist: buyers waiting for a rabbit by breed, sex and color.

Open requests are listed first come, first served, each with the growing-
out rabbits in the herd that fit it. One form adds a request or, with
?edit=<id>, edits one.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .costs import _decimal
from .health import parse
from .models import Rabbit, WaitlistEntry

FIELDS = ("buyer", "reach", "requested_on", "breed", "sex", "color", "status", "deposit", "rabbit", "notes")
LIMITS = {"buyer": 120, "reach": 160, "breed": 80, "color": 80, "notes": 1000}


def _clean(request):
    values = {key: request.POST.get(key, "").strip() for key in FIELDS}
    errors = {}
    day = parse(values["requested_on"])
    if not values["buyer"]:
        errors["buyer"] = ["Please enter the buyer's name."]
    if day is None:
        errors["requested_on"] = ["Please enter the date they asked."]
    elif day > timezone.localdate():
        errors["requested_on"] = ["That date is in the future. Please check it."]
    if values["sex"] not in WaitlistEntry.Sex.values:
        errors["sex"] = ["Please choose doe, buck or either."]
    if values["status"] not in WaitlistEntry.Status.values:
        errors["status"] = ["Please choose a status."]
    deposit, ok = _decimal(values["deposit"], 100000)
    if not ok:
        errors["deposit"] = ["Please enter the deposit as an amount, like 25."]
    rabbit = None
    if values["rabbit"]:
        rabbit = Rabbit.objects.filter(owner=request.user, pk=values["rabbit"]).first() if values["rabbit"].isdigit() else None
        if rabbit is None:
            errors["rabbit"] = ["Please choose one of your rabbits."]
    cleaned = {key: values[key][:limit] for key, limit in LIMITS.items()}
    cleaned.update(requested_on=day, sex=values["sex"], status=values["status"], deposit=deposit, rabbit=rabbit)
    return values, errors, cleaned


def _render(request, values, errors, editing, status=200):
    entries = list(WaitlistEntry.objects.filter(owner=request.user).select_related("rabbit"))
    candidates = list(Rabbit.objects.filter(owner=request.user, archived_at__isnull=True, status=Rabbit.Status.GROWING))
    open_entries = [entry for entry in entries if entry.status in WaitlistEntry.OPEN]
    for position, entry in enumerate(open_entries, start=1):
        entry.position = position
        entry.fits = entry.matches(candidates)
    rabbit_options = [(str(r.pk), r.name) for r in Rabbit.objects.filter(owner=request.user, archived_at__isnull=True)]
    return render(request, "rabbits/waitlist.html", {
        "open_entries": open_entries,
        "closed_entries": [entry for entry in entries if entry.status not in WaitlistEntry.OPEN][::-1][:50],
        "values": values, "errors": errors, "editing": editing,
        "sex_options": [choice for choice in WaitlistEntry.Sex.choices if choice[0]],
        "status_options": WaitlistEntry.Status.choices, "rabbit_options": rabbit_options,
        "today_iso": timezone.localdate().isoformat(), "wide": True,
    }, status=status)


@login_required
def waitlist(request):
    if request.method == "POST":
        values, errors, cleaned = _clean(request)
        if not errors:
            WaitlistEntry.objects.create(owner=request.user, **cleaned)
            messages.success(request, f"{cleaned['buyer']} was added to the waitlist.")
            return redirect("waitlist")
        return _render(request, values, errors, None, status=400)
    editing = None
    if request.GET.get("edit", "").isdigit():
        editing = WaitlistEntry.objects.filter(owner=request.user, pk=request.GET["edit"]).first()
    if editing:
        values = {key: str(getattr(editing, key) if getattr(editing, key) is not None else "") for key in FIELDS}
        values["requested_on"] = editing.requested_on.isoformat()
        values["rabbit"] = str(editing.rabbit_id or "")
    else:
        values = {"requested_on": timezone.localdate().isoformat(), "status": WaitlistEntry.Status.WAITING}
    return _render(request, values, {}, editing)


@login_required
@require_POST
def waitlist_edit(request, pk):
    entry = get_object_or_404(WaitlistEntry, owner=request.user, pk=pk)
    values, errors, cleaned = _clean(request)
    if errors:
        return _render(request, values, errors, entry, status=400)
    for key, value in cleaned.items():
        setattr(entry, key, value)
    entry.save()
    messages.success(request, f"{entry.buyer}'s request was saved.")
    return redirect("waitlist")


@login_required
@require_POST
def waitlist_delete(request, pk):
    entry = get_object_or_404(WaitlistEntry, owner=request.user, pk=pk)
    entry.delete()
    messages.success(request, f"{entry.buyer} was removed from the waitlist.")
    return redirect("waitlist")
