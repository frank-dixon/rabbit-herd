"""Rabbit photos: serving them to their owner only, and the Photos page.

Photos never go out through a public media URL. Each request is checked
against the signed-in keeper, and anyone else gets a 404, so a photo's
address reveals nothing and works for no one else. Every change is a POST
with a CSRF token and redirects afterwards, so a refresh never repeats it.
"""

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import photo_processing
from .photo_delivery import deliver
from .renditions import delete_renditions, rendition
from .forms import PhotoNotesForm, PhotoUploadForm
from .models import Rabbit, RabbitPhoto, valid_taken_date


def owned_photo(user, pk):
    return get_object_or_404(RabbitPhoto.objects.select_related("rabbit"), pk=pk, rabbit__owner=user)


def photos_url(rabbit, anchor="", request=None):
    """Where a photo change goes back to: the Photos page, or the Photos card
    on the rabbit's page when the form sent back_to=detail. Only those two
    fixed places are allowed, so this can't be used to redirect elsewhere."""
    if request is not None and request.POST.get("back_to") == "detail":
        return reverse("rabbit_detail", args=[rabbit.pk]) + "#photos"
    url = reverse("rabbit_photos", args=[rabbit.pk])
    return f"{url}#{anchor}" if anchor else url


@login_required
@require_GET
def photo_file(request, pk):
    photo = owned_photo(request.user, pk)
    name = photo.image.name
    width = request.GET.get("w", "")
    if width.isdigit():
        name = rendition(photo.image, int(width)) or name
    return deliver(request, photo.image.storage, name)


@login_required
def rabbit_photos(request, pk):
    """List a rabbit's photos with their notes, and take a new upload."""
    rabbit = get_object_or_404(Rabbit, pk=pk, owner=request.user)
    form = PhotoUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            first_main = not rabbit.photos.filter(is_main=True).exists()
            taken = valid_taken_date(form.taken_date(), rabbit.birth_date)
            photo = RabbitPhoto(
                rabbit=rabbit, notes=form.cleaned_data["notes"], is_main=first_main,
                taken_at=taken, taken_from_metadata=taken is not None,
            )
            photo.image.save(form.cleaned_data["image"].name, form.cleaned_data["image"], save=False)
            photo.save()
        if first_main:
            messages.success(request, f"The photo was added. It's {rabbit.name}'s main photo, since it's the first one.")
        else:
            messages.success(request, "The photo was added.")
        return redirect(photos_url(rabbit, f"photo-{photo.pk}", request))
    if request.method == "POST":
        for errors in form.errors.values():
            messages.error(request, errors[0])
        return redirect(photos_url(rabbit, request=request))
    return render(
        request,
        "rabbits/photos.html",
        {"rabbit": rabbit, "photos": list(rabbit.photos.all()), "upload_form": PhotoUploadForm(), "wide": True},
    )


@login_required
@require_POST
def photo_notes(request, pk):
    photo = owned_photo(request.user, pk)
    form = PhotoNotesForm(request.POST)
    if form.is_valid():
        photo.notes = form.cleaned_data["notes"]
        photo.save(update_fields=["notes"])
        messages.success(request, "The notes were saved.")
    else:
        messages.error(request, form.errors["notes"][0])
    return redirect(photos_url(photo.rabbit, f"photo-{photo.pk}", request))


@login_required
@require_POST
def photo_delete(request, pk):
    """Delete a photo and its file. If it was the main photo, the oldest
    remaining photo becomes the main one, so the rabbit keeps a picture."""
    photo = owned_photo(request.user, pk)
    rabbit = photo.rabbit
    was_main = photo.is_main
    name = photo.image.name
    storage = photo.image.storage
    with transaction.atomic():
        photo.delete()
        replacement = None
        if was_main:
            replacement = rabbit.photos.order_by("uploaded_at", "pk").first()
            if replacement:
                replacement.is_main = True
                replacement.save(update_fields=["is_main"])
    transaction.on_commit(lambda: (storage.delete(name), delete_renditions(storage, name)))
    if replacement:
        messages.success(request, "The photo was deleted. The oldest remaining photo is now the main photo.")
    else:
        messages.success(request, "The photo was deleted.")
    return redirect(photos_url(rabbit, request=request))


@login_required
@require_POST
def photo_set_main(request, pk):
    """Make this photo the rabbit's main photo, and the old main an extra."""
    photo = owned_photo(request.user, pk)
    with transaction.atomic():
        # Lock the rabbit so two quick taps can't leave two main photos.
        Rabbit.objects.select_for_update().get(pk=photo.rabbit_id)
        photo.rabbit.photos.filter(is_main=True).exclude(pk=photo.pk).update(is_main=False)
        if not photo.is_main:
            photo.is_main = True
            photo.save(update_fields=["is_main"])
    messages.success(request, f"This is now {photo.rabbit.name}'s main photo.")
    return redirect(photos_url(photo.rabbit, f"photo-{photo.pk}", request))


@login_required
@require_POST
def photo_rotate(request, pk):
    """Turn a photo a quarter turn left or right, saved as a new file so
    browsers don't keep showing the old one from cache."""
    photo = owned_photo(request.user, pk)
    direction = request.POST.get("direction")
    if direction not in ("left", "right"):
        messages.error(request, "Choose left or right to rotate the photo.")
        return redirect(photos_url(photo.rabbit, f"photo-{photo.pk}", request))
    old_name, storage = photo.image.name, photo.image.storage
    try:
        new_file = photo_processing.rotate_photo(photo.image, direction)
    except (OSError, ValueError):
        messages.error(request, "That photo couldn't be rotated.")
        return redirect(photos_url(photo.rabbit, f"photo-{photo.pk}", request))
    with transaction.atomic():
        photo.image.save(new_file.name, new_file, save=False)
        photo.save(update_fields=["image"])
        transaction.on_commit(lambda: (storage.delete(old_name), delete_renditions(storage, old_name)))
    messages.success(request, f"The photo was rotated {direction}.")
    return redirect(photos_url(photo.rabbit, f"photo-{photo.pk}", request))


@login_required
@require_POST
def photo_date(request, pk):
    """Set or clear the date a photo was taken. Blank clears it, so the
    badge falls back to the upload date."""
    photo = owned_photo(request.user, pk)
    raw = request.POST.get("taken_at", "").strip()
    if not raw:
        photo.taken_at, photo.taken_from_metadata = None, False
        photo.save(update_fields=["taken_at", "taken_from_metadata"])
        messages.success(request, "The date was cleared. The photo shows the day it was added.")
        return redirect(photos_url(photo.rabbit, f"photo-{photo.pk}", request))
    try:
        value = datetime.date.fromisoformat(raw)
    except ValueError:
        value = None
    if value is None:
        messages.error(request, "Pick the date from the calendar.")
    elif valid_taken_date(value, photo.rabbit.birth_date) is None:
        messages.error(request, "Pick a date between the rabbit's birth and today.")
    else:
        photo.taken_at, photo.taken_from_metadata = value, False
        photo.save(update_fields=["taken_at", "taken_from_metadata"])
        messages.success(request, "The date was saved.")
    return redirect(photos_url(photo.rabbit, f"photo-{photo.pk}", request))
