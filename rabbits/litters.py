"""Litters, started from a pairing. The breed date sets the day 12 palpate,
day 28 nest box and day 31 due dates; kindling records kits born alive and
dead, losses later on, and survivors can be added to the herd as rabbits."""

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import costs, flow
from .models import Breed, BreedShare, Litter, Pairing, Rabbit, Relative

DATE_REQUIRED = "Please enter the date, like {example}."
DATE_FUTURE = "That date is in the future. Please check it."
COUNT_INVALID = "Please enter a whole number of kits, 0 or more."
KIT_NAME_REQUIRED = "Please give the kit a name."
KIT_SEX_REQUIRED = "Please choose doe or buck for the kit."
NO_KITS_LEFT = "All {count} surviving kits are already in your herd."
TATTOO_TAKEN = "Another rabbit in your herd already has the ear tattoo {tattoo}."


def parse_date(raw):
    try:
        return datetime.date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def parse_count(raw, default=None):
    raw = (raw or "").strip()
    if raw == "":
        return default
    return int(raw) if raw.isdigit() and int(raw) <= 30 else -1


def own_litter(request, pk):
    return get_object_or_404(
        Litter.objects.select_related("pairing__doe", "pairing__buck"), owner=request.user, pk=pk
    )


@login_required
@require_POST
def litter_create(request, pk):
    pairing = get_object_or_404(Pairing, owner=request.user, pk=pk)
    bred_on = parse_date(request.POST.get("bred_on"))
    today = timezone.localdate()
    if bred_on is None:
        messages.error(request, DATE_REQUIRED.format(example=f"{today:%B} {today.day}, {today.year}"))
        return redirect(f"/pairings/{pairing.pk}/#litters")
    if bred_on > today:
        messages.error(request, DATE_FUTURE)
        return redirect(f"/pairings/{pairing.pk}/#litters")
    litter = Litter.objects.create(owner=request.user, pairing=pairing, bred_on=bred_on)
    messages.success(request, f"Litter started. Due {litter.due_on:%B} {litter.due_on.day}, {litter.due_on.year}.")
    return redirect("litter_detail", litter.pk)


@login_required
def litter_list(request):
    litters = list(Litter.objects.filter(owner=request.user).select_related("pairing__doe", "pairing__buck"))
    return render(request, "rabbits/litters.html", {
        "open": [litter for litter in litters if litter.kindled_on is None],
        "kindled": [litter for litter in litters if litter.kindled_on is not None],
        "today": timezone.localdate(), "wide": True,
    })


@login_required
def litter_detail(request, pk):
    litter = own_litter(request, pk)
    kits = list(litter.kits.prefetch_related("cull_notes"))
    for kit in kits:
        kit.latest_cull = next(iter(kit.cull_notes.all()), None)
    room = (litter.survivors or 0) - len(kits)
    return render(request, "rabbits/litter_detail.html", {
        "litter": litter, "tasks": litter.tasks(), "kits": kits, "room": room,
        "today": timezone.localdate(), "wide": True,
        "subtitle": f"Litter bred {litter.bred_on:%b} {litter.bred_on.day}, {litter.bred_on.year} · due {litter.due_on:%b} {litter.due_on.day}",
        "sex_options": Rabbit.Sex.choices,
        **dict(zip(("cost_items", "cost_total"), costs.linked(litter.expenses.all()))),
        "cost_add_url": f"/costs/?litter={litter.pk}#add",
    })


@login_required
@require_POST
def litter_task(request, pk):
    litter = own_litter(request, pk)
    task = request.POST.get("task")
    done = request.POST.get("done") == "1"
    if task == "palpate":
        litter.palpated = done
    elif task == "nest_box":
        litter.nest_box_in = done
    litter.save(update_fields=["palpated", "nest_box_in"])
    if request.POST.get("next") in ("/", "/tasks/"):
        return redirect(request.POST["next"])
    return redirect(f"/litters/{litter.pk}/#dates")


