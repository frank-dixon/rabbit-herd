def prefetch_keeps_messages(get_response):
    """A link prefetched on hover may never be opened, so it must not use up
    one-time messages meant for the page the keeper actually opens next."""

    def middleware(request):
        response = get_response(request)
        if request.headers.get("Sec-Purpose", "").startswith("prefetch") and hasattr(request, "_messages"):
            request._messages.used = False
        return response

    return middleware




def security_headers(get_response):
    """Headers Django's own middleware doesn't set.

    - Permissions-Policy: only what the app uses (passkeys; the camera for photo
      capture), everything else off.
    - The admin (Unfold) runs Alpine.js, which needs 'unsafe-eval', so /admin/
      gets its own slightly looser policy; the app keeps the strict one.
    - Cache-Control on HTML: pages for a signed-in visitor are private and never
      stored by browsers or proxies (the service worker keeps its own copy for
      offline use). Signed-out pages carry a CSRF token, so they're no-cache.
    """
    from django.conf import settings
    from django.utils.csp import CSP, build_policy

    admin_policy = dict(settings.SECURE_CSP)
    admin_policy["script-src"] = [CSP.SELF, CSP.UNSAFE_EVAL]
    admin_header = build_policy(admin_policy)
    admin_prefix = "/admin/"
    permissions = settings.PERMISSIONS_POLICY
    session_cookie = settings.SESSION_COOKIE_NAME

    def middleware(request):
        if request.path.startswith(admin_prefix):
            response = get_response(request)
            response.headers[str(CSP.HEADER_ENFORCE)] = admin_header
        else:
            response = get_response(request)
        response.headers.setdefault("Permissions-Policy", permissions)
        if "Cache-Control" not in response and response.get("Content-Type", "").startswith("text/html"):
            user = getattr(request, "_cached_user", None)  # only if the view already loaded it
            signed_in = user.is_authenticated if user is not None else session_cookie in request.COOKIES
            response["Cache-Control"] = "private, no-store" if signed_in else "private, no-cache"
        return response

    return middleware
