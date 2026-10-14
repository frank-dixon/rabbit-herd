"""Herd-wide views behind the menu and tabs: weights, health and shows across
every rabbit, newest first. Each row links to the rabbit's own section."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import HealthNote, ShowEntry


@login_required
def health_list(request):
    notes = HealthNote.objects.filter(rabbit__owner=request.user).select_related("rabbit").prefetch_related("rabbit__photos")[:100]
    return render(request, "hub/health.html", {"notes": notes})


@login_required
def show_list(request):
    entries = ShowEntry.objects.filter(rabbit__owner=request.user).select_related("rabbit").prefetch_related("rabbit__photos")[:100]
    return render(request, "hub/shows.html", {"entries": entries})
