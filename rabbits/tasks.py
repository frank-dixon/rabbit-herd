"""Tasks: manual to-dos plus the litter palpate, nest box, due, wean and process dates,
listed together by date. Overdue items are marked."""

import datetime

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .templatetags.dates import short_date
from django.views.decorators.http import require_POST

from .models import Litter, Rabbit, Task, prefs

TITLE_REQUIRED = "Say what needs doing, like Trim nails."
DATE_REQUIRED = "Enter a due date."
EVERY_REQUIRED = "Enter how often, like every 3 weeks."
REPEAT_KEYS = ("repeat", "repeat_every", "repeat_unit")


def repeat_options():
    return [(value, label) for value, label in Task.Repeat.choices]


def unit_options():
    return [(value, label) for value, label in Task.Unit.choices]


def parse_repeat(values, errors):
    """Repeat fields from the form. Every and unit only count when Custom is chosen."""
    repeat = values.get("repeat", "")
    if repeat not in Task.Repeat.values:
        return {"repeat": "", "repeat_every": None, "repeat_unit": ""}
    if repeat != "custom":
        return {"repeat": repeat, "repeat_every": None, "repeat_unit": ""}
    every, unit = values.get("repeat_every", ""), values.get("repeat_unit", "")
    if not every.isdigit() or not 1 <= int(every) <= 365 or unit not in Task.Unit.values:
        errors["repeat_every"] = [EVERY_REQUIRED]
        return {}
    return {"repeat": "custom", "repeat_every": int(every), "repeat_unit": unit}


def parse_task(request, values):
    """Clean the add/edit form. Returns (fields, errors)."""
    errors = {}
    title = " ".join(values["title"].split())[:120]
    try:
        due = datetime.date.fromisoformat(values["due_on"])
    except ValueError:
        due = None
    rabbit = None
    if values["rabbit"].isdigit():
        rabbit = Rabbit.objects.filter(owner=request.user, pk=int(values["rabbit"])).first()
    if not title:
        errors["title"] = [TITLE_REQUIRED]
    if due is None:
        errors["due_on"] = [DATE_REQUIRED]
    repeat = parse_repeat(values, errors)
    return {"title": title, "due_on": due, "rabbit": rabbit, **repeat}, errors


def form_context(values, errors):
    return {"values": values, "errors": errors, "repeat_options": repeat_options(), "unit_options": unit_options()}



def open_items(user, today=None, *, samples=None):
    """Every open task and litter date, soonest first, as plain dicts.

    samples=None follows the user's Show samples setting; False excludes samples
    (reminders and caps)."""
    today = today or timezone.localdate()
    items = []
    tasks = Task.objects.filter(owner=user, done_at__isnull=True)
    tasks = tasks.real() if samples is False else tasks.for_view(user)
    for task in tasks.select_related("rabbit").prefetch_related("rabbit__photos"):
        items.append({"kind": "task", "pk": task.pk, "title": task.title, "date": task.due_on, "repeat": task.repeat_label(),
                      "rabbit": task.rabbit, "url": reverse("rabbit_detail", args=[task.rabbit_id]) if task.rabbit_id else ""})
    # Litters still to kindle, plus recent ones with wean or process dates
    # open; older litters are history and stay off the list.
    recent = today - datetime.timedelta(days=prefs(user).process_age + 30)
    litters = Litter.objects.filter(owner=user)
    litters = litters.real() if samples is False else litters.for_view(user)
    litters = litters.filter(
        Q(kindled_on__isnull=True) | Q(kindled_on__gte=recent)).select_related("pairing__doe", "pairing__buck").prefetch_related("pairing__doe__photos")
    for litter in litters:
        litter.owner = user  # Shares the user's cached settings; no query per litter.
        for task in litter.tasks():
            if not task["done"]:
                pair = f"{litter.pairing.doe.name} × {litter.pairing.buck.name}"
                start = f"Kindled {short_date(litter.kindled_on)}" if litter.kindled_on else f"Bred {short_date(litter.bred_on)}"
                items.append({"kind": "litter", "pk": litter.pk, "key": task["key"], "date": task["date"],
                              "title": f"{task['label']} · {pair}", "detail": start,
                              "rabbit": litter.pairing.doe, "url": reverse("litter_detail", args=[litter.pk])})
    for item in items:
        item["overdue"] = item["date"] < today
        item["today"] = item["date"] == today
    items.sort(key=lambda item: (item["date"], item["title"]))
    return items


