"""Attempt limits for sign-in, sign-up, password reset, guest creation and admin sign-in.

Counts live in the "ratelimit" cache, a database cache table in Postgres, so every
serverless instance on Vercel shares them (a memory cache would be per instance).
Each POST to a limited view counts once per IP and, where the form names an
account, once per account. Over the limit the request gets the branded 429 page.
If the cache table is missing or the database errors, requests are let through:
a limiter outage must never lock people out.
"""

import hashlib
import logging

from django.core.cache import caches
from django.db import DatabaseError
from django.shortcuts import render
from django.urls import Resolver404, resolve

log = logging.getLogger(__name__)

MIN = 60
# url name -> (bucket, form field naming the account, [(scope, limit, window seconds)])
RULES = {
    "login": ("login", "username", [("ip", 30, 15 * MIN), ("account", 10, 15 * MIN)]),
    "admin:login": ("admin", "username", [("ip", 10, 15 * MIN), ("account", 5, 15 * MIN)]),
    "passkey_login_verify": ("login", None, [("ip", 30, 15 * MIN)]),
    "signup": ("signup", "email", [("ip", 10, 60 * MIN), ("account", 5, 60 * MIN)]),
    "password_reset": ("reset", "email", [("ip", 10, 60 * MIN), ("account", 3, 60 * MIN)]),
    "guest": ("guest", None, [("ip", 10, 60 * MIN)]),
}

MESSAGES = {
    "login": "Too many sign-in attempts. Wait 15 minutes, then try again, or reset your password.",
    "admin": "Too many sign-in attempts. Wait 15 minutes, then try again.",
    "signup": "Too many accounts were started from here. Wait an hour, then try again.",
    "reset": "Too many reset requests. Check your inbox (and spam) for the last email, or try again in an hour.",
    "guest": "Too many guest sessions were started from here. Wait an hour, or create an account.",
}


def client_ip(request):
    """The visitor's IP. Vercel sets X-Forwarded-For with the client first; elsewhere REMOTE_ADDR."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() or request.META.get("HTTP_X_REAL_IP", "")
            or request.META.get("REMOTE_ADDR", "") or "unknown")


def _key(bucket, scope, value):
    digest = hashlib.sha256(value.strip().lower().encode()).hexdigest()[:32]  # no raw emails or IPs in keys
    return f"rl:{bucket}:{scope}:{digest}"


def hit(key, limit, window):
    """Count one attempt; True when this attempt is over the limit."""
    cache = caches["ratelimit"]
    if cache.add(key, 1, window):
        return limit < 1
    try:
        count = cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.add(key, 1, window)
        count = 1
    return count > limit


def rule_for(request):
    try:
        match = resolve(request.path_info)
    except Resolver404:
        return None
    return RULES.get(match.view_name)


def limited(request):
    """The bucket name when this request is over a limit, else None."""
    if request.method != "POST":
        return None
    rule = rule_for(request)
    if not rule:
        return None
    bucket, field, limits = rule
    account = (request.POST.get(field, "") if field else "").strip()
    over = False
    try:
        for scope, limit, window in limits:
            value = client_ip(request) if scope == "ip" else account
            if value and hit(_key(bucket, scope, value), limit, window):
                over = True
    except DatabaseError:
        log.warning("Rate limit cache unavailable; letting the request through.")
        return None
    return bucket if over else None


def middleware(get_response):
    def handle(request):
        bucket = limited(request)
        if bucket:
            return render(request, "_error_page.html", {
                "status": 429, "heading": "Please wait a moment", "line": MESSAGES[bucket],
                "back_href": request.path}, status=429)
        return get_response(request)
    return handle
