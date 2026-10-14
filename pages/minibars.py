"""Mini column charts for stat cards (components/stat_card.html, bars=...): 8-10
periods of real history, zero-based, the current period last and highlighted."""

import datetime


def months(today, n=10):
    """(start, end, label) for the last n calendar months, oldest first, this month last."""
    out, y, m = [], today.year, today.month
    for _ in range(n):
        start = datetime.date(y, m, 1)
        end = (datetime.date(y + (m == 12), m % 12 + 1, 1) - datetime.timedelta(days=1))
        out.append((start, end, start.strftime("%b")))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out[::-1]


def weeks(today, n=10):
    """(start, end, label) for the last n weeks ending today, oldest first."""
    out = []
    for i in range(n):
        end = today - datetime.timedelta(days=7 * i)
        start = end - datetime.timedelta(days=6)
        out.append((start, end, f"week of {start:%b} {start.day}"))
    return out[::-1]


def bars(periods, values, what, fmt=str):
    """periods: from months()/weeks(); values: one number (or None) per period; what: the
    series name for the summary ("rabbits in the herd, by month")."""
    vals = [v or 0 for v in values]
    top = max(vals) if vals else 0
    if not top:
        return None  # no history to draw
    items = [{"h": max(round(100 * v / top), 4 if v else 2), "now": i == len(vals) - 1, "title": f"{p[2]}: {fmt(v)}"}
             for i, (p, v) in enumerate(zip(periods, vals))]
    summary = f"{what.capitalize()}, last {len(vals)}: " + ", ".join(i["title"] for i in items)
    return {"items": items, "summary": summary}
