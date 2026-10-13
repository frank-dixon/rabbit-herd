"""Tasks: manual to-dos plus the litter palpate, nest box, due, wean and process dates,
listed together by date. Overdue items are marked."""

import datetime

from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Litter, Rabbit, Task, prefs

TITLE_REQUIRED = "Please say what needs doing, like Trim nails."
DATE_REQUIRED = "Please enter a due date."


def open_items(user, today=None):
    """Every open task and litter date, soonest first, as plain dicts."""
    today = today or timezone.localdate()
    items = []
    for task in Task.objects.filter(owner=user, done_at__isnull=True).select_related("rabbit"):
        items.append({"kind": "task", "pk": task.pk, "title": task.title, "date": task.due_on,
                      "rabbit": task.rabbit, "url": reverse("rabbit_detail", args=[task.rabbit_id]) if task.rabbit_id else ""})
    # Litters still to kindle, plus recent ones with wean or process dates
    # open; older litters are history and stay off the list.
    recent = today - datetime.timedelta(days=prefs(user).process_age + 30)
    litters = Litter.objects.filter(owner=user).filter(
        Q(kindled_on__isnull=True) | Q(kindled_on__gte=recent)).select_related("pairing__doe", "pairing__buck")
    for litter in litters:
        litter.owner = user  # Shares the user's cached settings; no query per litter.
        for task in litter.tasks():
            if not task["done"]:
                when = f"kits {task['age']} days" if "age" in task else f"day {task['day']}"
                items.append({"kind": "litter", "pk": litter.pk, "key": task["key"], "date": task["date"],
                              "title": f"{task['label']}: {litter.pairing.doe.name} ({when})",
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
    values = {"title": "", "due_on": today.isoformat(), "rabbit": request.GET.get("rabbit", "")}
    errors = {}
    if request.method == "POST":
        values = {key: request.POST.get(key, "").strip() for key in values}
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
        if not errors:
            Task.objects.create(owner=request.user, title=title, due_on=due, rabbit=rabbit)
            messages.success(request, f"Added: {title}.")
            return redirect("task_list")
    done = Task.objects.filter(owner=request.user, done_at__isnull=False).select_related("rabbit").order_by("-done_at")[:10]
    return render(request, "rabbits/tasks.html", {
        "items": open_items(request.user, today), "done": done, "values": values, "errors": errors,
        "rabbit_options": rabbit_options(request.user), "wide": True,
    })


@login_required
@require_POST
def task_done(request, pk):
    task = get_object_or_404(Task, owner=request.user, pk=pk)
    task.done_at = None if task.done_at else timezone.now()
    task.save(update_fields=["done_at"])
    messages.success(request, f"{task.title}: {'done' if task.done_at else 'back on the list'}.")
    return redirect(safe_next(request, "task_list"))


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
