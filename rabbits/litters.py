"""Litters, started from a pairing. The breed date sets the palpate,
nest box and due dates (days from Settings); kindling records kits born alive and
dead, losses later on, and survivors can be added to the herd as rabbits."""

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_time
from django.views.decorators.http import require_http_methods, require_POST

from .sync import queueable
from .status_pills import tone
from . import costs, flow
from .models import Breed, BreedShare, Cover, Litter, LitterCheck, Pairing, Rabbit, Relative, prefs, weight_text

DATE_REQUIRED = "Enter the date, like {example}."
DATE_FUTURE = "That date is in the future."
COUNT_INVALID = "Enter a whole number of kits, 0 or more."
KIT_NAME_REQUIRED = "Give the kit a name."
KIT_SEX_REQUIRED = "Choose doe or buck for the kit."
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
    litter = Litter.objects.create(owner=request.user, pairing=pairing, bred_on=bred_on,
                                   breeding_schedule=pairing.resolved_schedule())
    Cover.objects.create(litter=litter, date=bred_on, outcome=Cover.Outcome.COVERED)
    messages.success(request, f"Litter started. Due {litter.due_on:%B} {litter.due_on.day}, {litter.due_on.year}.")
    return redirect("litter_detail", litter.pk)


def litter_card(litter, today):
    """What a litter card shows: the stage pill, key dates, kit counts with the
    sex split when known, the next step and a strip of kit photos."""
    doe, buck = litter.pairing.doe, litter.pairing.buck
    kits = list(litter.kits.all())
    task = litter.next_task()
    if task and task.get("key") == "due":
        task = {**task, "label": "Kindling"}
    card = {"litter": litter, "doe": doe, "buck": buck, "title": f"{doe.name} × {buck.name}", "task": task,
            "task_days": (task["date"] - today).days if task else None,
            "photos": [m for m in (k.main_photo for k in kits) if m][:4]}
    card["cover"] = card["photos"][0] if card["photos"] else doe.main_photo  # grid card photo: a kit, else the doe
    if litter.kindled_on is None:
        days = (litter.due_on - today).days
        card.update(stage="expecting", pill=("Overdue" if days < 0 else "Due today" if days == 0 else "Expecting"),
                    due_days=days)
        card["tone"] = tone(card["pill"])
    else:
        age = (today - litter.kindled_on).days
        weaned = litter.converted_at or not task
        card.update(stage="kindled", age=age, pill=("Converted" if litter.converted_at else "Weaned" if weaned and age >= 28 else "Nursing"),
                    alive=litter.survivors, total=(litter.born_alive or 0) + (litter.born_dead or 0),
                    does=sum(k.sex == "doe" for k in kits), bucks=sum(k.sex == "buck" for k in kits),
                    recorded=len(kits))  # kits on record: the count to show when kindling numbers were never entered
        card["tone"] = tone(card["pill"]) or "o"
    return card


@login_required
def litter_list(request):
    from .index_items import index_view, view_options

    view = index_view(request, "litters", "grid")
    today = timezone.localdate()
    litters = list(Litter.objects.filter(owner=request.user).for_view(request.user)
                   .select_related("pairing__doe", "pairing__buck", "breeding_schedule")
                   .prefetch_related("pairing__doe__photos", "pairing__buck__photos", "kits__photos", "kits__weights"))
    doe = request.GET.get("doe", "")
    if request.GET.get("archived") == "1":
        # Archived (converted) litters are past litters: the old link lands on the Past table.
        from django.shortcuts import redirect
        return redirect(reverse("litter_list") + (f"?doe={doe}" if doe.isdigit() else "") + "#past")
    archived = False
    litters = [l for l in litters if not doe.isdigit() or l.pairing.doe_id == int(doe)]
    from . import litter_outcomes as O

    unit = prefs(request.user).weight_unit
    past, current = [], []
    if not archived:
        for litter in litters:
            kits = list(litter.kits.all())
            # Converted litters are always past; others once every kit has an outcome or after 120 days.
            (past if litter.converted_at or O.is_past(litter, kits, today) else current).append((litter, kits))
        litters = [l for l, _ in current]
    from . import sorting
    past_cols = [("kindled", "Pair · kindled"), ("born", "Born / raised"), ("growout", "Avg. grow-out")]
    psort, pdesc = sorting.parse(request.GET.get("sort", ""), dict(past_cols), default="-kindled")
    past_rows = sorting.apply([O.past_row(l, k, unit) for l, k in past], {
        "kindled": lambda r: r["litter"].kindled_on, "born": lambda r: (r["born"], r["raised"]),
        "growout": lambda r: r["growout_g"]}, psort, pdesc)
    keep = {k: v for k, v in request.GET.items() if k in ("view", "doe") and v}
    past_headers = {h["key"]: h for h in sorting.headers(past_cols, psort, pdesc, keep, {"kindled", "born", "growout"})}
    cards = [litter_card(litter, today) for litter in litters]
    expecting = sorted((c for c in cards if c["stage"] == "expecting"), key=lambda c: c["litter"].due_on)
    kindled = sorted((c for c in cards if c["stage"] == "kindled"), key=lambda c: c["litter"].kindled_on, reverse=True)
    from rabbits.samples.context import sample_ctx
    return render(request, "rabbits/litters.html", {
        "open": expecting, "kindled": kindled, "today": today, "past": past_rows, "past_headers": past_headers, "past_after": O.PAST_AFTER_DAYS, "wide": True, "view": view, "archived": archived,
        "archived_count": Litter.objects.filter(owner=request.user, converted_at__isnull=False).real().count(),
        "view_options": view_options(request, view),
        **sample_ctx(request.user, "litters"),
    })


