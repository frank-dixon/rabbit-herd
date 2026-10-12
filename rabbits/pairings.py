"""Pairings: a doe and a buck from the herd, with a warning when they share
ancestors. Ancestors come from relatives rows (dam, sire, grandparents),
pedigree entries, and the herd rabbits those point at, followed upward."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Pairing, PedigreeEntry, Rabbit, Relative

MAX_GENERATIONS = 4
PARENT_STEPS = {"dam": 1, "sire": 1, "granddam": 2, "grandsire": 2}
CHOOSE_DOE = "Please choose a doe from your herd."
CHOOSE_BUCK = "Please choose a buck from your herd."


def _key(herd_rabbit_id, outside_id):
    return ("herd", herd_rabbit_id) if herd_rabbit_id else ("outside", outside_id)


def ancestors(rabbit, limit=MAX_GENERATIONS):
    """{key: (name, generations back)} keeping the closest generation."""
    found = {}
    frontier = [(rabbit.pk, 0)]
    done = set()
    while frontier:
        pk, depth = frontier.pop(0)
        if pk in done:
            continue
        done.add(pk)
        rows = [(PARENT_STEPS[row.relationship], row.herd_rabbit, row.outside)
                for row in Relative.objects.filter(rabbit_id=pk, relationship__in=PARENT_STEPS)
                .select_related("herd_rabbit", "outside")]
        rows += [(len(entry.position), entry.herd_rabbit, entry.outside)
                 for entry in PedigreeEntry.objects.filter(rabbit_id=pk).select_related("herd_rabbit", "outside")]
        # A herd rabbit that lists this one as its offspring is a parent.
        rows += [(1, row.rabbit, None)
                 for row in Relative.objects.filter(herd_rabbit_id=pk, relationship="offspring").select_related("rabbit")]
        for steps, herd, outside in rows:
            gen = depth + steps
            other = herd or outside
            if other is None or gen > limit or (herd is not None and herd.pk == rabbit.pk):
                continue
            key = _key(herd.pk if herd else None, outside.pk if outside else None)
            if key not in found or found[key][1] > gen:
                found[key] = (other.name, gen)
            if herd is not None and gen < limit:
                frontier.append((herd.pk, gen))
    return found


def generation_word(gen):
    return {1: "parent", 2: "grandparent", 3: "great-grandparent"}.get(gen, f"{gen - 2}× great-grandparent")


def inbreeding_warnings(doe, buck):
    """Plain sentences, closest relationship first; empty when none is known."""
    doe_up, buck_up = ancestors(doe), ancestors(buck)
    warnings = []
    for child, parent, child_up in ((doe, buck, doe_up), (buck, doe, buck_up)):
        hit = child_up.get(("herd", parent.pk))
        if hit:
            warnings.append(f"{parent.name} is {child.name}'s {generation_word(hit[1])}.")
    siblings = Relative.objects.filter(
        rabbit__in=[doe, buck], herd_rabbit__in=[doe, buck], relationship__in=["sibling", "half_sibling"]
    ).first()
    if siblings:
        warnings.append(f"{doe.name} and {buck.name} are recorded as {siblings.get_relationship_display().split(' (')[0].lower()}s.")
    shared = sorted(set(doe_up) & set(buck_up), key=lambda key: (doe_up[key][1] + buck_up[key][1], doe_up[key][0]))
    for key in shared:
        name, d_gen = doe_up[key]
        b_gen = buck_up[key][1]
        warnings.append(
            f"Shared ancestor {name}: {doe.name}'s {generation_word(d_gen)} and {buck.name}'s {generation_word(b_gen)}."
        )
    return warnings


def herd_choices(user, sex):
    rabbits = Rabbit.objects.filter(owner=user, sex=sex, archived_at__isnull=True).exclude(status=Rabbit.Status.DECEASED)
    return [(str(r.pk), f"{r.name}{f' · {r.tattoo}' if r.tattoo else ''} · {r.short_breed}") for r in rabbits]


def pick(user, raw, sex):
    raw = (raw or "").strip()
    if not raw.isdigit():
        return None
    return Rabbit.objects.filter(owner=user, sex=sex, archived_at__isnull=True, pk=int(raw)).exclude(
        status=Rabbit.Status.DECEASED).first()


@login_required
def pairing_list(request):
    errors = {}
    values = {"doe": request.GET.get("doe", ""), "buck": request.GET.get("buck", ""), "notes": ""}
    check = None
    if request.method == "POST":
        values = {key: request.POST.get(key, "") for key in values}
        doe = pick(request.user, values["doe"], Rabbit.Sex.DOE)
        buck = pick(request.user, values["buck"], Rabbit.Sex.BUCK)
        if doe is None:
            errors["doe"] = [CHOOSE_DOE]
        if buck is None:
            errors["buck"] = [CHOOSE_BUCK]
        if not errors and request.POST.get("action") == "save":
            pairing = Pairing.objects.create(owner=request.user, doe=doe, buck=buck,
                                             notes=" ".join(values["notes"].split())[:200])
            messages.success(request, f"{pairing} was saved.")
            return redirect("pairing_detail", pairing.pk)
        if not errors:
            check = {"doe": doe, "buck": buck, "warnings": inbreeding_warnings(doe, buck)}
    elif values["doe"] and values["buck"]:
        doe = pick(request.user, values["doe"], Rabbit.Sex.DOE)
        buck = pick(request.user, values["buck"], Rabbit.Sex.BUCK)
        if doe and buck:
            check = {"doe": doe, "buck": buck, "warnings": inbreeding_warnings(doe, buck)}
    pairings = Pairing.objects.filter(owner=request.user).select_related("doe", "buck")
    return render(request, "rabbits/pairings.html", {
        "pairings": pairings, "errors": errors, "values": values, "check": check, "wide": True,
        "doe_options": herd_choices(request.user, Rabbit.Sex.DOE),
        "buck_options": herd_choices(request.user, Rabbit.Sex.BUCK),
    })


@login_required
def pairing_detail(request, pk):
    pairing = get_object_or_404(Pairing.objects.select_related("doe", "buck"), owner=request.user, pk=pk)
    context = {"pairing": pairing, "warnings": inbreeding_warnings(pairing.doe, pairing.buck), "wide": True}
    return render(request, "rabbits/pairing_detail.html", context)


@login_required
@require_POST
def pairing_delete(request, pk):
    pairing = get_object_or_404(Pairing, owner=request.user, pk=pk)
    name = str(pairing)
    pairing.delete()
    messages.success(request, f"The pairing {name} was removed.")
    return redirect("pairing_list")
