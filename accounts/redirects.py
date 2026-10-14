import re
from urllib.parse import urlsplit

from django.apps import apps
from django.shortcuts import resolve_url
from django.utils.http import url_has_allowed_host_and_scheme


def is_safe_next(request, candidate):
    """True when a login `next` value stays on this host."""
    candidate = (candidate or "").strip()
    if not candidate or candidate.startswith("//") or candidate.startswith("/\\"):
        return False
    return url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )


# Record pages a `next` value can point at: (path pattern, model, list page).
OWNED_PAGES = [
    (r"^/litters/(\d+)/", "rabbits.Litter", "/litters/"),
    (r"^/rabbits/(\d+)/", "rabbits.Rabbit", "/rabbits/"),
    (r"^/pairings/(\d+)/", "rabbits.Pairing", "/pairings/"),
    (r"^/programs/(\d+)/", "rabbits.Program", "/programs/"),
    (r"^/contacts/(\d+)/", "rabbits.Contact", "/contacts/"),
    (r"^/locations/(\d+)/", "rabbits.Location", "/locations/"),
]


def owned_next(user, candidate):
    """candidate, or its section list when it names another account's record.

    A sign-in page reached from one account's page (say the demo herd's
    /litters/431/) carries that URL in `next`. Signing in as a different
    account would then land on a 404, because records are owner-scoped."""
    path = urlsplit(candidate).path
    for pattern, label, list_url in OWNED_PAGES:
        match = re.match(pattern, path)
        if match:
            model = apps.get_model(label)
            if not model.objects.filter(owner=user, pk=int(match.group(1))).exists():
                return list_url
            break
    return candidate


def safe_next_url(request, default="index", candidate=None):
    if candidate is None:
        candidate = request.POST.get("next", request.GET.get("next", ""))
    if is_safe_next(request, candidate):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return owned_next(user, candidate)
        return candidate
    return resolve_url(default)
