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
    pts = [x for x in weights if (today - x.date).days <= 365][-12:]
    if len(pts) < 2:
        return ""
    lo, hi = min(p.grams for p in pts), max(p.grams for p in pts)
    span_d = max((pts[-1].date - pts[0].date).days, 1)
    span_g = max(hi - lo, 1)
    return " ".join(f"{round(2 + (w - 4) * (p.date - pts[0].date).days / span_d, 1)},{round(h - 2 - (h - 4) * (p.grams - lo) / span_g, 1)}" for p in pts)


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
    none_last = lambda v: (v is None, v)
    keys = {
        "name": lambda r: r["rabbit"].name.casefold(),
        "sex": lambda r: (r["rabbit"].sex, r["rabbit"].name.casefold()),
        "age": lambda r: r["age_days"] or 0,
        "weight": lambda r: r["grams"] or 0,
        "last": lambda r: r["date"] or timezone.datetime.min.date(),
        "change": lambda r: r["change"] if r["change"] is not None else -10**9,
        "curve": lambda r: r["vs"] if r["vs"] is not None else -10**9,
    }
    rows.sort(key=keys[key], reverse=desc)
    if key in ("change", "curve", "weight"):  # unknowns always last
        field = {"change": "change", "curve": "vs", "weight": "grams"}[key]
        rows.sort(key=lambda r: r[field] is None)
    return rows


def chart(row, unit, w=640, h=280):
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
        recent = [x for x in ws if (ws[-1].date - x.date).days <= 365]
        mine = [((x.date - recent[0].date).days, x.grams) for x in recent]
        xmax = max(mine[-1][0], 1)
        gmax = max(g for _, g in mine)
        xs = lambda d: round(left + pw * d / xmax, 1)
        first = recent[0].date
        ticks_x = [(d, (first + timedelta(days=d)).strftime("%b")) for d in range(0, xmax + 1, max(xmax // 4, 1))]
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
    sort = g.get("sort") if g.get("sort") in SORTS else "last"
    if sort == "due":
        sort = "last"
    desc = g.get("dir") == "desc" if g.get("dir") in ("asc", "desc") else sort in DESC_FIRST
    all_rows = build_rows(request.user, today, unit)
    rows = sort_rows([r for r in all_rows if keep(r, f, today)], sort, desc)
    params = {k: v for k, v in f.items() if v and not (k == "tab" and v == "all")}
    if sort != "last" or g.get("dir"):
        params.update(sort=sort, dir="desc" if desc else "asc")
    headers = []
    for key, label in SORTS.items():
        on = key == sort
        nd = (not desc) if on else key in DESC_FIRST
        headers.append({"key": key, "label": label, "on": on, "desc": desc if on else None,
                        "href": "?" + qs(params, sort=key, dir="desc" if nd else "asc")})
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
    sel = None
    if view == "chart" and rows:
        pick = g.get("sel", "")
        sel = next((r for r in rows if str(r["rabbit"].pk) == pick), rows[0])
        sel["chart"] = chart(sel, unit)
        sel["log"] = [{"date": w.date, "text": weight_text(w.grams, unit),
                       "gain": signed(w.grams - p.grams, unit) if p else ""}
                      for p, w in reversed(list(zip([None] + sel["weights"][:-1], sel["weights"])))][:6]
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
        "sort_options": [{"value": f"{k}:{'desc' if k in DESC_FIRST else 'asc'}", "label": l, "selected": k == sort} for k, l in SORTS.items()],
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