@login_required
def litter_detail(request, pk):
    litter = own_litter(request, pk)
    kits = list(litter.kits.prefetch_related("cull_notes", "photos", "weights"))
    unit = prefs(request.user).weight_unit
    for kit in kits:
        kit.latest_cull = next(iter(kit.cull_notes.all()), None)
        latest = max(kit.weights.all(), key=lambda w: (w.date, w.pk), default=None)
        kit.latest_weight_text = weight_text(latest.grams, unit) if latest else ""
        kit.latest_weight_on = latest.date if latest else None
    room = (litter.survivors or 0) - len(kits)
    covers = list(litter.covers.all())
    from . import litter_kits as K
    from .litter_check_views import entry_unit

    slots = K.ensure_slots(litter) if litter.kindled_on else []
    checks = list(litter.checks.prefetch_related("rows__kit__rabbit"))
    for slot in slots:
        slot.last = next((row for c in checks for row in c.rows.all() if row.kit_id == slot.pk), None)
        slot.last_whole = next((c for c in checks if c.mode == "whole"), None)
        mine = [(row.litter_check.date, row.grams) for c in checks for row in c.rows.all() if row.kit_id == slot.pk and row.grams]
        if slot.last_whole and slot.last_whole.average_grams:
            mine.append((slot.last_whole.date, slot.last_whole.average_grams))
        slot.weight_text = weight_text(max(mine)[1], unit) if mine else ""
        slot.grams = max(mine)[1] if mine else None
    for c in checks:
        c.weight_label = weight_text(c.grams, unit) if c.grams else ""
        for row in c.rows.all():
            row.weight_label = weight_text(row.grams, unit) if row.grams else ""
    card = litter_main_card(litter, slots, kits, unit)
    from . import litter_outcomes as O

    outcome_kits = list(litter.kits.select_related("sold_to").prefetch_related("weights", "photos"))
    outcome = O.outcome(litter, outcome_kits, unit, timezone.localdate())
    past = O.is_past(litter, outcome_kits, timezone.localdate())
    all_tasks = litter.tasks()
    return render(request, "rabbits/litter_detail.html", {
        "delete_title": f"Delete the {litter.pairing.doe.name} × {litter.pairing.buck.name} litter?", "delete_text": LITTER_DELETE_TEXT,
        "litter": litter, "tasks": [t for t in all_tasks if not t["done"]], "done_tasks": [t for t in all_tasks if t["done"]], "kits": kits, "outcome": outcome, "is_past": past,
        "done_on": O.done_on(litter, outcome_kits) if past else None,
        "timeline": O.timeline(litter, outcome_kits) if litter.kindled_on else [], "room": room, "card": card,
        "today": timezone.localdate(), "wide": True,
        "subtitle": f"Litter bred {litter.bred_on:%b} {litter.bred_on.day}, {litter.bred_on.year} · due {litter.due_on:%b} {litter.due_on.day}",
        "sex_options": Rabbit.Sex.choices,
        "slots": slots, "checks": checks, "check_mode": "each" if request.GET.get("check") == "each" else "whole",
        "entry_unit": entry_unit(request.user), "litter_title": K.litter_title(litter),
        "status_choices": LitterCheck.Status.choices, "weight_kinds": LitterCheck.WeightKind.choices,
        "check_options": [{"href": f"?check={k}#checks", "label": l, "selected": k == ("each" if request.GET.get("check") == "each" else "whole")}
                          for k, l in LitterCheck.Mode.choices],
        "unconverted": [s for s in slots if not s.rabbit_id],
        "missing_sex": [s for s in slots if not s.rabbit_id and s.sex not in Rabbit.Sex.values],
        "covers": covers, "cover_outcomes": Cover.Outcome.choices,
        "counted_cover": next((c.pk for c in covers if c.outcome == Cover.Outcome.COVERED), None),
        **dict(zip(("cost_items", "cost_total"), costs.linked(litter.expenses.all()))),
        "cost_add_url": f"/costs/new/?litter={litter.pk}",
    })


