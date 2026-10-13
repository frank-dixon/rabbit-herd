"""Installable app: the web manifest, the service worker and the offline page.

The service worker is served from the site root so its scope covers every
page. It is rendered as a template so it can name the hashed CSS and JS
files; its version changes whenever those files' contents change (not just
their names, which stay the same with DEBUG on), which makes the browser
replace the old cache.
"""

import hashlib

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import cache_control


def shell_assets():
    return [
        static("css/app.css"),
        static("js/app.js"),
        static("icons/icon-192.png"),
        static("icons/apple-touch-icon.png"),
        static("fonts/instrument-sans-latin-var.woff2"),
        static("fonts/dm-mono-latin-400-normal.woff2"),
        static("fonts/dm-mono-latin-500-normal.woff2"),
    ]


@cache_control(max_age=3600)
def manifest(request):
    data = {
        "name": settings.APP_NAME,
        "short_name": "Bramble",  # fits under a home-screen icon
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#F5F6F5",
        "theme_color": "#F5F6F5",
        "description": "Private records for your rabbitry: herd, pedigrees, litters, weights and breeder contacts.",
        "icons": [
            {"src": static("icons/icon.svg"), "sizes": "any", "type": "image/svg+xml"},
            {"src": static("icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("icons/maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


SHELL_FILES = ("css/app.css", "js/app.js")


def shell_fingerprint():
    """A hash of the built CSS and JS, so a rebuild always ships a new worker."""
    from django.contrib.staticfiles import finders
    from django.contrib.staticfiles.storage import staticfiles_storage

    digest = hashlib.sha256()
    for name in SHELL_FILES:
        path = finders.find(name)
        if not path:
            try:
                path = staticfiles_storage.path(name)
            except NotImplementedError:
                path = None
        try:
            with open(path, "rb") as handle:
                digest.update(handle.read())
        except (OSError, TypeError):
            digest.update(b"missing:" + name.encode())
    return digest.hexdigest()


@cache_control(no_cache=True)
def service_worker(request):
    assets = shell_assets()
    version = hashlib.sha256(("|".join(assets) + shell_fingerprint()).encode()).hexdigest()[:12]
    response = render(
        request,
        "pwa/sw.js",
        {"assets": assets, "version": version},
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request):
    return render(request, "pwa/offline.html", {})
