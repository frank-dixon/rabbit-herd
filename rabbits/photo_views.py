"""Rabbit photos: serving them to their owner only, and the Photos page.

Photos never go out through a public media URL. Each request is checked
against the signed-in keeper, and anyone else gets a 404, so a photo's
address reveals nothing and works for no one else. Every change is a POST
with a CSRF token and redirects afterwards, so a refresh never repeats it.
"""

import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .forms import PhotoNotesForm, PhotoUploadForm
from .models import Rabbit, RabbitPhoto


def owned_photo(user, pk):
    return get_object_or_404(RabbitPhoto.objects.select_related("rabbit"), pk=pk, rabbit__owner=user)


def photos_url(rabbit, anchor=""):
    url = reverse("rabbit_photos", args=[rabbit.pk])
    return f"{url}#{anchor}" if anchor else url


@login_required
@require_GET
def photo_file(request, pk):
    photo = owned_photo(request.user, pk)
    try:
        handle = photo.image.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404("This photo's file is missing.")
    content_type = mimetypes.guess_type(photo.image.name)[0] or "application/octet-stream"
    if not content_type.startswith("image/"):
        content_type = "application/octet-stream"
    response = FileResponse(handle, content_type=content_type)
    response["Cache-Control"] = "private, max-age=3600"
    response["Content-Disposition"] = "inline"
    return response


@login_required
def rabbit_photos(request, pk):
    """List a rabbit's photos with their notes, and take a new upload."""
    rabbit = get_object_or_404(Rabbit, pk=pk, owner=request.user)
    form = PhotoUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            first_main = not rabbit.photos.filter(is_main=True).exists()
            photo = RabbitPhoto(rabbit=rabbit, notes=form.cleaned_data["notes"], is_main=first_main)
            photo.image.save(form.cleaned_data["image"].name, form.cleaned_data["image"], save=False)
            photo.save()
        if first_main:
            messages.success(request, f"The photo was added. It's {rabbit.name}'s main photo, since it's the first one.")
        else:
            messages.success(request, "The photo was added.")
        return redirect(photos_url(rabbit, f"photo-{photo.pk}"))
    return render(
        request,
        "rabbits/photos.html",
        {"rabbit": rabbit, "photos": list(rabbit.photos.all()), "form": form},
        status=400 if request.method == "POST" else 200,
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
    return redirect(photos_url(photo.rabbit, f"photo-{photo.pk}"))


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
    transaction.on_commit(lambda: storage.delete(name))
    if replacement:
        messages.success(request, "The photo was deleted. The oldest remaining photo is now the main photo.")
    else:
        messages.success(request, "The photo was deleted.")
    return redirect(photos_url(rabbit))


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
    return redirect(photos_url(photo.rabbit, f"photo-{photo.pk}"))
