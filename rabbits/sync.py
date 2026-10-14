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
