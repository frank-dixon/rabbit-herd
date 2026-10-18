"""Pairings: a doe and a buck from the herd, with a warning when they share
ancestors. Ancestors come from relatives rows (dam, sire, grandparents),
pedigree entries, and the herd rabbits those point at, followed upward."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from . import color_odds, genetics, schedules
from .models import Pairing, PedigreeEntry, Rabbit, Relative, prefs

MAX_GENERATIONS = 4
PARENT_STEPS = {"dam": 1, "sire": 1, "granddam": 2, "grandsire": 2}
CHOOSE_DOE = "Choose a doe from your herd."
CHOOSE_BUCK = "Choose a buck from your herd."


def _key(herd_rabbit_id, outside_id):
    return ("herd", herd_rabbit_id) if herd_rabbit_id else ("outside", outside_id)


class AncestorIndex:
    """Every parent link of one keeper's herd, loaded in four queries, so
    ancestor walks and sibling checks for many pairings cost nothing more."""

    def __init__(self, owner_id):
        self.up = {}  # rabbit_id -> [(generations, herd rabbit or None, outside or None)]
        for row in (Relative.objects.filter(rabbit__owner_id=owner_id, relationship__in=PARENT_STEPS)
                    .select_related("herd_rabbit", "outside").order_by("rabbit_id", "relationship", "pk")):
            self.up.setdefault(row.rabbit_id, []).append((PARENT_STEPS[row.relationship], row.herd_rabbit, row.outside))
        for entry in (PedigreeEntry.objects.filter(rabbit__owner_id=owner_id)
                      .select_related("herd_rabbit", "outside").order_by("rabbit_id", "position", "pk")):
            self.up.setdefault(entry.rabbit_id, []).append((len(entry.position), entry.herd_rabbit, entry.outside))
        # A herd rabbit that lists this one as its offspring is a parent.
        for row in (Relative.objects.filter(herd_rabbit__owner_id=owner_id, relationship="offspring")
                    .select_related("rabbit").order_by("relationship", "pk")):
            self.up.setdefault(row.herd_rabbit_id, []).append((1, row.rabbit, None))
        self.siblings = {}
        for row in (Relative.objects.filter(rabbit__owner_id=owner_id, herd_rabbit__isnull=False,
                                            relationship__in=["sibling", "half_sibling"]).order_by("relationship", "pk")):
            self.siblings.setdefault(frozenset((row.rabbit_id, row.herd_rabbit_id)), row)

    def sibling_row(self, a, b):
        return self.siblings.get(frozenset((a.pk, b.pk)))


def ancestor_index(owner_id):
    from . import derived

    return derived.memo(("ancestor_index", owner_id), lambda: AncestorIndex(owner_id))


def ancestors(rabbit, limit=MAX_GENERATIONS, index=None):
    """{key: (name, generations back)} keeping the closest generation."""
    index = index or ancestor_index(rabbit.owner_id)
    found = {}
    frontier = [(rabbit.pk, 0)]
    done = set()
    while frontier:
        pk, depth = frontier.pop(0)
        if pk in done:
            continue
        done.add(pk)
        for steps, herd, outside in index.up.get(pk, ()):
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


def inbreeding_warnings(doe, buck, index=None):
    """Plain sentences, closest relationship first; empty when none is known."""
    index = index or ancestor_index(doe.owner_id)
    doe_up, buck_up = ancestors(doe, index=index), ancestors(buck, index=index)
    warnings = []
    for child, parent, child_up in ((doe, buck, doe_up), (buck, doe, buck_up)):
        hit = child_up.get(("herd", parent.pk))
        if hit:
            warnings.append(f"{parent.name} is {child.name}'s {generation_word(hit[1])}.")
    siblings = index.sibling_row(doe, buck)
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


def age_warnings(doe, buck):
    """Plain sentences for a doe or buck younger than the owner's breeding age."""
    from django.utils import timezone

    from .models import prefs_for

    months = prefs_for(doe.owner_id).breeding_age_months
    today = timezone.localdate()
    out = []
    for rabbit in (doe, buck):
        if rabbit.birth_date is None:
            continue
        age = (today.year - rabbit.birth_date.year) * 12 + today.month - rabbit.birth_date.month - (today.day < rabbit.birth_date.day)
        if age < months:
            out.append(f"{rabbit.name} is {age} month{'s' if age != 1 else ''} old; your breeding age is {months} months.")
    return out


