"""Idempotent writes for queued (offline) and double-submitted forms.

A form carries a client-made ``op_id``. The first post that applies claims it
in SyncOp inside the same transaction as the write; any later post with that
op_id (a retry, a second tab) is answered as already done and writes nothing.
Queue flushes send ``X-BB-Queue: 1`` and get JSON: 201 applied, 200 duplicate,
422 with the form error so the entry is kept and shown, never dropped."""

import uuid

from django.db import IntegrityError, transaction
from django.http import JsonResponse

from .models import SyncOp


def op_id(request):
    try:
        return uuid.UUID(request.POST.get("op_id", ""))
    except ValueError:
        return None


def is_queue(request):
    return request.headers.get("X-BB-Queue") == "1"


def already_applied(request):
    op = op_id(request)
    return op is not None and SyncOp.objects.filter(op_id=op, owner=request.user).exists()


def claim(request, kind):
    """Call inside the write's transaction. False when another post won."""
    op = op_id(request)
    if op is None:
        return True
    try:
        with transaction.atomic():
            SyncOp.objects.create(op_id=op, owner=request.user, kind=kind)
    except IntegrityError:
        return False
    return True


def applied(status=201, **extra):
    return JsonResponse({"ok": True, **extra}, status=status)


def duplicate():
    return applied(status=200, duplicate=True)


def invalid(error):
    return JsonResponse({"ok": False, "error": error}, status=422)


QUEUE_FAILED = "This change didn't sync. Open it and save again."


def queueable(kind):
    """Lets a plain POST view take queued (offline) posts and double submits safely.

    The view runs inside one transaction with the op_id claim. A redirect with no
    error message counts as applied; anything else (a re-rendered form, an error
    message) rolls the claim back so the same op_id can be tried again. Queue
    flushes get the JSON answers above instead of the page, and the toasts the
    view queued are dropped so they don't pop up later on some other page."""
    from functools import wraps

    from django.contrib import messages

    def queued_messages(request):
        store = getattr(request, "_messages", None)
        return getattr(store, "_queued_messages", [])

    def wrap(view):
        @wraps(view)
        def inner(request, *args, **kwargs):
            queued = is_queue(request)
            if request.method != "POST" or (op_id(request) is None and not queued):
                return view(request, *args, **kwargs)
            if already_applied(request):
                if queued:
                    return duplicate()
                return view_redirect(request)
            before = len(queued_messages(request))
            with transaction.atomic():
                if not claim(request, kind):
                    return duplicate() if queued else view_redirect(request)
                response = view(request, *args, **kwargs)
                added = queued_messages(request)[before:]
                errors = [m for m in added if m.level >= messages.ERROR]
                ok = response.status_code in (301, 302, 303) and not errors
                if not ok:
                    transaction.set_rollback(True)
            if not queued:
                return response
            del queued_messages(request)[before:]
            if ok:
                return applied()
            return invalid(str(errors[0].message) if errors else QUEUE_FAILED)
        return inner
    return wrap


def view_redirect(request):
    """Where a repeated plain post goes: its safe next, else the page it came from."""
    from django.shortcuts import redirect
    from django.utils.http import url_has_allowed_host_and_scheme

    for url in (request.POST.get("next", ""), request.META.get("HTTP_REFERER", "")):
        if url and url_has_allowed_host_and_scheme(url, {request.get_host()}, require_https=request.is_secure()):
            return redirect(url)
    return redirect("/")
