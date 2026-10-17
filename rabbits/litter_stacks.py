"""Stacked litter cards on the Rabbits list (Active tab).

Growing-out rabbits from one litter (the litter link, or the same dam, sire
and birth date from their Relative rows) collapse into one entry. A litter
with a single growing-out rabbit left stays a normal card. Two queries at
most, whatever the herd size.
"""
from .models import Rabbit, Relative


class LitterStack:
    kind = "stack"

    def __init__(self, key, kits, dam, sire):
        self.key, self.kits, self.dam, self.sire = key, kits, dam, sire

    @property
    def count(self):
        return len(self.kits)

    @property
    def dam_name(self):
        return getattr(self.dam, "name", "") or "Unknown dam"

    @property
    def sire_name(self):
        return getattr(self.sire, "name", "") or "Unknown sire"

    @property
    def title(self):
        return f"{self.dam_name} × {self.sire_name}"

    @property
    def age_text(self):
        return self.kits[0].age_text()

    @property
    def color_text(self):
        colors = {k.color for k in self.kits if k.color}
        return colors.pop() if len(colors) == 1 else ""

    @property
    def parents(self):
        return [p for p in (self.dam, self.sire) if p is not None]

    @property
    def dam_is_herd(self):
        return isinstance(self.dam, Rabbit)

    @property
    def sire_is_herd(self):
        return isinstance(self.sire, Rabbit)


def _parents_from_relatives(rabbits):
    rows = (Relative.objects.filter(rabbit_id__in=[r.pk for r in rabbits], relationship__in=["dam", "sire"])
            .select_related("herd_rabbit", "outside").prefetch_related("herd_rabbit__photos"))
    found = {}
    for row in rows:
        found.setdefault(row.rabbit_id, {}).setdefault(row.relationship, row.other)
    return found


def _ident(obj):
    if obj is None:
        return None
    return (type(obj).__name__, obj.pk)


def stack_litters(rabbits):
    """The list's entries: rabbits, with each litter's growing-out kits folded
    into one LitterStack placed where its first kit sorted."""
    growing = [r for r in rabbits if r.status == Rabbit.Status.GROWING]
    if len(growing) < 2:
        return list(rabbits)
    unlinked = [r for r in growing if not r.litter_id]
    rel = _parents_from_relatives(unlinked) if unlinked else {}
    groups, parents = {}, {}
    for r in growing:
        if r.litter_id and r.litter.pairing_id:
            key = f"l{r.litter_id}"
            parents.setdefault(key, (r.litter.pairing.doe, r.litter.pairing.buck))
        else:
            p = rel.get(r.pk, {})
            dam, sire = p.get("dam"), p.get("sire")
            if dam is None or sire is None or not r.birth_date:
                continue
            d, s = _ident(dam), _ident(sire)
            key = f"p{d[0][0]}{d[1]}-{s[0][0]}{s[1]}-{r.birth_date:%Y%m%d}"
            parents.setdefault(key, (dam, sire))
        groups.setdefault(key, []).append(r)
    in_stack = {}
    for key, kits in groups.items():
        if len(kits) > 1:
            stack = LitterStack(key, kits, *parents[key])
            for k in kits:
                in_stack[k.pk] = stack
    out, placed = [], set()
    for r in rabbits:
        stack = in_stack.get(r.pk)
        if stack is None:
            out.append(r)
        elif stack.key not in placed:
            placed.add(stack.key)
            out.append(stack)
    return out
