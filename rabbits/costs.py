"""Feed purchases and other costs, with simple totals.

One form adds a cost or, with ?edit=<id>, edits one. A cost can be linked
to a rabbit or a litter, which counts it on that page. Totals cover this
month, this year and all time, plus this month's feed per active rabbit
and the year's average feed price per pound.
"""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .health import parse
from .models import Expense, Litter, Rabbit

CENT = Decimal("0.01")


def _decimal(raw, limit):
    raw = (raw or "").strip().replace("$", "").replace(",", "")
    if not raw:
        return None, True
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None, False
    if value < 0 or value >= limit or not value.is_finite():
        return None, False
    return value.quantize(CENT), True


def _options(user):
    rabbits = [(str(pk), name) for pk, name in Rabbit.objects.filter(owner=user, archived_at__isnull=True).values_list("pk", "name")]
    litters = [(str(litter.pk), str(litter)) for litter in Litter.objects.filter(owner=user).select_related("pairing__doe", "pairing__buck")]
    return rabbits, litters


def _clean(request):
    post = request.POST
    values = {key: post.get(key, "").strip() for key in ("date", "category", "description", "amount", "weight_lb", "rabbit", "litter")}
    errors = {}
    day = parse(values["date"])
    if day is None:
        errors["date"] = ["Please enter the date."]
    elif day > timezone.localdate():
        errors["date"] = ["That date is in the future. Please check it."]
    if values["category"] not in Expense.Category.values:
        errors["category"] = ["Please choose a category."]
    if not values["description"]:
        errors["description"] = ["Please say what it was, like 50 lb pellets."]
    amount, ok = _decimal(values["amount"], Decimal("1000000"))
    if amount is None:
        errors["amount"] = ["Please enter the amount, like 18.99."]
    weight, ok = _decimal(values["weight_lb"], Decimal("100000"))
    if not ok:
        errors["weight_lb"] = ["Please enter pounds as a number, like 50."]
    rabbit = litter = None
    if values["rabbit"]:
        rabbit = Rabbit.objects.filter(owner=request.user, pk=values["rabbit"]).first() if values["rabbit"].isdigit() else None
        if rabbit is None:
            errors["rabbit"] = ["Please choose one of your rabbits."]
    if values["litter"]:
        litter = Litter.objects.filter(owner=request.user, pk=values["litter"]).first() if values["litter"].isdigit() else None
        if litter is None:
            errors["litter"] = ["Please choose one of your litters."]
    cleaned = {"date": day, "category": values["category"], "description": values["description"][:120],
               "amount": amount, "weight_lb": weight, "rabbit": rabbit, "litter": litter}
    return values, errors, cleaned


def totals(user, today=None):
    today = today or timezone.localdate()
    mine = Expense.objects.filter(owner=user)
    month = mine.filter(date__year=today.year, date__month=today.month)
    year = mine.filter(date__year=today.year)
    total = lambda qs: qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    active = Rabbit.objects.filter(owner=user, archived_at__isnull=True).exclude(
        status__in=[Rabbit.Status.DECEASED, Rabbit.Status.SOLD, Rabbit.Status.CULLED]).count()
    feed_month = total(month.filter(category=Expense.Category.FEED))
    feed_year = year.filter(category=Expense.Category.FEED, weight_lb__isnull=False).aggregate(
        amount=Sum("amount"), pounds=Sum("weight_lb"))
    labels = dict(Expense.Category.choices)
    by_category = [(labels[row["category"]], row["total"]) for row in
                   year.values("category").annotate(total=Sum("amount")).order_by("-total")]
    return {
        "month": total(month), "year": total(year), "all": total(mine),
        "by_category": by_category, "active": active,
        "feed_per_rabbit": (feed_month / active).quantize(CENT) if active and feed_month else None,
        "price_per_lb": (feed_year["amount"] / feed_year["pounds"]).quantize(CENT) if feed_year["pounds"] else None,
        "month_label": f"{today:%B}", "year_label": str(today.year),
    }


def _render(request, values, errors, editing, status=200):
    rabbits, litters = _options(request.user)
    expenses = list(Expense.objects.filter(owner=request.user).select_related("rabbit", "litter__pairing__doe", "litter__pairing__buck")[:200])
    return render(request, "rabbits/costs.html", {
        "expenses": expenses, "values": values, "errors": errors, "editing": editing,
        "categories": Expense.Category.choices, "rabbit_options": rabbits, "litter_options": litters,
        "totals": totals(request.user), "today_iso": timezone.localdate().isoformat(), "wide": True,
    }, status=status)


@login_required
def cost_list(request):
    if request.method == "POST":
        values, errors, cleaned = _clean(request)
        if not errors:
            Expense.objects.create(owner=request.user, **cleaned)
            messages.success(request, "Cost added.")
            return redirect("cost_list")
        return _render(request, values, errors, None, status=400)
    editing = None
    if request.GET.get("edit", "").isdigit():
        editing = Expense.objects.filter(owner=request.user, pk=request.GET["edit"]).first()
    if editing:
        values = {"date": editing.date.isoformat(), "category": editing.category, "description": editing.description,
                  "amount": str(editing.amount), "weight_lb": str(editing.weight_lb or ""),
                  "rabbit": str(editing.rabbit_id or ""), "litter": str(editing.litter_id or "")}
    else:
        values = {"date": timezone.localdate().isoformat(), "category": Expense.Category.FEED,
                  "rabbit": request.GET.get("rabbit", ""), "litter": request.GET.get("litter", "")}
    return _render(request, values, {}, editing)


@login_required
@require_POST
def cost_edit(request, pk):
    expense = get_object_or_404(Expense, owner=request.user, pk=pk)
    values, errors, cleaned = _clean(request)
    if errors:
        return _render(request, values, errors, expense, status=400)
    for key, value in cleaned.items():
        setattr(expense, key, value)
    expense.save()
    messages.success(request, "Cost saved.")
    return redirect("cost_list")


@login_required
@require_POST
def cost_delete(request, pk):
    get_object_or_404(Expense, owner=request.user, pk=pk).delete()
    messages.success(request, "The cost was removed.")
    return redirect("cost_list")


def linked(expenses):
    """(list, total) for a rabbit's or litter's linked costs."""
    items = list(expenses)
    return items, sum((item.amount for item in items), Decimal("0"))