@login_required
@require_POST
def litter_kindle(request, pk):
    litter = own_litter(request, pk)
    kindled_on = parse_date(request.POST.get("kindled_on"))
    alive = parse_count(request.POST.get("born_alive"))
    dead = parse_count(request.POST.get("born_dead"), 0)
    lost = parse_count(request.POST.get("died_after"), 0)
    if kindled_on is None or kindled_on < litter.bred_on:
        messages.error(request, "Please enter the kindling date, on or after the breed date.")
    elif kindled_on > timezone.localdate():
        messages.error(request, DATE_FUTURE)
    elif alive is None or -1 in (alive, dead, lost):
        messages.error(request, COUNT_INVALID)
    elif lost > alive:
        messages.error(request, f"{lost} lost is more than the {alive} born alive. Please check the numbers.")
    elif alive - lost < litter.kits.count():
        messages.error(request, f"{litter.kits.count()} kits from this litter are already in your herd, so survivors can't be fewer.")
    else:
        litter.kindled_on, litter.born_alive, litter.born_dead, litter.died_after = kindled_on, alive, dead, lost
        litter.notes = " ".join(request.POST.get("notes", "").split())[:200]
        litter.save()
        messages.success(request, f"Saved: {alive} born alive, {dead} born dead, {litter.survivors} surviving.")
    return redirect(f"/litters/{litter.pk}/#kindling")


def kit_breed(doe, buck):
    """Breed fields for a kit from both parents, as the add flow fills them."""
    draft = {"breed_type": "", "purebred": "", "cross": []}
    line = flow.prefill_breed_from_parents(
        draft, [{"relationship": "dam", "target": doe}, {"relationship": "sire", "target": buck}]
    )
    if not line:
        return {"breed": doe.breed if doe.breed == buck.breed else "Cross", "breed_type": "", "purebred": None}, []
    if draft["breed_type"] == Rabbit.BreedType.PUREBRED:
        return {"breed": line, "breed_type": draft["breed_type"], "purebred": Breed.objects.get(pk=draft["purebred"])}, []
    shares = [(Breed.objects.get(pk=row["breed"]), flow.parse_share(row["percent"])) for row in draft["cross"]]
    return {"breed": flow.short_breed(line), "breed_type": draft["breed_type"], "purebred": None}, shares


@login_required
@require_POST
def litter_add_kit(request, pk):
    litter = own_litter(request, pk)
    back = redirect(f"/litters/{litter.pk}/#kits")
    if litter.kindled_on is None:
        messages.error(request, "Record the kindling first.")
        return back
    if litter.kits.count() >= (litter.survivors or 0):
        messages.error(request, NO_KITS_LEFT.format(count=litter.survivors or 0))
        return back
    name = " ".join(request.POST.get("name", "").split())[:120]
    sex = request.POST.get("sex", "")
    tattoo = " ".join(request.POST.get("tattoo", "").split())[:20]
    if not name:
        messages.error(request, KIT_NAME_REQUIRED)
        return back
    if sex not in Rabbit.Sex.values:
        messages.error(request, KIT_SEX_REQUIRED)
        return back
    doe, buck = litter.pairing.doe, litter.pairing.buck
    fields, shares = kit_breed(doe, buck)
    try:
        with transaction.atomic():
            kit = Rabbit.objects.create(
                owner=request.user, name=name, sex=sex, tattoo=tattoo, birth_date=litter.kindled_on,
                status=Rabbit.Status.GROWING, color=" ".join(request.POST.get("color", "").split())[:80] or "Not recorded yet",
                litter=litter, **fields,
            )
            BreedShare.objects.bulk_create(BreedShare(rabbit=kit, breed=breed, percent=pct) for breed, pct in shares)
            Relative.objects.create(rabbit=kit, relationship="dam", herd_rabbit=doe)
            Relative.objects.create(rabbit=kit, relationship="sire", herd_rabbit=buck)
    except IntegrityError:
        messages.error(request, TATTOO_TAKEN.format(tattoo=tattoo))
        return back
    messages.success(request, f"{kit.name} was added to your herd as a growing-out {kit.get_sex_display().lower()}.")
    return back


@login_required
@require_POST
def litter_delete(request, pk):
    litter = own_litter(request, pk)
    pairing = litter.pairing
    litter.delete()
    messages.success(request, "The litter was removed. Kits already in your herd stay there.")
    return redirect("pairing_detail", pairing.pk)