def herd_choices(user, sex):
    rabbits = Rabbit.objects.filter(owner=user, sex=sex, archived_at__isnull=True).for_view(user).exclude(status=Rabbit.Status.DECEASED)
    return [(str(r.pk), f"{r.name}{f' · {r.tattoo}' if r.tattoo else ''} · {r.short_breed}") for r in rabbits]


def pick(user, raw, sex):
    raw = (raw or "").strip()
    if not raw.isdigit():
        return None
    return Rabbit.objects.filter(owner=user, sex=sex, archived_at__isnull=True, pk=int(raw)).exclude(
        status=Rabbit.Status.DECEASED).first()


def short_generation(gen):
    """Compact table label: Parent, Grandparent, Great-gp, 2× great-gp."""
    return {1: "Parent", 2: "Grandparent", 3: "Great-gp"}.get(gen, f"{gen - 2}× great-gp")


def relatedness(user, doe, buck, params=None, sort=""):
    """The New pairing summary: severity, the closest relationship, COI, and the shared-ancestor table."""
    from . import program_plan, sorting

    index = ancestor_index(doe.owner_id)
    doe_up, buck_up = ancestors(doe, index=index), ancestors(buck, index=index)
    closest = ""
    for child, parent, up in ((doe, buck, doe_up), (buck, doe, buck_up)):
        hit = up.get(("herd", parent.pk))
        if hit and not closest:
            word = ("sire" if parent.sex == Rabbit.Sex.BUCK else "dam") if hit[1] == 1 else generation_word(hit[1])
            closest = f"{parent.name} is {child.name}'s {word}"
    siblings = index.sibling_row(doe, buck)
    if siblings and not closest:
        closest = f"{doe.name} and {buck.name} are {siblings.get_relationship_display().split(' (')[0].lower()}s"
    shared = [k for k in set(doe_up) & set(buck_up)]
    rows = [{"name": doe_up[k][0], "doe": short_generation(doe_up[k][1]), "buck": short_generation(buck_up[k][1]),
             "sort": {"closest": (doe_up[k][1] + buck_up[k][1], doe_up[k][1]), "name": doe_up[k][0].lower(),
                      "doe": doe_up[k][1], "buck": buck_up[k][1]}} for k in shared]
    if shared and not closest:
        first = min(rows, key=lambda r: r["sort"]["closest"])
        closest = f"Both descend from {first['name']}"
    coi = float(program_plan.pedigree(user).coi(("h", buck.pk), ("h", doe.pk))) * 100
    columns = [("name", "Ancestor"), ("doe", "Doe side"), ("buck", "Buck side")]
    key, desc = sorting.parse(sort, [c[0] for c in columns]) if sort else ("closest", False)
    rows.sort(key=lambda r: r["sort"]["name"])
    rows.sort(key=lambda r: (r["sort"][key], r["sort"]["closest"]), reverse=desc)
    heads = sorting.headers(columns, key, desc, {k: v for k, v in (params or {}).items() if k != "asort"}, param="asort")
    related = bool(closest or rows)
    tone = "r" if coi >= 25 else "y" if related else ""
    return {"related": related, "tone": tone, "label": "Closely related" if tone == "r" else "Related" if related else "Not related",
            "closest": closest, "coi": f"{coi:.1f}".rstrip("0").rstrip("."), "count": len(rows), "rows": rows,
            "heads": heads, "sorted": bool(sort)}