def litter_main_card(litter, slots, kits, unit):
    """The litter card: the litter photo (or a stock placeholder), key numbers
    and one tile per kit. Kits show their own photo, else the litter's."""
    from .litter_photos import kit_photo_url, litter_photo_url, placeholder_url, rabbit_photo_url

    own = litter_photo_url(litter)
    litter_img = own or placeholder_url(litter)
    by_pk = {k.pk: k for k in kits}

    def tile_for_rabbit(kit, slot=None):
        main = kit.main_photo
        img = rabbit_photo_url(main) if main else (kit_photo_url(slot) if slot and slot.photo else litter_img)
        weight = f"{kit.latest_weight_text}" if kit.latest_weight_text else "Not weighed"
        cull = kit.latest_cull
        return {"name": kit.name, "line1": f"{kit.get_sex_display()} · {kit.color or 'Color not set'}",
                "line2": kit.tattoo or ("Junior · " + kit.get_status_display().lower() if litter.converted_at else weight),
                "img": img, "placeholder": not main and not (slot and slot.photo) and not own,
                "href": reverse("rabbit_detail", args=[kit.pk]),
                "pill": cull.get_decision_display() if cull else "", "decision": cull.decision if cull else "", "reason": (cull.reason or "")[:140] if cull else "", "tone": {"keep": "g", "cull": "r", "sell": "y", "undecided": ""}.get(cull.decision, "") if cull else "",
                "upload": reverse("kit_photo", args=[litter.pk, slot.number]) if slot and not litter.converted_at else ""}

    tiles, seen = [], set()
    for slot in slots:
        if slot.rabbit_id and slot.rabbit_id in by_pk:
            tiles.append(tile_for_rabbit(by_pk[slot.rabbit_id], slot))
            seen.add(slot.rabbit_id)
        elif not slot.rabbit_id and not litter.converted_at:
            tiles.append({"name": slot.label, "line1": " · ".join(x for x in (slot.get_sex_display() or "Sex unknown", slot.color) if x),
                          "line2": slot.weight_text or "Not weighed", "img": kit_photo_url(slot) or litter_img,
                          "placeholder": not slot.photo and not own, "href": "", "pill": "", "tone": "",
                          "upload": reverse("kit_photo", args=[litter.pk, slot.number])})
    tiles += [tile_for_rabbit(k) for k in kits if k.pk not in seen]
    for t in tiles:
        t["inherits"] = t["img"] == litter_img
    weighed = [s.grams for s in slots if getattr(s, "grams", None)]
    task = litter.next_task()
    return {"img": litter_img, "own": bool(own), "tiles": tiles, "any_pill": any(t["pill"] for t in tiles),
            "avg": weight_text(round(sum(weighed) / len(weighed)), unit) if weighed else "",
            "next": task, "next_overdue": bool(task and task["date"] < timezone.localdate())}


@login_required
@require_POST
@queueable("litter-task")
def litter_task(request, pk):
    litter = own_litter(request, pk)
    if litter.converted_at:
        messages.error(request, "This litter was converted and is read-only.")
        return redirect("litter_detail", litter.pk)
    task = request.POST.get("task")
    done = request.POST.get("done") == "1"
    if task == "palpate":
        litter.palpated = done
    elif task == "nest_box":
        litter.nest_box_in = done
    elif task == "rebreed":
        litter.rebred = done
    elif task == "wean":
        litter.weaned = done
    elif task == "process":
        litter.processed = done
    litter.save(update_fields=["palpated", "nest_box_in", "rebred", "weaned", "processed"])
    if request.POST.get("next") in ("/", "/tasks/"):
        return redirect(request.POST["next"])
    return redirect(f"/litters/{litter.pk}/#dates")


