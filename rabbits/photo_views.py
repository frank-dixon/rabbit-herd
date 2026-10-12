"""Rabbit photos: serving them to their owner only.

Photos never go out through a public media URL. Each request is checked
against the signed-in keeper, and anyone else gets a 404, so a photo's
address reveals nothing and works for no one else.
"""

import mimetypes

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import RabbitPhoto


def owned_photo(user, pk):
    return get_object_or_404(RabbitPhoto.objects.select_related("rabbit"), pk=pk, rabbit__owner=user)


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
