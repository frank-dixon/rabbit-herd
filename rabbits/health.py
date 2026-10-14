"""Health notes on a rabbit: date, type, notes and an optional follow-up
date. A follow-up adds a task due that day, linked back to the note."""

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import HealthNote, Rabbit, RabbitPhoto, Task


def parse(raw):
    try:
        return datetime.date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


MAX_HEALTH_PHOTOS = 6


def health_photos(request):
    """The note's photos as (cleaned file, date taken) pairs, or None after
    saying what was wrong. Each is checked and stripped like any photo."""
    from .forms import PhotoUploadForm

    files = request.FILES.getlist("health_photos")[:MAX_HEALTH_PHOTOS + 1]
    if len(files) > MAX_HEALTH_PHOTOS:
        messages.error(request, f"Add up to {MAX_HEALTH_PHOTOS} photos to a health note.")
        return None
    out = []
    for upload in files:
        form = PhotoUploadForm({"notes": ""}, {"image": upload})
        if not form.is_valid():
            messages.error(request, next(iter(form.errors.values()))[0])
            return None
        out.append((form.cleaned_data["image"], form.taken_at))
    return out


@login_required
@require_POST
def health_add(request, pk):
    rabbit = get_object_or_404(Rabbit, owner=request.user, pk=pk)
    back = redirect(f"/rabbits/{rabbit.pk}/#health")
    day = parse(request.POST.get("health_date"))
    kind = request.POST.get("health_kind", "")
    notes = request.POST.get("notes", "").strip()[:1000]
    raw_follow = request.POST.get("health_follow_up", "").strip()
    follow = parse(raw_follow) if raw_follow else None
    if day is None:
        messages.error(request, "Enter the date of the health note.")
    elif day > timezone.localdate():
        messages.error(request, "The health note's date is in the future.")
    elif kind not in HealthNote.Kind.values:
        messages.error(request, "Choose a type: treatment, illness, injury, checkup or other.")
    elif raw_follow and follow is None:
        messages.error(request, "Enter the follow-up date as a date.")
    elif follow and follow < day:
        messages.error(request, "The follow-up date is before the note's date.")
    elif (photos := health_photos(request)) is None:
        pass  # health_photos said what was wrong
    else:
        with transaction.atomic():
            note = HealthNote(rabbit=rabbit, date=day, kind=kind, notes=notes, follow_up_on=follow)
            if follow:
                note.task = Task.objects.create(
                    owner=request.user, rabbit=rabbit, due_on=follow,
                    title=f"Follow up: {note.get_kind_display().lower()} ({rabbit.name})",
                )
            note.save()
            for upload, taken in photos:
                photo = RabbitPhoto(rabbit=rabbit, health_note=note, taken_at=taken or day,
                                    taken_from_metadata=taken is not None, notes=f"{note.get_kind_display()}, {day:%a, %b} {day.day}")
                photo.image.save(upload.name, upload, save=False)
                photo.save()
        messages.success(request, f"Health note added{f', with a follow-up on {follow:%b} {follow.day}' if follow else ''}.")
    return back


@login_required
@require_POST
def health_delete(request, pk):
    note = get_object_or_404(HealthNote, rabbit__owner=request.user, pk=pk)
    with transaction.atomic():
        if note.task_id and note.task.done_at is None:
            note.task.delete()
        note.delete()
    messages.success(request, "The health note was removed.")
    return redirect(f"/rabbits/{note.rabbit_id}/#health")
