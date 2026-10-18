"""Hand a stored photo to its (already checked) owner.

With the private S3 bucket (PHOTO_STORAGE=s3) the app answers with a redirect
to a short-lived signed URL (PHOTO_SIGNED_URL_SECONDS, one hour by default),
so the image bytes come straight from storage instead of through a Django
function. The app URL (/rabbits/photos/<id>/?w=&v=) stays the stable key the
service worker caches offline. Callers must check ownership first; nothing
here does. With local files (dev, the Mac) the file is streamed as before.
"""

import mimetypes

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect


def signed_urls_on():
    return getattr(settings, "PHOTO_SIGNED_URLS", False)


def deliver(request, storage, name):
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    if not content_type.startswith("image/"):
        content_type = "application/octet-stream"
    if signed_urls_on():
        seconds = getattr(settings, "PHOTO_SIGNED_URL_SECONDS", 3600)
        url = storage.url(name, parameters={"ResponseContentType": content_type}, expire=seconds)
        response = HttpResponseRedirect(url)
        # The browser may reuse this redirect a little less long than the link lives.
        response["Cache-Control"] = f"private, max-age={max(seconds - 300, 60)}"
        return response
    try:
        handle = storage.open(name, "rb")
    except (FileNotFoundError, OSError):
        raise Http404("This photo's file is missing.")
    response = FileResponse(handle, content_type=content_type)
    # The URL carries a version from the file name, so it can be kept long.
    response["Cache-Control"] = "private, max-age=2592000, immutable" if request.GET.get("v") else "private, max-age=3600"
    response["Content-Disposition"] = "inline"
    return response