def pair_check(user, doe, buck, params=None, sort=""):
    """What the New pairing form shows once both are chosen: relatedness, ages, and an existing same pair."""
    same = Pairing.objects.filter(owner=user, doe=doe, buck=buck).order_by("-pk").first()
    return {"doe": doe, "buck": buck, "warnings": inbreeding_warnings(doe, buck), "age": age_warnings(doe, buck), "duplicate": same,
            "rel": relatedness(user, doe, buck, params, sort)}


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
        if not errors and doe.is_sample != buck.is_sample:
            errors["doe"] = ["Sample rabbits can only be paired with other samples. Add your own rabbit to plan this pairing."]
        if not errors and request.POST.get("action") == "save":
            pairing = Pairing.objects.create(owner=request.user, doe=doe, buck=buck,
                                             notes=" ".join(values["notes"].split())[:200],
                                             is_sample=doe.is_sample)
            messages.success(request, f"{pairing} was saved.")
            return redirect("pairing_detail", pairing.pk)
        if not errors:
            check = pair_check(request.user, doe, buck, {"doe": values["doe"], "buck": values["buck"]}, request.GET.get("asort", ""))
    elif values["doe"] and values["buck"]:
        doe = pick(request.user, values["doe"], Rabbit.Sex.DOE)
        buck = pick(request.user, values["buck"], Rabbit.Sex.BUCK)
        if doe and buck:
            check = pair_check(request.user, doe, buck, {"doe": values["doe"], "buck": values["buck"]}, request.GET.get("asort", ""))
    from .index_items import index_view, sorted_items, stat, view_options

    pairings = list(Pairing.objects.filter(owner=request.user).for_view(request.user).select_related("doe", "buck")
                    .prefetch_related("doe__photos", "buck__photos", "doe__genes", "buck__genes", "litters"))
    view = index_view(request, "pairings", "grid")
    items = pairing_items(request.user, pairings)
    count = lambda label: sum(1 for it in items if it["pill"]["label"] == label)
    stats = [stat("Bred, due soon", count("Bred"), "waiting to kindle"), stat("Kits on ground", count("Kits on ground"), "not yet weaned or moved"),
             stat("High COI", sum(1 for it in items if it["coi"] >= 25), "25% or more", "r" if any(it["coi"] >= 25 for it in items) else "")]
    columns = [{"label": "Pair", "sort": "pair"}, {"label": "Inbreeding", "wide_only": True, "sort": "coi"}, {"label": "Predicted colors", "wide_only": True},
               {"label": "Last litter", "wide_only": True, "sort": "bred"}, {"label": "Status", "align": "r", "sort": "status"}]
    items = sorted_items(request, items, columns, desc_first=("coi", "bred"))
    from rabbits.samples.context import sample_ctx
    return render(request, "rabbits/pairings.html", {
        "pairings": pairings, "items": items, "view": view, "view_options": view_options(request, view), "stats": stats,
        "columns": columns, "errors": errors, "values": values, "check": check, "wide": True,
        "doe_options": herd_choices(request.user, Rabbit.Sex.DOE),
        "buck_options": herd_choices(request.user, Rabbit.Sex.BUCK),
        **sample_ctx(request.user, "pairings"),
    })


@login_required
def pairing_detail(request, pk):
    pairing = get_object_or_404(
        Pairing.objects.select_related("doe", "buck").prefetch_related("doe__genes", "buck__genes"),
        owner=request.user, pk=pk)
    from django.utils import timezone

    doe_pairs, buck_pairs = color_odds.recorded(pairing.doe), color_odds.recorded(pairing.buck)
    context = {"pairing": pairing, "delete_title": f"Delete {pairing}?", "delete_text": PAIRING_DELETE_TEXT, "rel": relatedness(request.user, pairing.doe, pairing.buck, {}, request.GET.get("asort", "")),
               "age_warnings": age_warnings(pairing.doe, pairing.buck), "wide": True,
               "litters": pairing.litters.all(), "today": timezone.localdate(),
               "odds": color_odds.predict(pairing.doe, pairing.buck),
               "hidden_notes": genetics.pairing_notes(pairing.doe.name, doe_pairs, pairing.buck.name, buck_pairs),
               "differing": color_odds.differing(doe_pairs, buck_pairs),
               "schedule": pairing.schedule,
               "litter_help": "Palpate on day {0.palpate_day}, nest box on day {0.nest_box_day}, due on day {0.gestation_days}. {1} schedule.".format(
                   pairing.schedule, pairing.schedule.name),
               "schedule_options": schedules.options(request.user, follow_label=f"{pairing.doe.name}'s schedule ({(pairing.doe.breeding_schedule or prefs(request.user)).name})"),
               "schedule_value": schedules.FOLLOW if pairing.follows_doe else schedules.value_for(pairing.breeding_schedule)}
    return render(request, "rabbits/pairing_detail.html", context)


PAIRING_DELETE_TEXT = "The pairing and its litters are removed. Both rabbits and any kits in your herd stay."


