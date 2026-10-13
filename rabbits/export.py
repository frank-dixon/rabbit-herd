"""CSV exports of the signed-in keeper's own records: rabbits, litters,
weights, show results and costs. Cells that a spreadsheet would read as a
formula are prefixed with an apostrophe."""

import csv

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.utils import timezone

from . import purebred
from .models import Expense, Litter, Rabbit, ShowEntry, Weight, prefs, weight_text


def safe(value):
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _date(value):
    return value.isoformat() if value else ""


def rabbits(user):
    rows = purebred.mark(list(Rabbit.objects.filter(owner=user).select_related("location", "source").prefetch_related(*purebred.PREFETCH)))
    from django.conf import settings

    loc = settings.FEATURE_LOCATIONS
    yield ["Name", "Ear tattoo", "Sex", "Breed", "Purebred", "Color", "Line", "Born", "Status", *(["Location"] if loc else []),
           "Came from", "Died", "Cause of death", "Archived"]
    for r in rows:
        yield [r.name, r.tattoo, r.get_sex_display(), r.breed_line(), "Yes" if r.purebred_info else "No", r.color_line, r.line,
               _date(r.birth_date), r.get_status_display(), *([r.location.name if r.location else ""] if loc else []),
               str(r.source) if r.source else "", _date(r.death_date), r.death_cause, "Yes" if r.archived_at else "No"]


def litters(user):
    yield ["Doe", "Buck", "Bred", "Due", "Kindled", "Born alive", "Born dead", "Lost since", "Surviving", "Kits in herd", "Notes"]
    for l in Litter.objects.filter(owner=user).select_related("pairing__doe", "pairing__buck").prefetch_related("kits"):
        yield [l.pairing.doe.name, l.pairing.buck.name, _date(l.bred_on), _date(l.due_on), _date(l.kindled_on),
               "" if l.born_alive is None else l.born_alive, l.born_dead, l.died_after,
               "" if l.survivors is None else l.survivors, ", ".join(k.name for k in l.kits.all()), l.notes]


def weights(user):
    yield ["Rabbit", "Ear tattoo", "Date", "Weight", "Grams", "Pounds", "Kilograms", "Note"]
    unit = prefs(user).weight_unit
    for w in Weight.objects.filter(rabbit__owner=user).select_related("rabbit").order_by("rabbit__name", "date", "pk"):
        yield [w.rabbit.name, w.rabbit.tattoo, _date(w.date), weight_text(w.grams, unit), w.grams, f"{w.grams / 453.59237:.2f}",
               f"{w.grams / 1000:.3f}", w.note]


def shows(user):
    yield ["Rabbit", "Show", "Date", "Location", "Class", "Placed", "Class size", "Award", "Judge", "Leg", "Notes"]
    for s in ShowEntry.objects.filter(rabbit__owner=user).select_related("rabbit").order_by("date", "pk"):
        yield [s.rabbit.name, s.show_name, _date(s.date), s.location, s.show_class, s.placing or "", s.out_of or "",
               s.award, s.judge, "Yes" if s.leg else "No", s.notes]


def costs(user):
    yield ["Date", "Category", "What", "Amount", "Pounds", "Per lb", "Rabbit", "Litter"]
    for e in Expense.objects.filter(owner=user).select_related("rabbit", "litter__pairing__doe", "litter__pairing__buck").order_by("date", "pk"):
        yield [_date(e.date), e.get_category_display(), e.description, e.amount, e.weight_lb or "", e.per_lb or "",
               e.rabbit.name if e.rabbit else "", str(e.litter) if e.litter else ""]


EXPORTS = {"rabbits": rabbits, "litters": litters, "weights": weights, "shows": shows, "costs": costs}


@login_required
def export_csv(request, kind):
    builder = EXPORTS.get(kind)
    if builder is None:
        raise Http404
    stamp = timezone.localdate().isoformat()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="bramble-burrow-{kind}-{stamp}.csv"'
    response["Cache-Control"] = "private, no-store"
    response.write("\ufeff")  # so Excel reads UTF-8
    writer = csv.writer(response)
    for row in builder(request.user):
        writer.writerow([safe(cell) for cell in row])
    return response
