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


SEEN_EVERY_SECONDS = 600


def touch_last_seen(get_response):
    """Record when an account was last used, at most every ten minutes per
    session: demo copies are deleted a day after last use and empty guests
    are deactivated after seven days (accounts.demo, accounts.guest). A guest's
    session cookie is pushed a year out each time, so the herd stays on the device."""
    import time

    def middleware(request):
        response = get_response(request)
        # Only when the view already loaded the user (so /sw.js and static stay query-free).
        if not hasattr(request, "_cached_user"):
            return response
        session = getattr(request, "session", None)
        if session is None:
            return response
        now = int(time.time())
        if now - int(session.get("seen_at", 0) or 0) < SEEN_EVERY_SECONDS:
            return response
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            from django.contrib.auth import get_user_model
            from django.utils import timezone

            # request.user can still be the lazy wrapper here, so not type(user).objects.
            get_user_model().objects.filter(pk=user.pk).update(last_seen_at=timezone.now())
            session["seen_at"] = now
            if user.is_guest and not user.is_demo:
                from accounts.guest import GUEST_SESSION_AGE

                session.set_expiry(GUEST_SESSION_AGE)  # slides: a year from this visit
        return response

    return middleware


def _seen_on_login(sender, request, user, **kwargs):
    import time

    from django.utils import timezone

    type(user).objects.filter(pk=user.pk).update(last_seen_at=timezone.now())
    if request is not None and hasattr(request, "session"):
        request.session["seen_at"] = int(time.time())


def connect_login_signal():
    from django.contrib.auth.signals import user_logged_in

    user_logged_in.connect(_seen_on_login, dispatch_uid="pages-seen-on-login")
