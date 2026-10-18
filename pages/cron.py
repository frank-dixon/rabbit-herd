"""Vercel Cron entry point (vercel.json "crons"). Vercel calls it with
"Authorization: Bearer <CRON_SECRET>"; without CRON_SECRET set it answers 404,
so the address does nothing on a server that isn't configured for it."""

import hmac
import os

from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def daily(request):
    secret = os.environ.get("CRON_SECRET", "")
    given = request.headers.get("Authorization", "")
    if not secret or not hmac.compare_digest(given.encode(), f"Bearer {secret}".encode()):
        raise Http404
    from accounts.demo import prune_demo_accounts
    from accounts.guest import deactivate_empty_guests
    from rabbits import purge

    result = {k: v for k, v in purge.run().items()}
    result["demo accounts"] = prune_demo_accounts()
    result["empty guests"] = deactivate_empty_guests()
    return JsonResponse(result)
