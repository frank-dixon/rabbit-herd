"""Purebred detection.

A rabbit counts as purebred when its breed makeup is 100% one breed. The
makeup comes from, in order:
1. what was entered for it (a purebred breed, or crossbred shares),
2. its dam and sire, averaged, when both are known (herd parents use their
   own makeup, worked out the same way; outside parents use the breed
   recorded on the relative row),
3. a plain breed text that exactly names a known breed (older records).
"""

from decimal import Decimal

from .models import Breed, Rabbit

HUNDRED = Decimal(100)
MAX_DEPTH = 4


def _breed_names():
    return {name.casefold(): name for name in Breed.objects.values_list("name", flat=True)}


def _from_text(text, names):
    """{breed: percent} from "Mini Rex" or "Cross: 50% Mini Rex, 50% Dutch"."""
    text = (text or "").strip()
    if not text:
        return None
    if text.casefold().startswith("cross:"):
        makeup = {}
        for part in text[len("cross:"):].split(","):
            percent, _, name = part.strip().partition("% ")
            canonical = names.get(name.strip().casefold())
            try:
                value = Decimal(percent)
            except Exception:
                return None
            if not canonical:
                return None
            makeup[canonical] = makeup.get(canonical, 0) + value
        return makeup or None
    canonical = names.get(text.casefold())
    return {canonical: HUNDRED} if canonical else None


def _parents(rabbit):
    rows = {row.relationship: row for row in rabbit.relatives.all() if row.relationship in ("dam", "sire")}
    return rows.get("dam"), rows.get("sire")


def makeup(rabbit, names=None, depth=0):
    """(makeup dict, source) where source is "entered", "parents" or "text"; (None, "") when unknown."""
    names = names if names is not None else _breed_names()
    if rabbit.breed_type == Rabbit.BreedType.PUREBRED and rabbit.purebred_id:
        return {rabbit.purebred.name: HUNDRED}, "entered"
    if rabbit.breed_type == Rabbit.BreedType.CROSSBRED:
        shares = {share.breed.name: share.percent for share in rabbit.breed_shares.all()}
        if shares:
            return shares, "entered"
    if depth < MAX_DEPTH:
        parent_makeups = []
        for row in _parents(rabbit):
            if row is None:
                break
            if row.herd_rabbit_id:
                found, _ = makeup(row.herd_rabbit, names, depth + 1)
            else:
                found = _from_text(row.breed, names)
            if not found:
                break
            parent_makeups.append(found)
        if len(parent_makeups) == 2:
            combined = {}
            for parent in parent_makeups:
                for name, percent in parent.items():
                    combined[name] = combined.get(name, 0) + Decimal(percent) / 2
            return combined, "parents"
    found = _from_text(rabbit.breed, names)
    return (found, "text") if found else (None, "")


def purebred(rabbit, names=None):
    """{"breed": name, "source": ...} when 100% one breed, else None."""
    found, source = makeup(rabbit, names)
    if found and len(found) == 1:
        (name, percent), = found.items()
        if Decimal(percent) == HUNDRED:
            return {"breed": name, "source": source}
    return None


def mark(rabbits):
    """Set .purebred_info on each rabbit (None when not purebred)."""
    names = _breed_names()
    for rabbit in rabbits:
        rabbit.purebred_info = purebred(rabbit, names)
    return rabbits


PREFETCH = ("purebred", "breed_shares__breed", "relatives__herd_rabbit__purebred",
            "relatives__herd_rabbit__breed_shares__breed", "relatives__herd_rabbit__relatives__herd_rabbit")
