"""Branded error pages.

400, 403 and 404 render through the normal page shell (with the request, so the
side menu and theme apply). 500 uses Django's default handler, which renders
templates/500.html with an empty context: that template is self-contained, with
no context processors, url lookups, static tags or database access.

On a DEBUG machine (Frank's Mac) Django shows its technical 404 page instead of
404.html. BrandedDebug404 swaps in the branded page there too, unless the URL
has ?debug=1 or settings.SHOW_DEBUG_404 is on.
"""

import re

from django.conf import settings
from django.shortcuts import render

# What a missing record was, by the start of the path: (pattern, noun, list URL).
RECORDS = [
    (r"^/litters/\d+/", "litter", "/litters/"),
    (r"^/rabbits/\d+/", "rabbit", "/rabbits/"),
    (r"^/pairings/\d+/", "pairing", "/pairings/"),
    (r"^/programs/\d+/", "program", "/programs/"),
    (r"^/tasks/\d+/", "task", "/tasks/"),
    (r"^/contacts/\d+/", "contact", "/contacts/"),
    (r"^/locations/\d+/", "location", "/locations/"),
    (r"^/waitlist/\d+/", "waitlist entry", "/waitlist/"),
    (r"^/costs/\d+/", "cost", "/costs/"),
]

PAGES = {
    400: ("Something was wrong with that request", "The page couldn't read what was sent. Go back and try again."),
    403: ("You don't have access to this page", "It may belong to another account, or you may need to sign in again."),
    404: ("Page not found", "The page you're looking for doesn't exist or has moved."),
}


def describe(status, path):
    """(heading, line, back_href) for an error page at path."""
    heading, line = PAGES[status]
    back = "/"
    for pattern, noun, list_url in RECORDS:
        if re.match(pattern, path or ""):
            back = list_url
            if status == 404:
                heading = f"{noun.capitalize()} not found"
                line = f"This {noun} may have been deleted or moved."
            break
    return heading, line, back


def render_error(request, status):
    heading, line, back = describe(status, request.path)
    response = render(request, f"{status}.html", {"heading": heading, "line": line, "back_href": back, "status": status}, status=status)
    response.branded = True
    return response


def bad_request(request, exception=None):
    return render_error(request, 400)


def permission_denied(request, exception=None):
    return render_error(request, 403)


def page_not_found(request, exception=None):
    return render_error(request, 404)


def csrf_failure(request, reason=""):
    """A form posted with an old or missing CSRF token, usually a page left open too long."""
    heading = "This form has expired"
    line = "Go back, reload the page and try again."
    response = render(request, "403.html", {"heading": heading, "line": line, "back_href": "/", "status": 403}, status=403)
    response.branded = True
    return response


def show_debug_404(request):
    return getattr(settings, "SHOW_DEBUG_404", False) or request.GET.get("debug") == "1"


def branded_debug_404(get_response):
    """With DEBUG on, replace Django's technical 404 HTML with the branded page."""

    def middleware(request):
        response = get_response(request)
        if (
            settings.DEBUG
            and response.status_code == 404
            and "text/html" in response.get("Content-Type", "")
            and not getattr(response, "branded", False)
            and not show_debug_404(request)
        ):
            response = page_not_found(request)
        return response

    return middleware
