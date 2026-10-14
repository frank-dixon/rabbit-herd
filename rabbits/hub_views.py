"""Herd-wide views behind the menu and tabs: weights, health and shows across
every rabbit. Shows and Health use the shared Grid/List index items."""

from collections import Counter

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .index_items import index_view, ordinal, place_tone, stat, view_options
from .models import HealthNote, ShowEntry

LEGS_FOR_GC = 3  # ARBA: three legs, at least one as a senior, make a Grand Champion.


def short(day):
    return f"{day:%b} {day.day}"


@login_required
def health_list(request):
    notes = HealthNote.objects.filter(rabbit__owner=request.user).select_related("rabbit").prefetch_related("rabbit__photos")[:100]
    return render(request, "hub/health.html", {"notes": notes})


@login_required
def show_list(request):
    entries = list(ShowEntry.objects.filter(rabbit__owner=request.user).select_related("rabbit").prefetch_related("rabbit__photos").order_by("-date", "-pk"))
    view = index_view(request, "shows", "list")
    legs = Counter(e.rabbit_id for e in entries if e.leg)
    year = timezone.localdate().year
    leader = max(legs.items(), key=lambda kv: kv[1], default=None)
    leader_name = next((e.rabbit.name for e in entries if leader and e.rabbit_id == leader[0]), "")
    items = [show_item(e, legs[e.rabbit_id]) for e in entries]
    return render(request, "hub/shows.html", {
        "entries": entries, "items": items, "wide": True, "view": view, "view_options": view_options(request, view),
        "stats": [stat(f"Entries in {year}", sum(1 for e in entries if e.date.year == year), f"{len(entries)} all time"),
                  stat("Legs earned", sum(legs.values()), f"{LEGS_FOR_GC} make a Grand Champion"),
                  stat("Closest to GC", f"{leader_name} · {min(leader[1], LEGS_FOR_GC)} of {LEGS_FOR_GC}" if leader else "—",
                       "Grand Champion ready" if leader and leader[1] >= LEGS_FOR_GC else "legs so far")],
        "columns": [{"label": "Rabbit"}, {"label": "Show"}, {"label": "Place"}, {"label": "Award", "wide_only": True},
                    {"label": "Toward GC", "align": "r", "wide_only": True}],
    })


def show_item(entry, legs):
    have = min(legs, LEGS_FOR_GC)
    progress = {"segs": [1 if i < have else 0 for i in range(LEGS_FOR_GC)], "dots": True,
                "label": "Grand Champion ready" if legs >= LEGS_FOR_GC else f"{have} of {LEGS_FOR_GC} legs"}
    place = {"label": ordinal(entry.placing) or "—", "tone": place_tone(entry.placing),
             "note": f"of {entry.out_of}" if entry.out_of else ""}
    award = {"label": entry.award, "tone": "y"} if entry.award else {"label": "No award" if not entry.leg else "Leg", "tone": "g" if entry.leg else "o"}
    when = f"{short(entry.date)}, {entry.date.year}"
    return {
        "href": f"{reverse('rabbit_detail', args=[entry.rabbit_id])}#shows", "title": entry.rabbit.name, "sub": entry.show_class,
        "thumbs": [entry.rabbit], "thumb_size": "md", "badge": place,
        "kv": [{"label": f"{when}{f' · {entry.location}' if entry.location else ''}", "value": entry.show_name}],
        "foot": {"pill": award, "progress": progress},
        "mobile": f"{entry.award + ' · ' if entry.award else ''}{progress['label']}",
        "cells": [{"kind": "lead"}, {"kind": "text", "main": entry.show_name, "sub": when, "wrap": True},
                  {"kind": "pill", **place}, {"kind": "pill", "wide_only": True, "label": entry.award, "tone": "y"},
                  {"kind": "progress", "align": "r", "wide_only": True, **progress, "after": progress["label"], "label": ""}],
    }
