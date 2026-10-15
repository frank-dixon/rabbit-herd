"""Add, toggle and clear sample content; start and continue the welcome guide."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from rabbits.samples import add_samples, clear_samples, sample_count
from rabbits.samples.service import SCREENS


@login_required
@require_POST
def samples_add(request, screen):
    if screen not in SCREENS:
        messages.error(request, "That screen has no samples.")
        return redirect(request.META.get("HTTP_REFERER") or "index")
    if not request.user.show_samples:
        messages.info(request, "Turn on Show samples in Settings first.")
        return redirect("account")
    add_samples(request.user, screen)
    messages.success(request, "Samples added. Your own records weren't changed.")
    return redirect(request.META.get("HTTP_REFERER") or "index")


@login_required
@require_POST
def samples_toggle(request):
    user = request.user
    user.show_samples = not user.show_samples
    user.save(update_fields=["show_samples"])
    messages.success(request, "Samples shown." if user.show_samples else "Samples hidden. Turn them back on any time.")
    return redirect(request.META.get("HTTP_REFERER") or "account")


@login_required
@require_POST
def samples_clear(request):
    n = clear_samples(request.user)
    messages.success(
        request,
        f"Samples cleared ({n}). Show samples is off — turn it on in Settings to add them again.",
    )
    return redirect(request.META.get("HTTP_REFERER") or "account")


@login_required
@require_POST
def guide_restart(request):
    user = request.user
    user.guide_step = "today"
    user.guide_dismissed_at = None
    user.save(update_fields=["guide_step", "guide_dismissed_at"])
    return redirect("index")


@login_required
@require_POST
def guide_continue(request):
    step = request.user.guide_step or "today"
    targets = {
        "today": "index", "rabbits": "rabbit_list", "litters": "litter_list",
        "pairings": "pairing_list", "weights": "weights", "tasks": "task_list",
        "health": "health", "settings": "account", "done": "account",
    }
    return redirect(targets.get(step, "index"))


@login_required
@require_POST
def guide_skip(request):
    user = request.user
    user.guide_dismissed_at = timezone.now()
    user.guide_step = "done"
    user.save(update_fields=["guide_dismissed_at", "guide_step"])
    messages.info(request, "Guide closed. Restart any time in Settings.")
    return redirect(request.META.get("HTTP_REFERER") or "index")


@login_required
@require_POST
def guide_step(request):
    """Advance or go back: body step=<id>."""
    step = (request.POST.get("step") or "").strip()
    user = request.user
    user.guide_step = step
    if step == "done":
        user.guide_dismissed_at = timezone.now()
    user.save(update_fields=["guide_step", "guide_dismissed_at"] if step == "done" else ["guide_step"])
    return redirect(request.META.get("HTTP_REFERER") or "index")
