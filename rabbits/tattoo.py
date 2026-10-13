"""The next ear tattoo in a keeper's format, such as {prefix}{yy}{nn}:
BH2603 after BH2602. {n}, {nn} and {nnn} are the next number, padded to
1, 2 or 3 digits, counted from the highest tattoo already in the herd
that fits the format."""

import re

from django.utils import timezone

from .models import Rabbit, prefs

NUMBER_TOKENS = {"{n}": 1, "{nn}": 2, "{nnn}": 3}


def suggest(user, today=None):
    settings = prefs(user)
    fmt = settings.tattoo_format.strip()
    if not fmt:
        return ""
    today = today or timezone.localdate()
    fixed = {"{prefix}": settings.prefix.strip(), "{yy}": f"{today:%y}", "{year}": f"{today:%Y}"}
    width = next((w for token, w in NUMBER_TOKENS.items() if token in fmt), None)
    if width is None:
        text = fmt
        for token, value in fixed.items():
            text = text.replace(token, value)
        return text[:20]
    token = next(t for t in NUMBER_TOKENS if t in fmt)
    head, _, tail = fmt.partition(token)
    for key, value in fixed.items():
        head, tail = head.replace(key, value), tail.replace(key, value)
    for t in NUMBER_TOKENS:
        tail = tail.replace(t, "")
    pattern = re.compile(rf"^{re.escape(head)}(\d+){re.escape(tail)}$", re.IGNORECASE)
    taken = set(Rabbit.objects.filter(owner=user).exclude(tattoo="").values_list("tattoo", flat=True))
    numbers = [int(match.group(1)) for match in map(pattern.match, taken) if match]
    number = max(numbers, default=0) + 1
    lowered = {t.lower() for t in taken}
    while True:
        candidate = f"{head}{number:0{width}d}{tail}"[:20]
        if candidate.lower() not in lowered:
            return candidate
        number += 1
