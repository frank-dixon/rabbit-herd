"""Installable app: the web manifest, the service worker and the offline page.

The service worker is served from the site root so its scope covers every
page. It is rendered as a template so it can name the hashed CSS and JS
files; its version changes whenever those files change, which makes the
browser replace the old cache.
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
    ]


@cache_control(max_age=3600)
def manifest(request):
    data = {
        "name": settings.APP_NAME,
        "short_name": settings.APP_NAME,
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#e5e5e5",
        "theme_color": "#262626",
        "icons": [
            {"src": static("icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("icons/maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


@cache_control(no_cache=True)
def service_worker(request):
    assets = shell_assets()
    version = hashlib.sha256("|".join(assets).encode()).hexdigest()[:12]
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
