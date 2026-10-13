"""Weights: quick entry per rabbit and a server-rendered SVG growth chart."""

import math
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import GRAMS_PER_OUNCE, Rabbit, Weight, prefs, weight_text

DATE_REQUIRED = "A weight needs a date. Please enter the day it was weighed."
DATE_FUTURE = "The date can't be in the future. Please check it."
DATE_BEFORE_BIRTH = "The date can't be before the rabbit was born. Please check it."
WEIGHT_REQUIRED = "Please enter a weight, like 4 lb 6 oz or 2.1 kg."
WEIGHT_RANGE = "That weight looks off. Please enter a weight more than 0 and up to 30 kg (66 lb)."
BOTH_UNITS = "Enter the weight in lb and oz, or in kg, but not both."
NOTE_TOO_LONG = "A note can be up to 200 characters. Please shorten it."


def number(text):
    text = (text or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return "bad"
    return value if value.is_finite() and value >= 0 else "bad"


class WeightForm(forms.Form):
    date = forms.CharField(required=False)
    lb = forms.CharField(required=False)
    oz = forms.CharField(required=False)
    kg = forms.CharField(required=False)
    note = forms.CharField(required=False)

    def __init__(self, *args, rabbit, **kwargs):
        super().__init__(*args, **kwargs)
        self.rabbit = rabbit

    def clean(self):
        data = super().clean()
        raw = (data.get("date") or "").strip()
        day = None
        try:
            day = forms.DateField().clean(raw) if raw else None
        except forms.ValidationError:
            pass
        if day is None:
            self.add_error("date", DATE_REQUIRED)
        elif day > timezone.localdate():
            self.add_error("date", DATE_FUTURE)
        elif day < self.rabbit.birth_date:
            self.add_error("date", DATE_BEFORE_BIRTH)
        has_kg = bool((data.get("kg") or "").strip())
        has_lb = bool((data.get("lb") or "").strip() or (data.get("oz") or "").strip())
        unit = Weight.Unit.KG if has_kg and not has_lb else Weight.Unit.LB_OZ
        if has_kg and has_lb:
            self.add_error("kg", BOTH_UNITS)
            grams, field = Decimal(1), "kg"
        elif unit == Weight.Unit.KG:
            kg = number(data.get("kg"))
            grams = None if kg in (None, "bad") else kg * 1000
            field = "kg"
        else:
            lb, oz = number(data.get("lb")), number(data.get("oz"))
            grams = None if "bad" in (lb, oz) or (lb is None and oz is None) else ((lb or 0) * 16 + (oz or 0)) * GRAMS_PER_OUNCE
            field = "lb"
        if has_kg and has_lb:
            pass
        elif grams is None:
            self.add_error(field, WEIGHT_REQUIRED)
        elif not 0 < grams <= 30000:
            self.add_error(field, WEIGHT_RANGE)
        note = " ".join((data.get("note") or "").split())
        if len(note) > 200:
            self.add_error("note", NOTE_TOO_LONG)
        data.update(day=day, unit=unit, grams=int(grams.quantize(Decimal("1"))) if grams else None, note=note)
        return data


@login_required
@require_POST
def weight_add(request, pk):
    rabbit = get_object_or_404(Rabbit, owner=request.user, pk=pk)
    form = WeightForm(request.POST, rabbit=rabbit)
    if form.is_valid():
        data = form.cleaned_data
        weight = Weight.objects.create(rabbit=rabbit, date=data["day"], grams=data["grams"], unit=data["unit"], note=data["note"])
        messages.success(request, f"{weight_text(weight.grams, prefs(request.user).weight_unit)} on {weight.date:%b} {weight.date.day} was added.")
        request.session["weight_unit"] = data["unit"]
    else:
        for errors in form.errors.values():
            messages.error(request, errors[0])
    return redirect(f"/rabbits/{rabbit.pk}/#weights")


@login_required
@require_POST
def weight_delete(request, pk):
    weight = get_object_or_404(Weight, rabbit__owner=request.user, pk=pk)
    weight.delete()
    messages.success(request, "The weight was removed.")
    return redirect(f"/rabbits/{weight.rabbit_id}/#weights")


def nice_step(span, ticks=4):
    raw = span / ticks
    power = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        if raw <= factor * power:
            return factor * power
    return 10 * power


def chart(weights, unit, width=400, height=200):
    """Points and axes for the growth chart, in the given unit (lb or kg).
    Returns None with fewer than one weight."""
    if not weights:
        return None
    left, right, top, bottom = 44, 10, 10, 26
    to_unit = (lambda g: g / 1000) if unit == Weight.Unit.KG else (lambda g: g / float(GRAMS_PER_OUNCE) / 16)
    values = [to_unit(w.grams) for w in weights]
    step = nice_step(max(max(values), 0.5))
    top_value = step * math.ceil(max(values) / step) or step
    first, last = weights[0].date, weights[-1].date
    days = max((last - first).days, 1)
    plot_w, plot_h = width - left - right, height - top - bottom

    def x(day):
        return round(left + (plot_w * (day - first).days / days if len(weights) > 1 else plot_w / 2), 1)

    def y(value):
        return round(top + plot_h * (1 - value / top_value), 1)

    points = [{"x": x(w.date), "y": y(v), "label": f"{w.date:%b} {w.date.day}, {w.date.year}: {weight_text(w.grams, unit)}"}
              for w, v in zip(weights, values)]
    suffix = " kg" if unit == Weight.Unit.KG else " lb"
    ticks = []
    value = 0.0
    while value <= top_value + 1e-9:
        ticks.append({"y": y(value), "label": f"{value:g}{suffix}"})
        value += step
    return {
        "width": width, "height": height, "left": left, "right": width - right, "bottom": height - bottom, "top": top,
        "points": points, "polyline": " ".join(f"{p['x']},{p['y']}" for p in points), "ticks": ticks,
        "first": f"{first:%b} {first.day}", "last": f"{last:%b} {last.day}", "single": len(weights) == 1,
        "summary": f"Weight from {weight_text(weights[0].grams, unit)} on {first:%b} {first.day}, {first.year} "
                   f"to {weight_text(weights[-1].grams, unit)} on {last:%b} {last.day}, {last.year}.",
    }
