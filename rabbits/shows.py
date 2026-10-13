"""Show results on a rabbit. Adding and editing use the same form on the
rabbit page; ?show=<id> loads an entry into it for editing."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .health import parse
from .models import Rabbit, ShowEntry

TEXT_FIELDS = {"show_name": 120, "location": 120, "show_class": 80, "award": 80, "judge": 120, "notes": 1000}


def form_context(request, rabbit):
    entries = list(rabbit.show_entries.all())
    editing = None
    raw = request.GET.get("show", "")
    if raw.isdigit():
        editing = next((entry for entry in entries if entry.pk == int(raw)), None)
    legs = sum(1 for entry in entries if entry.leg)
    return {"show_entries": entries, "show_editing": editing, "show_legs": legs,
            "legs_for_grand": ShowEntry.LEGS_FOR_GRAND}


def _number(raw):
    raw = (raw or "").strip()
    if not raw:
        return None, True
    if raw.isdigit() and 0 < int(raw) <= 999:
        return int(raw), True
    return None, False


def _save(request, rabbit, entry):
    post = request.POST
    values = {name: post.get(name, "").strip()[:limit] for name, limit in TEXT_FIELDS.items()}
    day = parse(post.get("show_date"))
    placing, placing_ok = _number(post.get("placing"))
    out_of, out_of_ok = _number(post.get("out_of"))
    error = ""
    if not values["show_name"]:
        error = "Enter the show's name."
    elif day is None:
        error = "Enter the show's date."
    elif day > timezone.localdate():
        error = "The show's date is in the future."
    elif not placing_ok or not out_of_ok:
        error = "Enter the placing and class size as whole numbers, like 2 of 9."
    elif placing and out_of and placing > out_of:
        error = "The placing is larger than the class size."
    if error:
        messages.error(request, error)
        return redirect(f"/rabbits/{rabbit.pk}/?show={entry.pk}#shows" if entry.pk else f"/rabbits/{rabbit.pk}/#shows")
    editing = entry.pk is not None
    for name, value in values.items():
        setattr(entry, name, value)
    entry.date, entry.placing, entry.out_of = day, placing, out_of
    entry.leg = post.get("leg") == "on"
    entry.save()
    messages.success(request, "Show result saved." if editing else "Show result added.")
    return redirect(f"/rabbits/{rabbit.pk}/#shows")


@login_required
@require_POST
def show_add(request, pk):
    rabbit = get_object_or_404(Rabbit, owner=request.user, pk=pk)
    return _save(request, rabbit, ShowEntry(rabbit=rabbit))


@login_required
@require_POST
def show_edit(request, pk):
    entry = get_object_or_404(ShowEntry.objects.select_related("rabbit"), rabbit__owner=request.user, pk=pk)
    return _save(request, entry.rabbit, entry)


@login_required
@require_POST
def show_delete(request, pk):
    entry = get_object_or_404(ShowEntry, rabbit__owner=request.user, pk=pk)
    entry.delete()
    messages.success(request, "The show result was removed.")
    return redirect(f"/rabbits/{entry.rabbit_id}/#shows")
