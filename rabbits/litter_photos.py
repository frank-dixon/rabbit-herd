"""Litter and kit photos.

A litter can have one photo; each kit shows it until the kit has its own.
With no litter photo, a stock newborn photo stands in, picked from the
parents' coats and tagged Placeholder. Photos are served only to their
owner, like rabbit photos. Uploads go through the same cleaning as rabbit
photos (size and type checks, metadata stripped)."""

import mimetypes

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.templatetags.static import static
from django.urls import reverse

from .models import Litter, LitterKit, OutsideRabbit, RabbitPhoto
from .photo_processing import clean_photo
from .renditions import rendition

# Stock newborn photos by coat. Frank's own photos, plus one CC0 broken litter.
PLACEHOLDERS = {
    "pink": "placeholders/newborn-pink.jpg",
    "dark": "placeholders/newborn-dark.jpg",
    "blue": "placeholders/newborn-blue.jpg",
    "red": "placeholders/newborn-red.jpg",
    "broken": "placeholders/newborn-broken.jpg",
    "default": "placeholders/nest-empty.jpg",
}
BROKEN = ("broken", "charlie", "tri-color", "tricolor", "harlequin", "magpie", "dutch", "english spot")
COATS = (
    ("pink", ("ruby-eyed white", "rew", "blue-eyed white", "bew", "white", "pointed", "himalayan", "californian", "frosty", "pink")),
    ("blue", ("blue", "lilac", "lavender")),
    ("dark", ("black", "chocolate", "havana", "seal", "ebony", "otter", "smoke")),
    ("red", ("red", "fawn", "orange", "cream", "tort", "frosted pearl", "sable")),
)


def coat(color):
    """The placeholder group a color reads as, or None (agouti colors and
    anything unknown have no stock photo of their own)."""
    text = (color or "").lower()
    if any(word in text for word in BROKEN):
        return "broken"
    for key, words in COATS:
        if any(word in text for word in words):
            return key
    return None


def placeholder_key(doe_color, buck_color):
    """Broken if either parent is broken; else the parents' shared coat, or the
    one that is known, or the doe's when they differ; else an empty nest."""
    doe, buck = coat(doe_color), coat(buck_color)
    if "broken" in (doe, buck):
        return "broken"
    return doe or buck or "default"


def placeholder_url(litter):
    return static(PLACEHOLDERS[placeholder_key(litter.pairing.doe.color, litter.pairing.buck.color)])


def litter_photo_url(litter, width=480):
    if not litter.photo:
        return None
    return f"{reverse('litter_photo', args=[litter.pk])}?w={width}&v={litter.photo.name.rsplit('/', 1)[-1][:8]}"


def kit_photo_url(slot, width=480):
    if not slot.photo:
        return None
    return f"{reverse('kit_photo', args=[slot.litter_id, slot.number])}?w={width}&v={slot.photo.name.rsplit('/', 1)[-1][:8]}"


def rabbit_photo_url(photo, width=480):
    return f"{reverse('rabbit_photo_file', args=[photo.pk])}?w={width}&v={photo.pk}"


def serve(request, field):
    if not field:
        raise Http404("No photo.")
    name = field.name
    width = request.GET.get("w", "")
    if width.isdigit():
        name = rendition(field, int(width)) or name
    try:
        handle = field.storage.open(name, "rb")
    except (FileNotFoundError, OSError):
        raise Http404("This photo's file is missing.")
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    response = FileResponse(handle, content_type=content_type if content_type.startswith("image/") else "application/octet-stream")
    response["Cache-Control"] = "private, max-age=2592000, immutable" if request.GET.get("v") else "private, max-age=3600"
    response["Content-Disposition"] = "inline"
    return response


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


def replace(field, content):
    """Save the cleaned picture into the field and remove the old file."""
    old = field.name
    field.save(content.name, content, save=True)
    if old and old != field.name:
        try:
            field.storage.delete(old)
        except OSError:
            pass


