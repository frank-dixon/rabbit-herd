"""Change a rabbit's status with the follow-up each one needs, on one page that works
without JavaScript (CSS :has() shows only the chosen status's fields):
Sold asks when, to whom (an existing buyer or a new one, saved as a contact) and the price;
Culled asks when and why (saved as a cull note); Deceased asks when and the cause.
Going back to Breeding or Growing out clears the sale and death details."""
import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from .flow_forms import DEATH_CAUSES
from .models import Contact, CullNote, Rabbit, prefs
from .views import owned_rabbit

HINTS = {"breeding": "In the breeding program.", "growing": "Young stock being grown out.",
         "sold": "Went to another rabbitry or a pet home.", "culled": "Removed from the herd by you.",
         "deceased": "Died."}


def parse_date(raw, born):
    if not raw:
        return timezone.localdate(), None
    try:
        day = datetime.date.fromisoformat(raw)
    except ValueError:
        return None, "Enter a date like 2026-10-13."
    if day > timezone.localdate():
        return None, "The date can't be in the future."
    if born and day < born:
        return None, "The date can't be before the birth date."
    return day, None


@login_required
def rabbit_status(request, pk):
    rabbit = owned_rabbit(request.user, pk)
    buyers = Contact.objects.filter(owner=request.user).order_by("-is_buyer", "name")
    data = request.POST if request.method == "POST" else {}
    errors = {}
    if request.method == "POST":
        status = data.get("status", "")
        if status not in Rabbit.Status.values:
            errors["status"] = "Choose a status."
        day, date_error = parse_date(data.get(f"{status}_on", "").strip(), rabbit.birth_date)
        if date_error and status in ("sold", "culled", "deceased"):
            errors[f"{status}_on"] = date_error
        price = None
        if status == "sold" and data.get("price", "").strip():
            try:
                price = Decimal(data["price"].strip().lstrip("$").replace(",", ""))
                if price < 0 or price >= Decimal("1000000"):
                    raise InvalidOperation
            except InvalidOperation:
                errors["price"] = "Enter an amount like 45 or 45.00."
        dressed_unit = "kg" if prefs(request.user).weight_unit == "kg" else "lb"
        dressed = None
        raw = data.get("dressed", "").strip().replace(",", ".")
        if status == "culled" and raw:
            try:
                value = Decimal(raw)
                dressed = int(value * (1000 if dressed_unit == "kg" else Decimal("453.59237")))
                if not 0 < dressed <= 15000:
                    raise InvalidOperation
            except InvalidOperation:
                errors["dressed"] = "Enter a weight like 2.6 lb or 1.2 kg."
        buyer = None
        if status == "sold":
            picked = data.get("buyer", "")
            if picked and picked != "new":
                buyer = buyers.filter(pk=picked).first()
            elif data.get("buyer_name", "").strip():
                buyer = Contact(owner=request.user, name=data["buyer_name"].strip()[:120],
                                rabbitry=data.get("buyer_rabbitry", "").strip()[:120],
                                phone=data.get("buyer_phone", "").strip()[:40], is_buyer=True)
        if not errors:
            with transaction.atomic():
                rabbit.status = status
                rabbit.death_date = day if status in ("culled", "deceased") else None
                rabbit.death_cause = (data.get("cause", "").strip()[:120] if status == "deceased"
                                      else "Culled" if status == "culled" else "")
                if status == "sold":
                    if buyer is not None and buyer.pk is None:
                        buyer.save()
                    elif buyer is not None and not buyer.is_buyer:
                        Contact.objects.filter(pk=buyer.pk).update(is_buyer=True)
                    rabbit.sold_on, rabbit.sold_to, rabbit.sale_price = day, buyer, price
                else:
                    rabbit.sold_on, rabbit.sold_to, rabbit.sale_price = None, None, None
                rabbit.dressed_grams = dressed if status == "culled" else None
                rabbit.save()
                reason = data.get("reason", "").strip()[:1000]
                if status == "culled" and reason:
                    CullNote.objects.create(rabbit=rabbit, date=day, decision="cull", reason=reason)
            messages.success(request, f"{rabbit.name} is now {rabbit.get_status_display().lower()}.")
            return redirect("rabbit_detail", pk=rabbit.pk)
    chosen = data.get("status", rabbit.status)
    tiles = [{"value": v, "label": label, "hint": HINTS[v], "checked": v == chosen} for v, label in Rabbit.Status.choices]
    today = timezone.localdate()
    context = {
        "rabbit": rabbit, "tiles": tiles, "errors": errors, "buyers": buyers, "today": today.isoformat(),
        "death_causes": DEATH_CAUSES, "data": data,
        "dressed_unit": "kg" if prefs(request.user).weight_unit == "kg" else "lb",
        "dressed": data.get("dressed") or (_dressed_value(rabbit, request.user) if rabbit.dressed_grams else ""),
        "sold_on": data.get("sold_on") or (rabbit.sold_on or today).isoformat(),
        "culled_on": data.get("culled_on") or ((rabbit.death_date if rabbit.status == "culled" else None) or today).isoformat(),
        "deceased_on": data.get("deceased_on") or ((rabbit.death_date if rabbit.status == "deceased" else None) or today).isoformat(),
    }
    return render(request, "rabbits/status.html", context, status=400 if errors else 200)


def _dressed_value(rabbit, user):
    if prefs(user).weight_unit == "kg":
        return f"{Decimal(rabbit.dressed_grams) / 1000:.2f}"
    return f"{Decimal(rabbit.dressed_grams) / Decimal('453.59237'):.2f}"