def rabbit_options(user):
    return [(str(pk), name) for pk, name in
            Rabbit.objects.filter(owner=user, archived_at__isnull=True).values_list("pk", "name")]


@login_required
def task_list(request):
    today = timezone.localdate()
    values = {"title": "", "due_on": today.isoformat(), "rabbit": request.GET.get("rabbit", ""),
              "repeat": "", "repeat_every": "", "repeat_unit": "weeks"}
    errors = {}
    if request.method == "POST":
        values = {key: request.POST.get(key, "").strip() for key in values}
        fields, errors = parse_task(request, values)
        if not errors:
            Task.objects.create(owner=request.user, **fields)
            messages.success(request, f"Added: {fields['title']}.")
            return redirect("task_list")
    done = list(Task.objects.filter(owner=request.user, done_at__isnull=False).for_view(request.user).select_related("rabbit")
                .prefetch_related("rabbit__photos").order_by("-done_at")[:20])
    items = open_items(request.user, today)
    groups = {"todo": items, "overdue": [i for i in items if i["overdue"]],
              "litters": [i for i in items if i["kind"] == "litter"], "done": done}
    show = request.GET.get("show", "todo")
    if show not in groups:
        show = "todo"
    labels = [("todo", "To do"), ("overdue", "Overdue"), ("done", "Done")]  # litter dates are already in To do
    tabs = [{"key": key, "label": label, "count": len(groups[key]), "selected": key == show,
             "href": "?" if key == "todo" else f"?show={key}"} for key, label in labels]
    from rabbits.samples.context import sample_ctx
    return render(request, "rabbits/tasks.html", {
        "items": groups[show] if show != "done" else [], "done": done if show == "done" else [], "show": show,
        "tabs": tabs, **form_context(values, errors),
        "rabbit_options": rabbit_options(request.user), "wide": True,
        **sample_ctx(request.user, "tasks"),
    })


@login_required
@require_POST
def task_done(request, pk):
    task = get_object_or_404(Task, owner=request.user, pk=pk)
    with transaction.atomic():
        set_done(task, not task.done_at)
    if task.done_at:
        extra = f" Next one is due {task.next_occurrence.due_on:%b} {task.next_occurrence.due_on.day}." if task.next_occurrence_id else ""
        messages.success(request, f"{task.title}: done.{extra}", extra_tags="undo|" + reverse("task_done", args=[task.pk]))
    else:
        messages.success(request, f"{task.title}: back on the list.")
    return redirect(safe_next(request, "task_list"))


def set_done(task, done):
    """Mark a task done or not. Done on a repeating task adds the next one, counted from
    its due date; undoing removes that next one again if it is still open."""
    if done:
        task.done_at = timezone.now()
        due = task.next_due()
        if due and not task.next_occurrence_id:
            task.next_occurrence = Task.objects.create(
                owner=task.owner, title=task.title, due_on=due, rabbit=task.rabbit,
                repeat=task.repeat, repeat_every=task.repeat_every, repeat_unit=task.repeat_unit)
    else:
        task.done_at = None
        nxt = task.next_occurrence
        if nxt and nxt.done_at is None and not nxt.next_occurrence_id:
            task.next_occurrence = None
            nxt.delete()
    task.save(update_fields=["done_at", "next_occurrence"])


@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, owner=request.user, pk=pk)
    values = {"title": task.title, "due_on": task.due_on.isoformat(), "rabbit": str(task.rabbit_id or ""),
              "repeat": task.repeat, "repeat_every": str(task.repeat_every or ""), "repeat_unit": task.repeat_unit or "weeks"}
    errors = {}
    if request.method == "POST":
        values = {key: request.POST.get(key, "").strip() for key in values}
        fields, errors = parse_task(request, values)
        if not errors:
            for key, value in fields.items():
                setattr(task, key, value)
            task.save()
            messages.success(request, f"Saved: {task.title}.")
            return redirect("task_list")
    return render(request, "rabbits/task_edit.html", {
        "task": task, **form_context(values, errors), "rabbit_options": rabbit_options(request.user),
    })


@login_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, owner=request.user, pk=pk)
    task.delete()
    messages.success(request, f"Removed: {task.title}.")
    return redirect(safe_next(request, "task_list"))


def safe_next(request, default):
    target = request.POST.get("next", "")
    return target if target in ("/", "/tasks/") or (target.startswith("/rabbits/") and target[9:].rstrip("/").isdigit()) else reverse(default)
