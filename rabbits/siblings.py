"""Compare siblings: one litter's kits side by side by growth.

A server-drawn chart plots each kit's weight against its age in weeks, with a
dashed litter average, and a card per kit shows its weight at 4, 8 and 12
weeks, its average daily gain and its latest keep-or-cull decision. Kits are
ranked by their latest weight. No JavaScript is needed: the legend chips are
checkboxes that hide a line with CSS alone.
"""

import math

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from .litters import own_litter
from .models import GRAMS_PER_OUNCE, Weight, prefs, weight_text
from .weights import nice_step

# Distinct, colorblind-aware hues that read on light and dark surfaces.
PALETTE = ["#0f766e", "#d9603b", "#7c5cbf", "#c48a12", "#3b7fc4", "#6b8e23", "#b04a87", "#5f6b7a",
           "#0e9aa7", "#a0522d"]
MILESTONES = (4, 8, 12)
WINDOW_DAYS = 5  # a weighing counts for a milestone within this many days of it


def to_unit(grams, unit):
    return grams / 1000 if unit == Weight.Unit.KG else grams / float(GRAMS_PER_OUNCE) / 16


def short_value(grams, unit):
    return f"{to_unit(grams, unit):.1f}"


def kit_rows(kits, unit):
    rows = []
    for index, kit in enumerate(kits):
        weights = sorted(kit.weights.all(), key=lambda w: (w.date, w.pk))
        birth = kit.birth_date
        points = [((w.date - birth).days, w.grams) for w in weights if w.date >= birth]
        milestones = []
        for week in MILESTONES:
            near = [(abs(day - week * 7), grams) for day, grams in points if abs(day - week * 7) <= WINDOW_DAYS]
            milestones.append({"week": week, "value": short_value(min(near)[1], unit) if near else ""})
        gain = None
        if len(points) > 1 and points[-1][0] > points[0][0]:
            gain = round((points[-1][1] - points[0][1]) / (points[-1][0] - points[0][0]))
        cull = next(iter(kit.cull_notes.all()), None)
        rows.append({
            "kit": kit, "color": PALETTE[index % len(PALETTE)], "index": index, "points": points,
            "latest": points[-1][1] if points else None,
            "latest_text": short_value(points[-1][1], unit) if points else "",
            "latest_full": weight_text(points[-1][1], unit) if points else "",
            "milestones": milestones, "gain": gain, "cull": cull,
        })
    weighed = sorted((r for r in rows if r["latest"] is not None), key=lambda r: -r["latest"])
    for rank, row in enumerate(weighed, 1):
        row["rank"] = rank
    return rows, len(weighed)


def at_age(points, day):
    """A kit's weight at an age by straight lines between weighings; None outside them."""
    for (d0, g0), (d1, g1) in zip(points, points[1:]):
        if d0 <= day <= d1:
            return g0 if d1 == d0 else g0 + (g1 - g0) * (day - d0) / (d1 - d0)
    if points and points[0][0] == day:
        return points[0][1]
    return None


def growth_chart(rows, unit, width=640, height=300, right=92):
    series = [r for r in rows if r["points"]]
    if not series:
        return None
    left, top, bottom = 52, 12, 46
    plot_w, plot_h = width - left - right, height - top - bottom
    last_day = max(max(day for day, _ in r["points"]) for r in series)
    weeks = max(1, math.ceil(last_day / 7))
    max_value = max(to_unit(g, unit) for r in series for _, g in r["points"])
    step = nice_step(max(max_value, 0.5))
    top_value = step * math.ceil(max_value / step) or step

    def x(day):
        return round(left + plot_w * day / (weeks * 7), 1)

    def y(value):
        return round(top + plot_h * (1 - value / top_value), 1)

    week_step = 1 if weeks <= 6 else 2 if weeks <= 14 else 4
    x_ticks = [{"x": x(w * 7), "label": str(w)} for w in range(0, weeks + 1, week_step)]
    y_ticks = []
    value = 0.0
    while value <= top_value + 1e-9:
        y_ticks.append({"y": y(value), "label": f"{value:g}"})
        value += step
    lines = []
    for r in series:
        pts = [(x(day), y(to_unit(g, unit))) for day, g in r["points"]]
        lines.append({"index": r["index"], "color": r["color"], "name": r["kit"].name,
                      "points": " ".join(f"{a},{b}" for a, b in pts), "end": pts[-1],
                      "dots": [{"x": a, "y": b} for a, b in pts]})
    # End labels: in weight order, nudged apart so they never overlap.
    placed = sorted(lines, key=lambda l: l["end"][1])
    previous = -1e9
    for line in placed:
        line["label_y"] = max(line["end"][1], previous + 13)
        previous = line["label_y"]
    overflow = previous - (top + plot_h)
    if overflow > 0:
        for line in placed:
            line["label_y"] = round(line["label_y"] - overflow, 1)
    average = []
    for day in range(0, weeks * 7 + 1, 7):
        values = [v for v in (at_age(r["points"], day) for r in series) if v is not None]
        if len(values) >= 2:
            average.append(f"{x(day)},{y(to_unit(sum(values) / len(values), unit))}")
    return {
        "width": width, "height": height, "left": left, "right": width - right, "top": top, "bottom": height - bottom,
        "x_ticks": x_ticks, "y_ticks": y_ticks, "lines": lines, "label_x": width - right + 8,
        "average": " ".join(average) if len(average) >= 2 else "",
        "x_title": "Age (weeks)", "y_title": "Weight (kg)" if unit == Weight.Unit.KG else "Weight (lb)",
        "mid_x": round(left + plot_w / 2, 1), "mid_y": round(top + plot_h / 2, 1),
        "summary": f"Weight by age for {len(series)} kit{'s' if len(series) != 1 else ''}, up to {weeks} weeks.",
    }


@login_required
def litter_siblings(request, pk):
    litter = own_litter(request, pk)
    unit = prefs(request.user).weight_unit
    kits = list(litter.kits.prefetch_related("weights", "cull_notes", "photos").order_by("birth_date", "name", "pk"))
    rows, weighed = kit_rows(kits, unit)
    sort = "name" if request.GET.get("sort") == "name" else "rank"
    cards = sorted(rows, key=(lambda r: r["kit"].name.lower()) if sort == "name"
                   else (lambda r: (r.get("rank") or 10**6, r["kit"].name.lower())))
    return render(request, "rabbits/litter_siblings.html", {
        "litter": litter, "rows": rows, "cards": cards, "weighed": weighed, "chart": growth_chart(rows, unit),
        # Phones get their own narrower drawing, so the text stays readable.
        "chart_sm": growth_chart(rows, unit, width=360, height=320, right=66),
        "unit_label": "kg" if unit == Weight.Unit.KG else "lb", "sort": sort,
        "sort_options": [{"href": "?", "label": "Rank", "selected": sort == "rank"},
                         {"href": "?sort=name", "label": "Name", "selected": sort == "name"}],
        "weigh_url": reverse("litter_weigh_in", args=[litter.pk]),
        "photos_url": reverse("litter_compare", args=[litter.pk]),
        "wide": True,
    })