@login_required
@require_http_methods(["GET", "POST"])
def pairing_delete(request, pk):
    pairing = get_object_or_404(Pairing, owner=request.user, pk=pk)
    if request.method != "POST":
        from django.urls import reverse
        from .confirm import confirm_delete
        return confirm_delete(request, f"Delete {pairing}?", PAIRING_DELETE_TEXT, reverse("pairing_detail", args=[pairing.pk]))
    name = str(pairing)
    pairing.delete()
    messages.success(request, f"The pairing {name} was removed.")
    return redirect("pairing_list")


STATUS_ORDER = {"Bred": 0, "Kits on ground": 1, "Planned": 2, "Done": 3}


def pairing_items(user, pairings):
    """Pairings for the shared card/row: thumbs, COI and closest relation, predicted colors, last litter, status."""
    from django.urls import reverse
    from django.utils import timezone

    from . import program_plan
    from .status_pills import tone as status_tone
    from .swatches import swatch

    today = timezone.localdate()
    ped = program_plan.pedigree(user)
    index = ancestor_index(user.pk)
    items = []
    for p in pairings:
        coi = float(ped.coi(("h", p.buck_id), ("h", p.doe_id))) * 100
        warnings = inbreeding_warnings(p.doe, p.buck, index)
        odds = color_odds.predict(p.doe, p.buck)
        chips = [{"swatch": swatch(name), "label": name.replace(" (black points)", "").replace(" (blue points)", " blue"), "note": pct}
                 for name, pct in odds["colors"][:3]]
        litter = max(p.litters.all(), key=lambda l: l.bred_on, default=None)
        if litter is None:
            pill, when, result = {"label": "Planned", "tone": status_tone("planned")}, "Not bred yet", f"Saved {p.created_at:%b} {p.created_at.day}"
        elif not litter.kindled_on:
            days = (litter.due_on - today).days
            pill = {"label": "Bred", "tone": status_tone("bred")}
            when, result = f"Bred {litter.bred_on:%b} {litter.bred_on.day}", f"Due {litter.due_on:%b} {litter.due_on.day}" + (f" · {days} days" if days >= 0 else f" · {-days} days late")
        else:
            done = bool(litter.converted_at)
            pill = {"label": "Done" if done else "Kits on ground", "tone": "" if done else status_tone("nursing")}
            raised = litter.survivors if getattr(litter, "survivors", None) is not None else litter.born_alive
            when = f"{'Last litter' if done else 'Kindled'} {litter.kindled_on:%b} {litter.kindled_on.day}"
            result = f"{litter.born_alive or 0} born, {raised or 0} {'raised' if done else 'alive'}"
        tone = "r" if coi >= 25 else "y" if coi > 0 else ""
        coi_pill = {"label": f"COI {coi:.1f}%".replace(".0%", "%"), "tone": tone}
        relation = warnings[0] if warnings else "No shared ancestors on record"
        items.append({
            "href": reverse("pairing_detail", args=[p.pk]), "is_sample": p.is_sample, "title": f"{p.doe.name} × {p.buck.name}",
            "sub": f"{p.doe.color or 'Color not set'} × {p.buck.color or 'Color not set'}", "thumbs": [p.doe, p.buck],
            "pill": pill, "coi": coi, "chips_label": "Predicted colors", "chips": chips,
            "kv": [{"label": when, "value": result}, {"label": "Litters", "value": len(p.litters.all())}],
            "foot": {"pill": coi_pill, "text": relation},
            "mobile": f"{result} · COI {coi:.1f}%",
            "cells": [{"kind": "lead"}, {"kind": "pill", "wide_only": True, **coi_pill}, {"kind": "chips", "chips": chips, "wide_only": True},
                      {"kind": "text", "main": when, "sub": result, "wide_only": True}, {"kind": "pill", "align": "r", **pill}],
            "sort": {"pair": f"{p.doe.name} {p.buck.name}".lower(), "coi": coi, "bred": litter.bred_on if litter else None, "status": STATUS_ORDER[pill["label"]]},
            "order": (STATUS_ORDER[pill["label"]], -(litter.bred_on.toordinal() if litter else 0)),
        })
    items.sort(key=lambda it: it["order"])
    return items
