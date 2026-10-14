"""One sortable-table helper for every table in the app.

The sort lives in the URL as ?sort=key (ascending) or ?sort=-key (descending),
so a header link, a Filter-panel <select name="sort"> and Back/Forward all agree.
Header links only change the query string, so list-swap.mjs swaps them in
without a reload. Unknown values (None) always sort last, in either direction.
Render headers with components/sort_th.html."""

from urllib.parse import urlencode


def parse(value, keys, default="", desc_first=(), legacy=None):
    """(key, desc) from a ?sort= value. legacy maps old values like "oldest"."""
    value = (legacy or {}).get(value, value) or ""
    key = value.lstrip("-")
    if key not in keys:
        key = default.lstrip("-")
        return key, default.startswith("-") if key else False
    return key, value.startswith("-")


def token(key, desc):
    return f"-{key}" if desc else key


def headers(columns, key, desc, params, desc_first=(), param="sort"):
    """Header cells: [{key, label, on, desc, href, aria, next}]. columns is
    [(key, label)]; a click on the active column flips it, a new column starts
    descending if it is in desc_first."""
    out = []
    for k, label in columns:
        on = k == key
        nxt = (not desc) if on else k in desc_first
        q = {**params, param: token(k, nxt)}
        out.append({
            "key": k, "label": label, "on": on, "desc": desc if on else None,
            "aria": ("descending" if desc else "ascending") if on else "none",
            "href": "?" + urlencode({a: b for a, b in q.items() if b not in ("", None)}),
            "next": "descending" if nxt else "ascending",
        })
    return out


def apply(items, funcs, key, desc):
    """Sort items by funcs[key](item); None values go last either way. Stable."""
    if key not in funcs:
        return list(items)
    f = funcs[key]
    known = [x for x in items if f(x) is not None]
    known.sort(key=f, reverse=desc)
    return known + [x for x in items if f(x) is None]
