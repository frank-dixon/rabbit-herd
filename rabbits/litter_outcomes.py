"""Past litters and each litter's outcome: what became of every kit (kept,
sold, processed, lost), live and dressed weights, dress-out and feed cost
per dressed pound, plus a dated notes timeline."""

from datetime import timedelta
from decimal import Decimal

from .models import GRAMS_PER_OUNCE, Rabbit, weight_text

# A kindled litter counts as Past once every kit has an outcome, or this many
# days after kindling, whichever comes first.
PAST_AFTER_DAYS = 120

KINDS = ("kept", "sold", "processed", "lost")
LABELS = {"kept": "Kept", "sold": "Sold", "processed": "Processed", "lost": "Lost", "growing": "Growing out"}


# A breeding-status kit only counts as Kept once it is past fryer age; before
# that it is still growing out (kits are often entered as breeding by default).
KEPT_AFTER_DAYS = 75


def kit_outcome(kit, today=None):
    """kept, sold, processed, lost or growing (no outcome yet) for one kit rabbit."""
    from django.utils import timezone

    today = today or timezone.localdate()
    if kit.status == Rabbit.Status.SOLD:
        return "sold"
    if kit.status == Rabbit.Status.CULLED:
        return "processed"
    if kit.status == Rabbit.Status.DECEASED:
        return "lost"
    if kit.status == Rabbit.Status.BREEDING and kit.birth_date and (today - kit.birth_date).days >= KEPT_AFTER_DAYS:
        return "kept"
    return "growing"


def counts(litter, kits):
    """Outcome counts. Kits lost before they became rabbits (born dead, lost
    since birth) count as lost; survivors never entered count as nothing."""
    c = dict.fromkeys(KINDS, 0)
    c["growing"] = 0
    for kit in kits:
        c[kit_outcome(kit)] += 1
    c["lost"] += (litter.died_after or 0)
    return c


def is_past(litter, kits, today):
    if litter.kindled_on is None:
        return False
    if (today - litter.kindled_on).days >= PAST_AFTER_DAYS:
        return True
    c = counts(litter, kits)
    return bool(kits) and c["growing"] == 0 and len(kits) >= (litter.survivors or 0)


def done_on(litter, kits):
    days = [k.sold_on or k.death_date for k in kits if kit_outcome(k) in ("sold", "processed", "lost")]
    days = [d for d in days if d]
    return max(days) if days else (litter.kindled_on + timedelta(days=PAST_AFTER_DAYS) if litter.kindled_on else None)


def live_grams(kit):
    """The last weight on or before the day it left (sold or processed)."""
    end = kit.sold_on or kit.death_date
    ws = [w for w in kit.weights.all() if end is None or w.date <= end]
    return max(ws, key=lambda w: (w.date, w.pk)).grams if ws else None


def summary_text(c):
    parts = [f"{c[k]} {k}" for k in ("kept", "sold", "processed", "lost", "growing") if c[k]]
    return " · ".join(p.replace("growing", "growing out") for p in parts) or "No kits recorded"


def bar(c):
    total = sum(c[k] for k in KINDS)
    return [{"kind": k, "pct": round(100 * c[k] / total, 2)} for k in KINDS if c[k]] if total else []


