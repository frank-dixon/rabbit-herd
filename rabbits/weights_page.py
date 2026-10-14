"""The Weights page: every rabbit in the herd with its current weight, 30-day
change, a sparkline and how it sits against a sourced breed growth curve.
Table (default) or Chart (list + the selected rabbit's growth chart); the
choice is remembered per account like Grid/List on Rabbits."""

from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import growth_curve as G
from .models import Litter, Rabbit, Weight, prefs, weight_text
from .weights import WeightForm

TABS = [("all", "All"), ("breeders", "Breeders"), ("growing", "Growing out"), ("kits", "Kits"), ("overdue", "Overdue")]
AGE_GROUPS = [("adult", "Adult"), ("junior", "Junior"), ("kit", "Kit")]
SORTS = {"name": "Rabbit", "sex": "Sex", "age": "Age", "weight": "Current", "last": "Last weighed", "change": "30-day", "curve": "Vs curve"}
# Default direction when a column is first clicked.
DESC_FIRST = {"weight", "change", "curve", "age"}
KIT_DAYS, JUNIOR_DAYS = 56, 183
OVERDUE_ADULT, OVERDUE_JUNIOR = 30, 7
IN_HERD = (Rabbit.Status.BREEDING, Rabbit.Status.GROWING)


def age_group(rabbit, today):
    days = (today - rabbit.birth_date).days if rabbit.birth_date else 9999
    return "kit" if days < KIT_DAYS else "junior" if days < JUNIOR_DAYS else "adult"


def change_30(weights):
    """Latest minus the weigh-in closest to 30 days before it (from 21-45 days back), or the
    oldest one in the last 30 days when there is none that far back."""
    if len(weights) < 2:
        return None
    last = weights[-1]
    older = [w for w in weights[:-1] if 21 <= (last.date - w.date).days <= 45]
    if older:
        base = min(older, key=lambda w: abs((last.date - w.date).days - 30))
    else:
        recent = [w for w in weights[:-1] if (last.date - w.date).days <= 30]
        if not recent:
            return None
        base = recent[0]
    return last.grams - base.grams


