"""Litter kits as a group: numbered kit slots, whole-litter and each-kit
checks (weight, health status, note), and the one-way conversion of every
kit into its own rabbit record.

Checks on a kit that is already a rabbit are copied onto that rabbit at once
(a Weight and a HealthNote), so its own page shows them; checks on kits that
are still only numbers are copied when the litter is converted."""

from django.db import transaction
from django.utils import timezone

from .models import (BreedShare, HealthNote, HistoryEntry, KitCheck, Litter, LitterCheck, LitterKit, Rabbit,
                     Relative, Weight, prefs)


class ConvertError(Exception):
    pass


def litter_title(litter):
    return f"{litter.pairing.doe.name} × {litter.pairing.buck.name}"


def same_text(a, b):
    return " ".join((a or "").split()).casefold() == " ".join((b or "").split()).casefold()


def ensure_slots(litter):
    """One slot per surviving kit, the litter's herd kits linked first."""
    slots = list(litter.slots.select_related("rabbit"))
    linked = {s.rabbit_id for s in slots if s.rabbit_id}
    number = max((s.number for s in slots), default=0)
    for kit in litter.kits.order_by("pk"):
        if kit.pk in linked:
            continue
        free = next((s for s in slots if s.rabbit_id is None), None)
        if free:
            free.rabbit, free.sex, free.color = kit, kit.sex, kit.color
            free.save(update_fields=["rabbit", "sex", "color"])
        else:
            number += 1
            slots.append(LitterKit.objects.create(litter=litter, number=number, rabbit=kit, sex=kit.sex, color=kit.color))
    while len(slots) < (litter.survivors or 0):
        number += 1
        slots.append(LitterKit.objects.create(litter=litter, number=number))
    return sorted(slots, key=lambda s: s.number)


def status_text(status, note):
    words = [dict(LitterCheck.Status.choices).get(status, "")] if status else []
    if note:
        words.append(note)
    return ". ".join(words)


def copy_whole(check, rabbit, unit):
    avg = check.average_grams
    if avg:
        Weight.objects.create(rabbit=rabbit, date=check.date, grams=avg, unit=unit,
                              note=f"Litter average ({check.kit_count} kits)" if check.kit_count else "Litter average")
    text = status_text(check.status, check.note)
    if text:
        HealthNote.objects.create(rabbit=rabbit, date=check.date, kind=HealthNote.Kind.CHECKUP,
                                  notes=f"Whole-litter check: {text}")


def copy_row(row, rabbit, unit):
    if row.grams:
        Weight.objects.create(rabbit=rabbit, date=row.litter_check.date, grams=row.grams, unit=unit, note="Litter check")
    text = status_text(row.status, row.note)
    if text:
        HealthNote.objects.create(rabbit=rabbit, date=row.litter_check.date,
                                  kind=HealthNote.Kind.ILLNESS if row.status == LitterCheck.Status.SICK else HealthNote.Kind.CHECKUP,
                                  notes=f"Litter check: {text}")


@transaction.atomic
def record_whole(litter, date, kit_count, grams, weight_kind, status, note):
    check = LitterCheck.objects.create(litter=litter, date=date, mode=LitterCheck.Mode.WHOLE, kit_count=kit_count,
                                       grams=grams, weight_kind=weight_kind, status=status, note=note)
    unit = prefs(litter.owner).weight_unit
    for slot in ensure_slots(litter):
        if slot.rabbit_id:
            copy_whole(check, slot.rabbit, unit)
    return check


@transaction.atomic
def record_each(litter, date, rows):
    """rows: [(slot, grams or None, status, note)]; empty rows are skipped."""
    rows = [r for r in rows if r[1] or r[2] or r[3]]
    if not rows:
        return None
    check = LitterCheck.objects.create(litter=litter, date=date, mode=LitterCheck.Mode.EACH, kit_count=len(rows))
    unit = prefs(litter.owner).weight_unit
    for slot, grams, status, note in rows:
        row = KitCheck.objects.create(litter_check=check, kit=slot, grams=grams, status=status, note=note)
        if slot.rabbit_id:
            copy_row(row, slot.rabbit, unit)
    return check


def convert(litter_id, user, typed):
    """Make every kit that is still only a number its own rabbit, once.
    Returns the litter's kit rabbits. Raises ConvertError when the typed
    name doesn't match or a kit has no sex; a second submit is a no-op."""
    from .litters import kit_breed
    from .tattoo import suggest

    with transaction.atomic():
        litter = Litter.objects.select_for_update().select_related("pairing__doe", "pairing__buck").get(pk=litter_id, owner=user)
        if litter.converted_at:
            return list(litter.kits.all())
        if not same_text(typed, litter_title(litter)):
            raise ConvertError(f"Type {litter_title(litter)} to confirm.")
        if litter.kindled_on is None:
            raise ConvertError("Record the kindling first.")
        slots = ensure_slots(litter)
        todo = [s for s in slots if s.rabbit_id is None]
        missing = [s.label for s in todo if s.sex not in Rabbit.Sex.values]
        if missing:
            raise ConvertError(f"Set the sex of {', '.join(missing)} first.")
        doe, buck = litter.pairing.doe, litter.pairing.buck
        fields, shares = kit_breed(doe, buck)
        unit = prefs(user).weight_unit
        title = litter_title(litter)
        whole = list(litter.checks.filter(mode=LitterCheck.Mode.WHOLE).order_by("date", "pk"))
        for slot in todo:
            tattoo = suggest(user) if prefs(user).tattoo_prefill else ""
            kit = Rabbit.objects.create(
                owner=user, name=f"{doe.name} kit {slot.number}", sex=slot.sex, tattoo=tattoo, birth_date=litter.kindled_on,
                status=Rabbit.Status.GROWING, color=slot.color or "Not recorded yet", litter=litter, **fields)
            BreedShare.objects.bulk_create(BreedShare(rabbit=kit, breed=breed, percent=pct) for breed, pct in shares)
            Relative.objects.create(rabbit=kit, relationship="dam", herd_rabbit=doe)
            Relative.objects.create(rabbit=kit, relationship="sire", herd_rabbit=buck)
            for check in whole:
                copy_whole(check, kit, unit)
            for row in slot.checks.select_related("litter_check").order_by("litter_check__date", "pk"):
                copy_row(row, kit, unit)
            slot.rabbit = kit
            slot.save(update_fields=["rabbit"])
            HistoryEntry.objects.create(rabbit=kit, action=HistoryEntry.Action.ADDED, subject="litter",
                                        summary=f"Made its own rabbit from litter {title} (kit {slot.number})")
        litter.converted_at = timezone.now()
        litter.save(update_fields=["converted_at"])
        return list(litter.kits.all())
