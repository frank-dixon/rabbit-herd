"""Shared pieces for index pages that offer Grid and List (Programs, Pairings,
Shows, Health). Pages hand the shared components a list of plain item dicts;
the same item feeds both the card (components/item_grid.html) and the row
(components/item_rows.html), so no page carries its own markup.

An item: href, title, sub, thumbs (rabbits), swatch (CSS background), pill
{label, tone}, kv [{label, value, big}], text, chips_label, chips [{swatch,
label, note}], progress {label, right, segs [0..1], dots}, foot {pill, text,
tone}, action {url, label}, dim, mobile (one line under the title on phones),
cells [{kind, ...}] for the list row, kinds: lead, text, pill, progress,
chips, thumbs, num.
"""

VIEWS = ("grid", "list")


def index_view(request, page, default):
    """Grid or List for one index page. ?view= sets it and the account
    remembers it per page, the same way the Rabbits page remembers its view."""
    user = request.user
    saved = dict(user.ui_views or {})
    asked = request.GET.get("view")
    if asked in VIEWS and saved.get(page) != asked:
        saved[page] = asked
        user.ui_views = saved
        user.save(update_fields=["ui_views"])
    view = saved.get(page) if saved.get(page) in VIEWS else default
    return view


def view_options(request, view):
    """Options for the shared Grid/List segmented control, keeping other query args."""
    out = []
    for key, label in (("grid", "Grid"), ("list", "List")):
        q = request.GET.copy()
        q["view"] = key
        out.append({"href": f"?{q.urlencode()}", "label": label, "selected": key == view, "icon": key})
    return out


def tabs(request, current, choices):
    """Underline tabs [{href, label, count, on}] for ?tab=, keeping the view."""
    out = []
    for key, label, count in choices:
        q = request.GET.copy()
        q["tab"] = key
        out.append({"href": f"?{q.urlencode()}", "label": label, "count": count, "on": key == current})
    return out


def stat(label, value, note="", tone=""):
    return {"label": label, "value": value, "note": note, "tone": tone}


def ordinal(n):
    if n is None:
        return ""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def place_tone(n):
    return {1: "y", 2: "b"}.get(n, "")
