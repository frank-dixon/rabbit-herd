"""Cage and hutch locations: a simple owner-scoped list, assigned on each rabbit."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Location, Rabbit

NAME_REQUIRED = "A location needs a name, like Hutch 3 or Barn row A."
NAME_TOO_LONG = "A location's name can be up to 80 characters. Please shorten it."
NAME_TAKEN = "You already have a location called {name}. Please choose another name."


def clean_name(user, raw, exclude=None):
    name = " ".join((raw or "").split())
    if not name:
        return None, NAME_REQUIRED
    if len(name) > 80:
        return None, NAME_TOO_LONG
    taken = Location.objects.filter(owner=user, name__iexact=name).exclude(pk=exclude)
    if taken.exists():
        return None, NAME_TAKEN.format(name=name)
    return name, ""


@login_required
def location_list(request):
    if request.method == "POST":
        name, error = clean_name(request.user, request.POST.get("name"))
        if error:
            messages.error(request, error)
        else:
            Location.objects.create(owner=request.user, name=name, notes=" ".join(request.POST.get("notes", "").split())[:200])
            messages.success(request, f"{name} was added.")
        return redirect("location_list")
    locations = Location.objects.filter(owner=request.user).annotate(
        count=Count("rabbits", filter=Q(rabbits__archived_at__isnull=True))
    )
    unplaced = Rabbit.objects.filter(owner=request.user, archived_at__isnull=True, location__isnull=True).count()
    return render(request, "rabbits/locations.html", {"locations": locations, "unplaced": unplaced, "wide": True})


@login_required
@require_POST
def location_edit(request, pk):
    location = get_object_or_404(Location, owner=request.user, pk=pk)
    if request.POST.get("action") == "delete":
        location.delete()
        messages.success(request, f"{location.name} was removed. Its rabbits now have no location.")
        return redirect("location_list")
    name, error = clean_name(request.user, request.POST.get("name"), exclude=location.pk)
    if error:
        messages.error(request, error)
    else:
        location.name = name
        location.notes = " ".join(request.POST.get("notes", "").split())[:200]
        location.save()
        messages.success(request, f"{name} was saved.")
    return redirect("location_list")


@login_required
@require_POST
def rabbit_location(request, pk):
    rabbit = get_object_or_404(Rabbit, owner=request.user, pk=pk)
    raw = request.POST.get("location", "")
    new_name = request.POST.get("new_location", "").strip()
    if new_name:
        name, error = clean_name(request.user, new_name)
        if error:
            messages.error(request, error)
            return redirect(f"/rabbits/{rabbit.pk}/#location")
        rabbit.location = Location.objects.create(owner=request.user, name=name)
    elif raw == "":
        rabbit.location = None
    elif raw.isdigit() and Location.objects.filter(owner=request.user, pk=int(raw)).exists():
        rabbit.location_id = int(raw)
    else:
        messages.error(request, "Please choose one of your locations.")
        return redirect(f"/rabbits/{rabbit.pk}/#location")
    rabbit.save(update_fields=["location", "updated_at"])
    messages.success(request, f"{rabbit.name} is now in {rabbit.location.name}." if rabbit.location else f"{rabbit.name} has no location now.")
    return redirect(f"/rabbits/{rabbit.pk}/#location")