def answer(request, back, url=None, error=None):
    if wants_json(request):
        return JsonResponse({"url": url} if not error else {"error": error}, status=400 if error else 200)
    if error:
        from django.contrib import messages

        messages.error(request, error)
    return redirect(back)


@login_required
def litter_photo(request, pk):
    """GET: the litter photo. POST: replace it."""
    litter = get_object_or_404(Litter.objects.select_related("pairing__doe", "pairing__buck"), pk=pk, owner=request.user)
    if request.method != "POST":
        return serve(request, litter.photo)
    back = reverse("litter_detail", args=[litter.pk]) + "#litter"
    if litter.converted_at:
        return answer(request, back, error="This litter is archived and read-only.")
    try:
        content = clean_photo(request.FILES["photo"])
    except KeyError:
        return answer(request, back, error="Choose a photo to upload.")
    except ValidationError as error:
        return answer(request, back, error=error.messages[0])
    replace(litter.photo, content)
    return answer(request, back, url=litter_photo_url(litter))


@login_required
def kit_photo(request, pk, number):
    """GET: a kit's own photo. POST: set it. A kit already in the herd gets the
    photo as its main rabbit photo, so its own page shows it too."""
    slot = get_object_or_404(LitterKit.objects.select_related("litter", "rabbit"), litter__pk=pk, litter__owner=request.user, number=number)
    if request.method != "POST":
        return serve(request, slot.photo)
    back = reverse("litter_detail", args=[pk]) + "#kits"
    if slot.litter.converted_at:
        return answer(request, back, error="This litter is archived and read-only.")
    try:
        content = clean_photo(request.FILES["photo"])
    except KeyError:
        return answer(request, back, error="Choose a photo to upload.")
    except ValidationError as error:
        return answer(request, back, error=error.messages[0])
    if slot.rabbit_id:
        with transaction.atomic():
            slot.rabbit.photos.filter(is_main=True).update(is_main=False)
            photo = RabbitPhoto(rabbit=slot.rabbit, is_main=True)
            photo.image.save(content.name, content, save=True)
        return answer(request, back, url=rabbit_photo_url(photo))
    replace(slot.photo, content)
    return answer(request, back, url=kit_photo_url(slot))


def copy_to_rabbit(slot, litter):
    """At conversion: the kit's own photo, else the litter photo, becomes the
    new rabbit's main photo. A placeholder is never copied."""
    from django.core.files.base import ContentFile

    source = slot.photo or litter.photo
    if not source:
        return None
    try:
        with source.storage.open(source.name, "rb") as handle:
            data = handle.read()
    except OSError:
        return None
    photo = RabbitPhoto(rabbit=slot.rabbit, is_main=not slot.rabbit.photos.filter(is_main=True).exists())
    photo.image.save(source.name.rsplit("/", 1)[-1], ContentFile(data), save=True)
    return photo


def coat_placeholder_url(color):
    """The stock photo for one coat, by the same picker litters use."""
    return static(PLACEHOLDERS[coat(color) or "default"])


def outside_photo_url(outside, width=480):
    if not outside.photo:
        return None
    return f"{reverse('outside_photo', args=[outside.pk])}?w={width}&v={outside.photo.name.rsplit('/', 1)[-1][:8]}"


@login_required
def outside_photo(request, pk):
    """GET: an outside ancestor's photo. POST: set it (or remove it with remove=1)."""
    outside = get_object_or_404(OutsideRabbit, pk=pk, owner=request.user)
    if request.method != "POST":
        return serve(request, outside.photo)
    back = request.POST.get("next", "")
    if not back.startswith("/") or back.startswith("//"):
        back = reverse("rabbit_list")
    if request.POST.get("remove"):
        if outside.photo:
            outside.photo.delete(save=True)
        return answer(request, back)
    try:
        content = clean_photo(request.FILES["photo"])
    except KeyError:
        return answer(request, back, error="Choose a photo to upload.")
    except ValidationError as error:
        return answer(request, back, error=error.messages[0])
    replace(outside.photo, content)
    return answer(request, back, url=outside_photo_url(outside))