def past_row(litter, kits, unit):
    c = counts(litter, kits)
    proc = [g for g in (live_grams(k) for k in kits if kit_outcome(k) == "processed") if g]
    return {"litter": litter, "doe": litter.pairing.doe, "buck": litter.pairing.buck,
            "title": f"{litter.pairing.doe.name} × {litter.pairing.buck.name}",
            "born": (litter.born_alive or 0) + (litter.born_dead or 0), "raised": litter.survivors if litter.survivors is not None else len(kits),
            "summary": summary_text(c), "bar": bar(c),
            "growout": weight_text(sum(proc) // len(proc), unit) if proc else ""}


def outcome(litter, kits, unit, today):
    """Everything the Outcome section shows, or None before kindling."""
    if litter.kindled_on is None:
        return None
    c = counts(litter, kits)
    rows, live, dressed, ages = [], [], [], []
    sold_total = Decimal(0)
    for kit in sorted(kits, key=lambda k: (KINDS.index(kit_outcome(k)) if kit_outcome(k) in KINDS else 9, k.name)):
        kind = kit_outcome(kit)
        lg = live_grams(kit) if kind in ("sold", "processed") else None
        dg = kit.dressed_grams if kind == "processed" else None
        end = kit.sold_on or kit.death_date
        days = (end - litter.kindled_on).days if end and kind in ("sold", "processed") else None
        if kind == "processed":
            if lg:
                live.append(lg)
            if dg:
                dressed.append(dg)
            if lg and dg:
                ages.append(days)
        if kind == "sold" and kit.sale_price:
            sold_total += kit.sale_price
        label = {"kept": "Kept as breeder", "sold": "Sold" + (f" · ${kit.sale_price:,.0f}" if kit.sale_price else ""),
                 "processed": "Processed", "lost": "Lost", "growing": "Growing out"}[kind]
        rows.append({"kit": kit, "kind": kind, "label": label,
                     "live": weight_text(lg, unit) if lg else "", "dressed": weight_text(dg, unit) if dg else "",
                     "pct": f"{round(100 * dg / lg)}%" if lg and dg else "", "days": days})
    pairs = [(live_grams(k), k.dressed_grams) for k in kits if kit_outcome(k) == "processed" and k.dressed_grams and live_grams(k)]
    dress_pct = round(100 * sum(d for _, d in pairs) / sum(l for l, _ in pairs)) if pairs else None
    cost = sum((e.amount for e in litter.expenses.all()), Decimal(0))
    dressed_lb = Decimal(sum(dressed)) / (GRAMS_PER_OUNCE * 16) if dressed else None
    total = (litter.born_alive or 0) + (litter.born_dead or 0)
    lost_note = []
    if litter.born_dead:
        lost_note.append(f"{litter.born_dead} stillborn")
    if litter.died_after:
        lost_note.append(f"{litter.died_after} lost after birth")
    return {
        "counts": c, "bar": bar(c), "rows": rows,
        "raised": litter.survivors if litter.survivors is not None else len(kits), "total": total or len(kits),
        "lost_note": ", ".join(lost_note) or "None lost",
        "split": f"{c['kept']} · {c['sold']} · {c['processed']}",
        "sold_note": f"Sold ${sold_total:,.0f}" if sold_total else "None sold",
        "avg_live": weight_text(sum(live) // len(live), unit) if live else "",
        "dress_pct": f"{dress_pct}%" if dress_pct is not None else "",
        "avg_dressed": weight_text(sum(dressed) // len(dressed), unit) if dressed else "",
        "feed_per_lb": f"${cost / dressed_lb:,.2f}/lb" if cost and dressed_lb else "",
        "cost_note": f"${cost:,.2f} logged" if cost else "No costs linked",
        "days": round(sum(ages) / len(ages)) if ages else None,
    }


def timeline(litter, kits):
    """Dated notes, newest first: the keeper's own notes plus what the records say."""
    items = [{"date": n.date, "text": n.text, "own": True} for n in litter.dated_notes.all()]
    if litter.kindled_on:
        born = (litter.born_alive or 0) + (litter.born_dead or 0)
        items.append({"date": litter.kindled_on, "text": f"Kindled {born}." + (f" {litter.notes}" if litter.notes else "") if born else "Kindled."})
    groups = {}
    for kit in kits:
        kind = kit_outcome(kit)
        day = kit.sold_on if kind == "sold" else kit.death_date if kind in ("processed", "lost") else None
        if day:
            groups.setdefault((day, kind), []).append(kit)
    for (day, kind), group in groups.items():
        names = ", ".join(k.name for k in group)
        if kind == "sold":
            for k in group:
                who = f" to {k.sold_to.name}" if k.sold_to_id else ""
                price = f" for ${k.sale_price:,.0f}" if k.sale_price else ""
                items.append({"date": day, "text": f"{k.name} sold{who}{price}."})
        elif kind == "processed":
            items.append({"date": day, "text": f"Processed {names}."})
        else:
            items.append({"date": day, "text": f"Lost {names}."})
    items.sort(key=lambda i: i["date"], reverse=True)
    return items
