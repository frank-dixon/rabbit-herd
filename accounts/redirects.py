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


def safe_next_url(request, default="index", candidate=None):
    if candidate is None:
        candidate = request.POST.get("next", request.GET.get("next", ""))
    if is_safe_next(request, candidate):
        return candidate
    return resolve_url(default)
