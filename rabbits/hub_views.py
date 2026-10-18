"""Herd-wide views behind the menu and tabs: weights, health and shows across
every rabbit. Shows and Health use the shared Grid/List index items."""

from collections import Counter

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .index_items import index_view, ordinal, place_tone, sorted_items, stat, tabs, view_options
from .models import HealthNote, ShowEntry
from .status_pills import tone as status_tone

LEGS_FOR_GC = 3  # ARBA: three legs, at least one as a senior, make a Grand Champion.


def short(day):
    from .templatetags.dates import short_date

    return short_date(day)


@login_required
def health_list(request):
    today = timezone.localdate()
    notes = list(HealthNote.objects.filter(rabbit__owner=request.user).select_related("rabbit", "task").prefetch_related("rabbit__photos").order_by("-date", "-pk")[:200])
    tab = request.GET.get("tab", "open")
    tab = tab if tab in ("open", "resolved", "all") else "open"
    open_notes = [n for n in notes if not n.resolved]
    overdue = sum(1 for n in open_notes if n.follow_up_on and n.follow_up_on < today)
    shown = {"open": open_notes, "resolved": [n for n in notes if n.resolved], "all": notes}[tab]
    items = sorted((health_item(n, today) for n in shown), key=lambda it: it["order"])
    recent = sum(1 for n in notes if (today - n.date).days <= 30)
    columns = [{"label": "Rabbit", "sort": "rabbit"}, {"label": "Type", "sort": "type"}, {"label": "Note", "wide_only": True}, {"label": "Follow-up", "wide_only": True, "sort": "follow"},
               {"label": "State", "align": "r", "wide_only": True}, {"label": "", "align": "r"}]
    items = sorted_items(request, items, columns)
    return render(request, "hub/health.html", {
        "notes": notes, "items": items, "wide": True, "view": "list",  # Health has no layout toggle (Frank, 2026-10-18)
        "tabs": tabs(request, tab, [("open", "Open", len(open_notes)), ("resolved", "Resolved", len(notes) - len(open_notes)), ("all", "All", len(notes))]),
        "stats": [stat("Open", len(open_notes), "notes to watch"), stat("Overdue", overdue, "follow-ups past due", "r" if overdue else ""),
                  stat("Logged in 30 days", recent, "all types")],
        "columns": columns,
    })


def health_item(note, today):
    if note.resolved:
        state, follow, tone = {"label": "Resolved", "tone": ""}, "—", ""
    else:
        # Open is grey until its follow-up comes due: amber on the day, red once overdue (Critic v3 V2).
        state = {"label": "Open", "tone": ""}
        if note.follow_up_on:
            days = (note.follow_up_on - today).days
            follow = f"Overdue {-days} day{'s' if days != -1 else ''}" if days < 0 else "Follow up today" if days == 0 else f"Follow up in {days} day{'s' if days != 1 else ''}"
            tone = "r" if days < 0 else ""
            state["tone"] = "r" if days < 0 else "y" if days == 0 else ""
        else:
            follow, tone = "No follow-up set", ""
    kind = {"label": note.get_kind_display(), "tone": status_tone(note.get_kind_display())}
    action = {"url": reverse("health_resolve", args=[note.pk]), "label": "Reopen" if note.resolved else "Resolve"}
    when = short(note.follow_up_on) if note.follow_up_on else ""
    return {
        "href": f"{reverse('rabbit_detail', args=[note.rabbit_id])}#health", "title": note.rabbit.name, "sub": short(note.date),
        "thumbs": [note.rabbit], "pill": kind, "text": note.notes, "dim": note.resolved, "action": action,
        "foot": {"strong": "", "text": follow, "tone": tone, "end": state},
        "mobile": note.notes + ("" if note.resolved else f" · {follow}"),
        "cells": [{"kind": "lead"}, {"kind": "pill", **kind}, {"kind": "text", "main": note.notes, "wide_only": True, "wrap": True},
                  {"kind": "text", "main": follow, "sub": when, "tone": tone, "wide_only": True},
                  {"kind": "pill", "align": "r", "wide_only": True, **state}, {"kind": "action", "align": "r"}],
        "sort": {"rabbit": note.rabbit.name.lower(), "type": note.kind, "follow": None if note.resolved else note.follow_up_on},
        "order": (note.resolved, not (note.follow_up_on and not note.resolved), note.follow_up_on or today, -note.date.toordinal()),
    }


@login_required
@require_POST
def health_resolve(request, pk):
    """Resolve (or reopen) a health note; resolving also closes its open follow-up task."""
    note = get_object_or_404(HealthNote, rabbit__owner=request.user, pk=pk)
    with transaction.atomic():
        note.resolved = not note.resolved
        note.save(update_fields=["resolved"])
        if note.resolved and note.task_id and note.task.done_at is None:
            note.task.done_at = timezone.now()
            note.task.save(update_fields=["done_at"])
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("health_list"))


@login_required
def show_list(request):
    entries = list(ShowEntry.objects.filter(rabbit__owner=request.user).select_related("rabbit").prefetch_related("rabbit__photos").order_by("-date", "-pk"))
    view = index_view(request, "shows", "list")
    legs = Counter(e.rabbit_id for e in entries if e.leg)
    year = timezone.localdate().year
    leader = max(legs.items(), key=lambda kv: kv[1], default=None)
    leader_name = next((e.rabbit.name for e in entries if leader and e.rabbit_id == leader[0]), "")
    columns = [{"label": "Rabbit", "sort": "rabbit"}, {"label": "Show", "sort": "date"}, {"label": "Place", "sort": "place"}, {"label": "Award", "wide_only": True},
               {"label": "Toward GC", "align": "r", "wide_only": True, "sort": "legs"}]
    items = sorted_items(request, [show_item(e, legs[e.rabbit_id]) for e in entries], columns, desc_first=("date", "legs"))
    return render(request, "hub/shows.html", {
        "entries": entries, "items": items, "wide": True, "view": view, "view_options": view_options(request, view),
        "stats": [stat(f"Entries in {year}", sum(1 for e in entries if e.date.year == year), f"{len(entries)} all time"),
                  stat("Legs earned", sum(legs.values()), f"{LEGS_FOR_GC} make a Grand Champion"),
                  stat("Closest to GC", f"{leader_name} · {min(leader[1], LEGS_FOR_GC)} of {LEGS_FOR_GC}" if leader else "—",
                       "Grand Champion ready" if leader and leader[1] >= LEGS_FOR_GC else "legs so far")],
        "columns": columns,
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
        "sort": {"rabbit": entry.rabbit.name.lower(), "date": entry.date, "place": entry.placing, "legs": legs},
        "mobile": f"{entry.award + ' · ' if entry.award else ''}{progress['label']}",
        "cells": [{"kind": "lead"}, {"kind": "text", "main": entry.show_name, "sub": when, "wrap": True},
                  {"kind": "pill", **place}, {"kind": "pill", "wide_only": True, "label": entry.award, "tone": "y"},
                  {"kind": "progress", "align": "r", "wide_only": True, **progress, "after": progress["label"], "label": ""}],
    }