def spark(weights, today, w=64, h=20):
    """SVG path for the Table's trend: the same 12-month window as the Chart view and a
    zero-based y axis, so a few ounces on an adult reads nearly flat and a junior climbs.
    Drawn as a monotone cubic (Fritsch-Carlson) so it is smooth without overshoot."""
    pts = [x for x in weights if (today - x.date).days <= 365]
    if len(pts) < 2:
        return ""
    start = pts[0].date
    span_d = max((pts[-1].date - start).days, 1)
    top = max(p.grams for p in pts) * 1.05
    xy = [(2 + (w - 4) * (p.date - start).days / span_d, h - 2 - (h - 4) * p.grams / top) for p in pts]
    xy = [q for i, q in enumerate(xy) if i == 0 or q[0] > xy[i - 1][0]]  # one point per x
    if len(xy) < 2:
        return ""
    n = len(xy)
    d = [(xy[i + 1][1] - xy[i][1]) / (xy[i + 1][0] - xy[i][0]) for i in range(n - 1)]
    m = [d[0]] + [0 if d[i - 1] * d[i] <= 0 else (d[i - 1] + d[i]) / 2 for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0:
            m[i] = m[i + 1] = 0
        else:
            a_, b_ = m[i] / d[i], m[i + 1] / d[i]
            if a_ * a_ + b_ * b_ > 9:
                t = 3 / (a_ * a_ + b_ * b_) ** 0.5
                m[i], m[i + 1] = t * a_ * d[i], t * b_ * d[i]
    f = lambda v: f"{v:.1f}"
    out = [f"M{f(xy[0][0])},{f(xy[0][1])}"]
    for i in range(n - 1):
        (x0, y0), (x1, y1) = xy[i], xy[i + 1]
        dx = (x1 - x0) / 3
        out.append(f"C{f(x0 + dx)},{f(y0 + m[i] * dx)} {f(x1 - dx)},{f(y1 - m[i + 1] * dx)} {f(x1)},{f(y1)}")
    return " ".join(out)


def signed(grams, unit):
    if grams is None:
        return ""
    size = weight_text(abs(grams), unit)
    return "No change" if size in ("0 oz", "0 kg") else ("+" if grams > 0 else "−") + size


def build_rows(user, today, unit):
    rabbits = (Rabbit.objects.filter(owner=user, archived_at__isnull=True, status__in=IN_HERD)
               .select_related("litter__pairing__doe", "litter__pairing__buck").prefetch_related("photos", "weights"))
    rows = []
    for r in rabbits:
        ws = sorted(r.weights.all(), key=lambda x: (x.date, x.pk))
        last = ws[-1] if ws else None
        group = age_group(r, today)
        points, curve_label = G.curve_for(r) if group != "adult" else (None, "")
        # Against the curve at the latest weigh-in inside its measured range (4-12 weeks),
        # so a 14-week junior still shows how it finished the curve.
        ref = next((x for x in reversed(ws) if points and G.expected(points, (x.date - r.birth_date).days)), None)
        ref_age = (ref.date - r.birth_date).days if ref else None
        vs = G.versus(points, ref_age, ref.grams) if ref else None
        since = (today - last.date).days if last else None
        limit = OVERDUE_ADULT if group == "adult" else OVERDUE_JUNIOR
        ch = change_30(ws)
        rows.append({
            "rabbit": r, "group": group, "weights": ws, "grams": last.grams if last else None,
            "text": weight_text(last.grams, unit) if last else "", "date": last.date if last else None,
            "since": since, "overdue": since is None or since > limit,
            "change": ch, "change_text": signed(ch, unit), "spark": spark(ws, today),
            "spark_title": f"Trend over the last {span_text([x for x in ws if (today - x.date).days <= 365]) or '12 months'}" if len(ws) > 1 else "",
            "vs": vs, "curve_label": curve_label, "has_curve": bool(points),
            "vs_text": "" if vs is None else ("On track" if abs(vs) <= G.ON_TRACK else f"{'+' if vs > 0 else '−'}{round(abs(vs) * 100)}% vs curve")
                       + (f" · wk {ref_age // 7}" if vs is not None and ref is not last else ""),
            "ref_age": ref_age,
            "vs_tone": "" if vs is None else ("g" if vs >= -G.ON_TRACK else "r"),
            "age_days": (today - r.birth_date).days if r.birth_date else None,
        })
    return rows


def keep(row, f, today):
    r = row["rabbit"]
    tab = f["tab"]
    if tab == "breeders" and not (r.status == Rabbit.Status.BREEDING and row["group"] == "adult"):
        return False
    if tab == "growing" and not (r.status == Rabbit.Status.GROWING or row["group"] == "junior"):
        return False
    if tab == "kits" and row["group"] != "kit":
        return False
    if tab == "overdue" and not row["overdue"]:
        return False
    q = f["q"].casefold()
    if q and q not in r.name.casefold() and q not in (r.tattoo or "").casefold():
        return False
    if f["sex"] and r.sex != f["sex"]:
        return False
    if f["status"] and r.status != f["status"]:
        return False
    if f["breed"] and f["breed"].casefold() not in (r.breed or "").casefold():
        return False
    if f["age"] and row["group"] != f["age"]:
        return False
    if f["litter"] and str(r.litter_id) != f["litter"]:
        return False
    return True


def sort_rows(rows, key, desc):
    """Header sort via the shared helper; unknown values always go last."""
    from . import sorting
    keys = {
        "name": lambda r: r["rabbit"].name.casefold(),
        "sex": lambda r: (r["rabbit"].sex, r["rabbit"].name.casefold()),
        "age": lambda r: r["age_days"],
        "weight": lambda r: r["grams"],
        "last": lambda r: r["date"],
        "change": lambda r: r["change"],
        "curve": lambda r: r["vs"],
    }
    return sorting.apply(rows, keys, key, desc)


RANGES = [("3m", "3 mo", 92), ("12m", "12 mo", 365), ("all", "All", None)]


def in_range(ws, key):
    """Weigh-ins in the chosen range, counted back from the latest one. All starts at the first
    weight on record, kit weights from birth included."""
    days = dict((k, d) for k, _, d in RANGES).get(key)
    return [x for x in ws if days is None or (ws[-1].date - x.date).days <= days] if ws else []


def date_ticks(first, xmax):
    """X labels that suit the span: months up to about a year, quarters to three years, then years."""
    last = first + timedelta(days=xmax)
    if xmax <= 120:
        months, fmt = 1, "%b"
    elif xmax <= 400:
        months, fmt = 2, "%b"
    elif xmax <= 1100:
        months, fmt = 3, "%b ’%y"
    else:
        months, fmt = 12, "%Y"
    y, m = first.year, first.month
    out = []
    while True:
        m += 1
        if m > 12:
            y, m = y + 1, 1
        day = first.replace(year=y, month=m, day=1)
        if day > last:
            break
        if (m - 1) % months == 0:
            out.append(((day - first).days, day.strftime(fmt)))
    return out


def span_text(ws):
    if len(ws) < 2:
        return ""
    days = (ws[-1].date - ws[0].date).days
    return f"{days} days" if days < 60 else f"{round(days / 30.4)} months" if days < 700 else f"{days / 365.25:.1f} years"


def chart(row, unit, w=640, h=280, rng="12m"):
    """The growth chart for one rabbit. Juniors with a sourced curve: by age in weeks
    (0-12) against the curve with a +/-10% band. Everyone else: the last year by date."""
    r, ws = row["rabbit"], row["weights"]
    if not ws:
        return None
    left, right, top, bottom = 56, 24, 12, 28
    pw, ph = w - left - right, h - top - bottom
    points, label = G.curve_for(r)
    by_age = bool(points) and row["group"] != "adult"
    if by_age:
        mine = [((x.date - r.birth_date).days, x.grams) for x in ws if (x.date - r.birth_date).days <= 90]
        xmax = 84 if all(d <= 84 for d, _ in mine) else 91
        gmax = max([g for _, g in mine] + [v * (1 + G.ON_TRACK) for v in points.values()])
        xs = lambda d: round(left + pw * d / xmax, 1)
        ticks_x = [(d, f"{d // 7} wk") for d in range(0, xmax + 1, 14)]
    else:
        recent = in_range(ws, rng)
        mine = [((x.date - recent[0].date).days, x.grams) for x in recent]
        xmax = max(mine[-1][0], 1)
        gmax = max(g for _, g in mine)
        xs = lambda d: round(left + pw * d / xmax, 1)
        ticks_x = date_ticks(recent[0].date, xmax)
    # Round ticks in the keeper's unit: whole pounds (2 lb steps for adults) or half kilos.
    if unit == "kg":
        step_u, per = (1 if gmax > 4000 else 0.5), 1000
        fmt = lambda n: f"{n:g} kg"
    else:
        step_u, per = (2 if gmax > 6 * 453.59 else 1), 453.59237
        fmt = lambda n: f"{n:g} lb"
    n_ticks = int(gmax / (step_u * per)) + 1
    top_g = n_ticks * step_u * per
    ys = lambda g: round(top + ph * (1 - g / top_g), 1)
    ticks_y = [(i * step_u * per, fmt(i * step_u) if i else "0") for i in range(n_ticks + 1)]
    out = {"w": w, "h": h, "left": left, "right": w - right, "bottom": h - bottom,
           "ticks_x": [{"x": xs(d), "label": t} for d, t in ticks_x],
           "ticks_y": [{"y": ys(g), "label": t} for g, t in ticks_y],
           "line": " ".join(f"{xs(d)},{ys(g)}" for d, g in mine),
           "dots": [{"x": xs(d), "y": ys(g)} for d, g in mine], "by_age": by_age, "label": label}
    if by_age:
        days = sorted(points)
        out["curve"] = " ".join(f"{xs(d)},{ys(points[d])}" for d in days)
        out["band"] = " ".join([f"{xs(d)},{ys(points[d] * (1 + G.ON_TRACK))}" for d in days] +
                               [f"{xs(d)},{ys(points[d] * (1 - G.ON_TRACK))}" for d in reversed(days)])
    return out


def range_choice(request):
    """3 mo / 12 mo / All for the Chart view, remembered per account like Table/Chart."""
    user = request.user
    asked = request.GET.get("range")
    if asked in dict(user.WEIGHTS_RANGES) and asked != user.ui_weights_range:
        user.ui_weights_range = asked
        user.save(update_fields=["ui_weights_range"])
    return user.ui_weights_range if user.ui_weights_range in dict(user.WEIGHTS_RANGES) else "12m"


def view_choice(request):
    user = request.user
    asked = request.GET.get("view")
    if asked in dict(user.WEIGHTS_VIEWS) and asked != user.ui_weights_view:
        user.ui_weights_view = asked
        user.save(update_fields=["ui_weights_view"])
    return user.ui_weights_view if user.ui_weights_view in dict(user.WEIGHTS_VIEWS) else "table"


def qs(params, **change):
    merged = {**params, **change}
    return urlencode({k: v for k, v in merged.items() if v})


@login_required
def weights_hub(request):
    today = timezone.localdate()
    unit = prefs(request.user).weight_unit
    view = view_choice(request)
    g = request.GET
    f = {"tab": g.get("tab") if g.get("tab") in dict(TABS) else "all", "q": g.get("q", "").strip(),
         "sex": g.get("sex") if g.get("sex") in Rabbit.Sex.values else "",
         "status": g.get("status") if g.get("status") in IN_HERD else "",
         "breed": g.get("breed", "").strip()[:80], "age": g.get("age") if g.get("age") in dict(AGE_GROUPS) else "",
         "litter": g.get("litter", "") if g.get("litter", "").isdigit() else ""}
    from . import sorting
    raw = g.get("sort", "")
    if g.get("dir") in ("asc", "desc") and raw and not raw.startswith("-"):  # old ?sort=x&dir=y links
        raw = sorting.token(raw, g.get("dir") == "desc")
    sort, desc = sorting.parse(raw if raw.lstrip("-") != "due" else "", SORTS, default="last")
    all_rows = build_rows(request.user, today, unit)
    rows = sort_rows([r for r in all_rows if keep(r, f, today)], sort, desc)
    params = {k: v for k, v in f.items() if v and not (k == "tab" and v == "all")}
    if raw:
        params["sort"] = sorting.token(sort, desc)
    headers = sorting.headers(SORTS.items(), sort, desc, params, DESC_FIRST)
    counts = {}
    for key, _ in TABS:
        counts[key] = sum(1 for r in all_rows if keep(r, {**f, "tab": key, "q": "", "sex": "", "status": "", "breed": "", "age": "", "litter": ""}, today))
    tabs = [{"key": k, "label": l, "count": counts[k], "on": k == f["tab"], "href": "?" + qs(params, tab="" if k == "all" else k)} for k, l in TABS]
    adults = [r["grams"] for r in all_rows if r["group"] == "adult" and r["grams"]]
    adult_changes = [r["change"] for r in all_rows if r["group"] == "adult" and r["change"] is not None]
    juniors = [r for r in all_rows if r["group"] != "adult" and r["vs"] is not None]
    stats = {
        "avg": weight_text(sum(adults) // len(adults), unit) if adults else "—",
        "avg_change": signed(sum(adult_changes) // len(adult_changes), unit) if adult_changes else "",
        "behind": sum(1 for r in juniors if r["vs"] < -G.ON_TRACK), "juniors": len(juniors),
        "overdue": sum(1 for r in all_rows if r["overdue"]),
        "week": sum(1 for r in all_rows if r["since"] is not None and r["since"] <= 7), "herd": len(all_rows),
    }
    from pages import minibars as MB

    wk = MB.weeks(today)
    stamps = [(x.date, r["rabbit"].pk) for r in all_rows for x in r["weights"]]
    stats["week_bars"] = MB.bars(wk, [len({pk for d, pk in stamps if a <= d <= z}) for a, z, _ in wk], "rabbits weighed per week")
    mo = MB.months(today)
    adult_ws = [(x.date, x.grams) for r in all_rows if r["group"] == "adult" for x in r["weights"]]
    avg = lambda a, z: (lambda g: sum(g) // len(g) if g else None)([gr for d, gr in adult_ws if a <= d <= z])
    stats["avg_bars"] = MB.bars(mo, [avg(a, z) for a, z, _ in mo], "average adult weight by month", lambda v: weight_text(v, unit) if v else "none")
    sel = None
    if view == "chart" and rows:
        pick = g.get("sel", "")
        sel = next((r for r in rows if str(r["rabbit"].pk) == pick), rows[0])
        rng = range_choice(request)
        sel["chart"] = chart(sel, unit, rng=rng)
        shown = in_range(sel["weights"], rng)
        prev = {w.pk: p for p, w in zip([None] + sel["weights"][:-1], sel["weights"])}
        sel["log"] = [{"date": w.date, "text": weight_text(w.grams, unit),
                       "gain": signed(w.grams - prev[w.pk].grams, unit) if prev[w.pk] else ""} for w in reversed(shown)]
        sel["range_options"] = [{"href": "?" + qs(params, sel=sel["rabbit"].pk, range=k), "label": l, "selected": k == rng} for k, l, _ in RANGES]
        sel["range_label"] = dict((k, l) for k, l, _ in RANGES)[rng]
        ref_days = sel["ref_age"]
        points, _ = G.curve_for(sel["rabbit"])
        ref = G.expected(points, ref_days) if points and sel["group"] != "adult" and ref_days is not None else None
        sel["vs_pct"] = "" if sel["vs"] is None else f"{'+' if sel['vs'] > 0 else '−' if sel['vs'] < 0 else ''}{round(abs(sel['vs']) * 100)}%"
        sel["ref_text"] = weight_text(int(ref), unit) if ref else ""
        sel["ref_week"] = ref_days // 7 if ref else None
        span = [w for w in sel["weights"] if (sel["date"] - w.date).days <= 30] if sel["date"] else []
        sel["daily"] = f"{round((span[-1].grams - span[0].grams) / max((span[-1].date - span[0].date).days, 1))} g" if len(span) > 1 else ""
    for r in rows:
        r["sel_href"] = "?" + qs(params, sel=r["rabbit"].pk)
    litter_ids = {r["rabbit"].litter_id for r in all_rows if r["rabbit"].litter_id}
    litters = Litter.objects.filter(pk__in=litter_ids).select_related("pairing__doe", "pairing__buck").order_by("-kindled_on")
    chips = [k for k in ("sex", "status", "breed", "age", "litter") if f[k]]
    return render(request, "hub/weights.html", {
        "rows": rows, "all_count": len(all_rows), "wide": True, "view": view, "f": f, "tabs": tabs, "headers": headers,
        "stats": stats, "sel": sel, "unit": unit, "today": today,
        "view_options": [{"href": "?" + qs(params, view=k), "label": l, "icon": "list" if k == "table" else "chart", "selected": view == k}
                         for k, l in request.user.WEIGHTS_VIEWS],
        "sex_options": Rabbit.Sex.choices, "status_options": [(s, Rabbit.Status(s).label) for s in IN_HERD],
        "breed_options": sorted({r["rabbit"].breed for r in all_rows if r["rabbit"].breed}),
        "age_options": AGE_GROUPS,
        "litter_options": [(l.pk, f"{l.pairing.doe.name} × {l.pairing.buck.name} · {l.kindled_on:%b %-d, %Y}" if l.kindled_on else str(l)) for l in litters],
        "filter_count": len(chips), "filtering": bool(chips or f["q"]),
        "clear_qs": qs({"tab": params.get("tab", "")}),
        "sort_options": [{"value": sorting.token(k, k in DESC_FIRST), "label": l, "selected": k == sort} for k, l in SORTS.items()],
        "sort": sort, "desc": desc, "here": request.get_full_path(),
        # Back-compat for callers reading the old sort.
        "sort_hint": "",
    })


@login_required
@require_POST
def weight_log(request, pk):
    """Inline Log weight from the Weights page. JSON for the page script; a plain
    form post redirects back to the page."""
    rabbit = get_object_or_404(Rabbit, owner=request.user, pk=pk)
    data = request.POST.copy()
    if not data.get("date"):
        data["date"] = timezone.localdate().isoformat()
    form = WeightForm(data, rabbit=rabbit)
    back = request.POST.get("next", "")
    back = back if back.startswith("/weights/") else "/weights/"
    wants_json = "application/json" in request.headers.get("Accept", "")
    if form.is_valid():
        d = form.cleaned_data
        w = Weight.objects.create(rabbit=rabbit, date=d["day"], grams=d["grams"], unit=d["unit"], note=d["note"])
        text = f"{rabbit.name}: {weight_text(w.grams, prefs(request.user).weight_unit)} logged."
        if wants_json:
            return JsonResponse({"ok": True, "message": text})
        messages.success(request, text, extra_tags="toast")
        return redirect(back)
    first = next(iter(form.errors.values()))[0]
    if wants_json:
        return JsonResponse({"ok": False, "error": first}, status=400)
    messages.error(request, f"The weight wasn't saved. {first}", extra_tags="toast")
    return redirect(back)


@login_required
def weigh_group(request):
    """Weigh a group: one row per chosen rabbit, saved together."""
    unit = prefs(request.user).weight_unit
    raw = request.POST.getlist("ids") if request.method == "POST" else request.GET.getlist("ids")
    ids = [int(i) for part in raw for i in part.split(",") if i.isdigit()]
    if not ids:  # nothing ticked: everyone the page was showing
        src = request.POST if request.method == "POST" else request.GET
        ids = [int(i) for i in src.get("all", "").split(",") if i.isdigit()]
    rabbits = list(Rabbit.objects.filter(owner=request.user, pk__in=ids, archived_at__isnull=True).order_by("name"))
    errors, saved = {}, 0
    if request.method == "POST":
        day = request.POST.get("date") or timezone.localdate().isoformat()
        pending = []
        for r in rabbits:
            vals = {k: request.POST.get(f"w{r.pk}-{k}", "") for k in ("lb", "oz", "kg")}
            if not any(v.strip() for v in vals.values()):
                continue
            form = WeightForm({"date": day, **vals}, rabbit=r)
            if form.is_valid():
                pending.append((r, form.cleaned_data))
            else:
                errors[r.pk] = next(iter(form.errors.values()))[0]
        if not errors:
            for r, d in pending:
                Weight.objects.create(rabbit=r, date=d["day"], grams=d["grams"], unit=d["unit"])
            saved = len(pending)
            messages.success(request, f"{saved} weight{'s' if saved != 1 else ''} logged.", extra_tags="toast")
            return redirect("/weights/")
    latest = {}
    for w in Weight.objects.filter(rabbit__in=rabbits).order_by("date", "pk"):
        latest[w.rabbit_id] = w
    rows = [{"rabbit": r, "last": weight_text(latest[r.pk].grams, unit) if r.pk in latest else "",
             "last_date": latest[r.pk].date if r.pk in latest else None, "error": errors.get(r.pk),
             "values": {k: request.POST.get(f"w{r.pk}-{k}", "") for k in ("lb", "oz", "kg")}} for r in rabbits]
    return render(request, "hub/weigh_group.html", {"rows": rows, "unit": unit, "today": timezone.localdate(),
                                                     "ids": ",".join(str(r.pk) for r in rabbits)},
                  status=400 if errors else 200)
