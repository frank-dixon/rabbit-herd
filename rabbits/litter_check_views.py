"""Litter page actions: whole-litter and each-kit checks, and converting
every kit into its own rabbit."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .sync import queueable
from . import litter_kits as K
from .litters import own_litter
from .models import LitterCheck, Rabbit, prefs
from .weigh_in import to_grams


def entry_unit(user):
    """Kits are weighed in ounces for lb keepers and grams for kg keepers."""
    return "oz" if prefs(user).weight_unit == "lb" else "g"


def clean_status(value):
    return value if value in LitterCheck.Status.values else ""


@login_required
@require_POST
@queueable("litter-check")
def litter_check(request, pk):
    litter = own_litter(request, pk)
    back = redirect(f"/litters/{litter.pk}/?check={request.POST.get('mode', 'whole')}#checks")
    if litter.converted_at:
        messages.error(request, "This litter was converted; log checks on each rabbit now.")
        return back
    if litter.kindled_on is None:
        messages.error(request, "Record the kindling first.")
        return back
    day = parse_date(request.POST.get("date") or "") or timezone.localdate()
    unit = entry_unit(request.user)
    note = " ".join(request.POST.get("note", "").split())[:300]
    if request.POST.get("mode") == "each":
        rows = []
        for slot in K.ensure_slots(litter):
            n = slot.number
            raw = request.POST.get(f"w_{n}", "").strip()
            grams = to_grams(raw, unit) if raw else None
            if raw and grams is None:
                messages.error(request, f"Check the weight for {slot.label}.")
                return back
            sex, color = request.POST.get(f"sex_{n}", slot.sex), " ".join(request.POST.get(f"color_{n}", slot.color).split())[:80]
            if not slot.rabbit_id and (sex != slot.sex or color != slot.color) and sex in ("", *Rabbit.Sex.values):
                slot.sex, slot.color = sex, color
                slot.save(update_fields=["sex", "color"])
            rows.append((slot, grams, clean_status(request.POST.get(f"s_{n}")), " ".join(request.POST.get(f"n_{n}", "").split())[:300]))
        check = K.record_each(litter, day, rows)
        if check is None:
            messages.success(request, "Kit details saved.")
            return back
        messages.success(request, f"Logged {check.kit_count} kit{'s' if check.kit_count != 1 else ''} for {day:%a, %b} {day.day}.")
        return back
    raw = request.POST.get("weight", "").strip()
    grams = to_grams(raw, unit) if raw else None
    if raw and grams is None:
        messages.error(request, "Check the weight.")
        return back
    try:
        count = int(request.POST.get("kit_count") or litter.survivors or 0) or None
    except ValueError:
        count = None
    kind = request.POST.get("weight_kind") if request.POST.get("weight_kind") in LitterCheck.WeightKind.values else "average"
    status = clean_status(request.POST.get("status"))
    if not (grams or status or note):
        messages.error(request, "Enter a weight, a health status or a note.")
        return back
    K.record_whole(litter, day, count, grams, kind, status, note)
    messages.success(request, f"Whole-litter check logged for {day:%a, %b} {day.day}.")
    return back


@login_required
def litter_convert(request, pk):
    """GET: the confirm page (used without JS). POST: convert, once."""
    litter = own_litter(request, pk)
    title = K.litter_title(litter)
    if request.method == "POST":
        try:
            kits = K.convert(litter.pk, request.user)
        except K.ConvertError as error:
            messages.error(request, str(error))
            return redirect(f"/litters/{litter.pk}/convert/")
        messages.success(request, f"{len(kits)} kits are now rabbits in your herd.")
        return redirect(f"/litters/{litter.pk}/#kits")
    if litter.converted_at:
        return redirect(f"/litters/{litter.pk}/#kits")
    slots = K.ensure_slots(litter)
    return render(request, "rabbits/litter_convert.html", {"litter": litter, "title": title, "todo": [s for s in slots if not s.rabbit_id],
                                                            "missing": [s for s in slots if not s.rabbit_id and not s.sex]})
