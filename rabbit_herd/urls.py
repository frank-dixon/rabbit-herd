from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path, re_path
from django.views.static import serve


def debug_media(request, path):
    """Serve uploaded photos from disk only while DEBUG is on."""
    if not settings.DEBUG:
        raise Http404()
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("rabbits/", include("rabbits.urls")),
    path("", include("pages.urls")),
    re_path(r"^media/(?P<path>.*)$", debug_media),
]
