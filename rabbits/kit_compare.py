"""Side-by-side photos of a litter's kits, lined up by age or by date.

Each kit is a column. Rows are the week of age the photo was taken in
(from the photo's taken date when usable, else the day it was added), or
the calendar date. Several photos of one kit in one row show the latest
first; the rest are counted.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .litters import own_litter
from .models import valid_taken_date


def photo_day(photo, birth_date):
    return valid_taken_date(photo.taken_at, birth_date) or timezone.localdate(photo.uploaded_at)


def compare_rows(kits, by="age"):
    """[(label, [[photo, ...] per kit])], oldest row first."""
    rows = {}
    for column, kit in enumerate(kits):
        for photo in kit.photos.all():
            day = photo_day(photo, kit.birth_date)
            if by == "date":
                key = day
            else:
                key = max((day - kit.birth_date).days, 0) // 7
            cells = rows.setdefault(key, [[] for _ in kits])
            cells[column].append((day, photo))
    result = []
    for key in sorted(rows):
        if by == "date":
            label = f"{key:%b} {key.day}, {key.year}"
        else:
            label = "Under 1 week" if key == 0 else f"{key} week{'s' if key != 1 else ''}"
        cells = [[photo for _, photo in sorted(cell, key=lambda item: (item[0], item[1].pk), reverse=True)] for cell in rows[key]]
        result.append((label, cells))
    return result


@login_required
def litter_compare(request, pk):
    litter = own_litter(request, pk)
    by = "date" if request.GET.get("by") == "date" else "age"
    kits = list(litter.kits.prefetch_related("photos").order_by("name", "pk"))
    rows = compare_rows(kits, by)
    return render(request, "rabbits/litter_compare.html", {
        "litter": litter, "kits": kits, "rows": rows, "by": by, "wide": True,
    })
