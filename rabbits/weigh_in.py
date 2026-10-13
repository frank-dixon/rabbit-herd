"""Quick weigh-in: step through a litter kit by kit, one big number entry per
kit, saving each as it goes. Grams or ounces, since kits are small."""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .litters import own_litter
from .models import GRAMS_PER_OUNCE, Weight

UNITS = {"g": "grams", "oz": "ounces"}


def live_kits(litter):
    return [k for k in litter.kits.order_by("name", "pk") if not k.archived_at and k.status != "deceased"]


def to_grams(raw, unit):
    try:
        value = Decimal((raw or "").strip().replace(",", "."))
    except InvalidOperation:
        return None
    if value <= 0 or value > 20000:
        return None
    grams = value * GRAMS_PER_OUNCE if unit == "oz" else value
    return int(grams.quantize(Decimal("1")))


@login_required
def weigh_in(request, pk):
    litter = own_litter(request, pk)
    kits = live_kits(litter)
    if not kits:
        messages.error(request, "Add the kits to this litter first, then weigh them here.")
        return redirect("litter_detail", pk=litter.pk)
    unit = request.POST.get("unit") or request.GET.get("unit") or request.session.get("weigh_unit", "g")
    unit = unit if unit in UNITS else "g"
    try:
        index = max(0, min(int(request.POST.get("kit") or request.GET.get("kit") or 0), len(kits) - 1))
    except ValueError:
        index = 0
    kit = kits[index]
    error = ""
    if request.method == "POST":
        request.session["weigh_unit"] = unit
        if "skip" not in request.POST:
            grams = to_grams(request.POST.get("value"), unit)
            if grams is None:
                error = "Enter the weight as a number, like 312."
            else:
                today = timezone.localdate()
                stored = Weight.Unit.KG if unit == "g" else Weight.Unit.LB_OZ
                existing = kit.weights.filter(date=today).order_by("-pk").first()
                if existing:
                    existing.grams, existing.unit = grams, stored
                    existing.save(update_fields=["grams", "unit"])
                else:
                    Weight.objects.create(rabbit=kit, date=today, grams=grams, unit=stored)
        if not error:
            if index + 1 < len(kits):
                return redirect(f"{reverse('litter_weigh_in', args=[litter.pk])}?kit={index + 1}&unit={unit}")
            messages.success(request, f"Weighed {len(kits)} kit{'s' if len(kits) != 1 else ''}.")
            return redirect(reverse("litter_detail", args=[litter.pk]) + "#kits")
    last = kit.weights.order_by("-date", "-pk").first()
    if last is not None:
        last_value = last.grams if unit == "g" else (Decimal(last.grams) / GRAMS_PER_OUNCE).quantize(Decimal("0.1"))
    else:
        last_value = None
    return render(request, "rabbits/weigh_in.html", {
        "litter": litter, "kit": kit, "index": index, "count": len(kits), "position": index + 1,
        "unit": unit, "units": UNITS, "unit_options": [{"value": k, "label": k, "selected": unit == k} for k in UNITS], "last": last, "last_value": last_value, "error": error,
        "value": request.POST.get("value", "") if error else "",
        "done_today": [k.pk for k in kits if k.weights.filter(date=timezone.localdate()).exists()],
        "kits": kits,
    })
