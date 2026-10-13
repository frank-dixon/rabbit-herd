"""Named breeding schedules: add and edit them (one form for both), pick one
for a doe, override it on a pairing, and optionally move existing litters
onto the new dates. Litters keep the schedule they started with until asked."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import BreedingSchedule, Litter, Pairing, Rabbit, prefs
from .settings_forms import BreedingScheduleForm

FOLLOW, STANDARD = "doe", "standard"


def options(user, follow_label=None):
    """(value, label) pairs for a schedule select. follow_label adds the 'use the doe's' choice first."""
    rows = [(FOLLOW, follow_label)] if follow_label else []
    standard = prefs(user)
    rows.append((STANDARD, f"Standard · due day {standard.gestation_days}"))
    rows += [(str(s.pk), f"{s.name} · due day {s.gestation_days}") for s in BreedingSchedule.objects.filter(owner=user)]
    return rows


def parse(user, raw, allow_follow=False):
    """FOLLOW, None (Standard) or a BreedingSchedule; False when the value is not valid."""
    raw = (raw or "").strip()
    if raw == FOLLOW and allow_follow:
        return FOLLOW
    if raw in ("", STANDARD):
        return None
    if raw.isdigit():
        found = BreedingSchedule.objects.filter(owner=user, pk=int(raw)).first()
        if found:
            return found
    return False


def value_for(schedule):
    return str(schedule.pk) if schedule else STANDARD


def open_litters(qs):
    """Litters still running: not yet weaned and not processed."""
    return qs.filter(weaned=False, processed=False)


def recalculate(litters, schedule):
    return Litter.objects.filter(pk__in=[l.pk for l in litters]).update(breeding_schedule=schedule)


def moved_text(count):
    if not count:
        return ""
    return f" {count} open litter{'s' if count != 1 else ''} moved to the new dates."


@login_required
def schedule_form(request, pk=None):
    instance = get_object_or_404(BreedingSchedule, owner=request.user, pk=pk) if pk else None
    if instance is None:
        s = prefs(request.user)
        instance = BreedingSchedule(owner=request.user, **{f: getattr(s, f) for f in (
            "gestation_days", "palpate_day", "nest_box_day", "wean_age", "process_age", "rebreed_days")})
    adding = instance.pk is None
    form = BreedingScheduleForm(request.POST or None, instance=instance, owner=request.user)
    if request.method == "POST" and form.is_valid():
        schedule = form.save()
        moved = 0
        if not adding and request.POST.get("recalculate"):
            moved = recalculate(open_litters(Litter.objects.filter(owner=request.user)).exclude(
                breeding_schedule=schedule).filter(pairing__doe__breeding_schedule=schedule, pairing__breeding_schedule__isnull=True,
                                                   pairing__standard_schedule=False), schedule)
        messages.success(request, f"{schedule.name} {'added' if adding else 'saved'}." + moved_text(moved))
        return redirect(reverse("account") + "#schedule")
    items = [{"anchor": f"id_{name}", "message": e} for name, errs in form.errors.items() for e in errs]
    return render(request, "rabbits/schedule_form.html", {
        "form": form, "adding": adding, "schedule": None if adding else instance, "items": items,
        "uses": 0 if adding else instance.does.count(),
    }, status=400 if form.errors else 200)


@login_required
@require_POST
def schedule_delete(request, pk):
    schedule = get_object_or_404(BreedingSchedule, owner=request.user, pk=pk)
    name = schedule.name
    schedule.delete()
    messages.success(request, f"{name} was removed. Does and litters on it are back on Standard.")
    return redirect(reverse("account") + "#schedule")


@login_required
@require_POST
def doe_schedule(request, pk):
    doe = get_object_or_404(Rabbit, owner=request.user, pk=pk, sex=Rabbit.Sex.DOE)
    choice = parse(request.user, request.POST.get("schedule"))
    if choice is False:
        messages.error(request, "Choose a schedule from the list.")
        return redirect(reverse("rabbit_detail", args=[doe.pk]) + "#schedule")
    doe.breeding_schedule = choice
    doe.save(update_fields=["breeding_schedule"])
    moved = 0
    if request.POST.get("recalculate"):
        moved = recalculate(open_litters(Litter.objects.filter(
            owner=request.user, pairing__doe=doe, pairing__breeding_schedule__isnull=True, pairing__standard_schedule=False)), choice)
    messages.success(request, f"{doe.name} is on {choice.name if choice else 'Standard'}." + moved_text(moved))
    return redirect(reverse("rabbit_detail", args=[doe.pk]) + "#schedule")


@login_required
@require_POST
def pairing_schedule(request, pk):
    pairing = get_object_or_404(Pairing.objects.select_related("doe"), owner=request.user, pk=pk)
    choice = parse(request.user, request.POST.get("schedule"), allow_follow=True)
    if choice is False:
        messages.error(request, "Choose a schedule from the list.")
        return redirect(reverse("pairing_detail", args=[pairing.pk]) + "#schedule")
    apply(pairing, choice)
    pairing.save(update_fields=["breeding_schedule", "standard_schedule"])
    moved = 0
    if request.POST.get("recalculate"):
        moved = recalculate(open_litters(pairing.litters.all()), pairing.resolved_schedule())
    label = f"{pairing.doe.name}'s schedule" if pairing.follows_doe else (pairing.resolved_schedule() or prefs(request.user)).name
    messages.success(request, f"{pairing} uses {label}." + moved_text(moved))
    return redirect(reverse("pairing_detail", args=[pairing.pk]) + "#schedule")


def apply(pairing, choice):
    pairing.breeding_schedule = choice if isinstance(choice, BreedingSchedule) else None
    pairing.standard_schedule = choice is None