@login_required
@require_POST
@queueable("kindling")
def litter_kindle(request, pk):
    litter = own_litter(request, pk)
    if litter.converted_at:
        messages.error(request, "This litter was converted and is read-only.")
        return redirect("litter_detail", litter.pk)
    kindled_on = parse_date(request.POST.get("kindled_on"))
    alive = parse_count(request.POST.get("born_alive"))
    dead = parse_count(request.POST.get("born_dead"), 0)
    lost = parse_count(request.POST.get("died_after"), 0)
    if kindled_on is None or kindled_on < litter.bred_on:
        messages.error(request, "Enter the kindling date. It can't be before the breed date.")
    elif kindled_on > timezone.localdate():
        messages.error(request, DATE_FUTURE)
    elif alive is None or -1 in (alive, dead, lost):
        messages.error(request, COUNT_INVALID)
    elif lost > alive:
        messages.error(request, f"{lost} lost is more than the {alive} born alive. Check the numbers.")
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
    if litter.converted_at:
        messages.error(request, "This litter was converted and is read-only.")
        return redirect("litter_detail", litter.pk)
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


LITTER_DELETE_TEXT = "The litter, its dates, covers and checks are removed. Kits already in your herd stay."


@login_required
@require_http_methods(["GET", "POST"])
def litter_delete(request, pk):
    litter = own_litter(request, pk)
    if litter.converted_at:
        messages.error(request, "This litter was converted and is read-only.")
        return redirect("litter_detail", litter.pk)
    if request.method != "POST":
        from .confirm import confirm_delete
        return confirm_delete(request, f"Delete the {litter.pairing.doe.name} × {litter.pairing.buck.name} litter?",
                              LITTER_DELETE_TEXT, reverse("litter_detail", args=[litter.pk]))
    pairing = litter.pairing
    litter.delete()
    messages.success(request, "The litter was removed. Kits already in your herd stay there.")
    return redirect("pairing_detail", pairing.pk)


def sync_bred_on(litter):
    """The bred date is the first cover that took. With none, it stays put."""
    first = litter.covers.filter(outcome=Cover.Outcome.COVERED).order_by("date", "time", "pk").first()
    if first and first.date != litter.bred_on:
        litter.bred_on = first.date
        litter.save(update_fields=["bred_on"])
        return True
    return False


@login_required
@require_POST
def cover_add(request, pk):
    litter = own_litter(request, pk)
    back = reverse("litter_detail", args=[litter.pk]) + "#covers"
    day = parse_date(request.POST.get("date") or "")
    today = timezone.localdate()
    outcome = request.POST.get("outcome") or Cover.Outcome.COVERED
    errors = []
    if day is None:
        errors.append("A cover needs a date.")
    elif day > today:
        errors.append(DATE_FUTURE)
    elif litter.kindled_on and day > litter.kindled_on:
        errors.append("A cover can't be after the litter was kindled.")
    if outcome not in Cover.Outcome.values:
        errors.append("Choose how the cover went.")
    raw_time = (request.POST.get("time") or "").strip()
    try:
        time = parse_time(raw_time) if raw_time else None
    except ValueError:
        time = None
    if raw_time and time is None:
        errors.append("Enter the time like 7:30 AM, or leave it blank.")
    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect(back)
    Cover.objects.create(litter=litter, date=day, time=time, outcome=outcome,
                         note=" ".join((request.POST.get("note") or "").split())[:200])
    moved = sync_bred_on(litter)
    text = "Cover added."
    if moved:
        text += f" Bred date is now {litter.bred_on:%B} {litter.bred_on.day}; due {litter.due_on:%B} {litter.due_on.day}."
    messages.success(request, text)
    return redirect(back)


@login_required
@require_POST
def cover_delete(request, pk, cover_pk):
    litter = own_litter(request, pk)
    cover = get_object_or_404(Cover, litter=litter, pk=cover_pk)
    cover.delete()
    sync_bred_on(litter)
    messages.success(request, "Cover removed.")
    return redirect(reverse("litter_detail", args=[litter.pk]) + "#covers")


@login_required
@require_POST
@queueable("litter-note")
def litter_note_add(request, pk):
    """A dated note on the litter's Notes timeline."""
    from .models import LitterNote

    litter = own_litter(request, pk)
    text = request.POST.get("text", "").strip()[:500]
    day = parse_date(request.POST.get("date", "")) or timezone.localdate()
    if text:
        LitterNote.objects.create(litter=litter, date=min(day, timezone.localdate()), text=text)
        messages.success(request, "Note added.")
    else:
        messages.error(request, "Write a note first.", extra_tags="toast")
    return redirect(f"/litters/{litter.pk}/#notes")
