"""A 4-generation pedigree: the rabbit, its parents, grandparents and
great-grandparents. Each position comes from the closest record that names
it exactly: the rabbit's own pedigree entries, then dam and sire relatives,
then the same records on a herd ancestor further up."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import PEDIGREE_GENERATIONS, PedigreeEntry, Rabbit, Relative, position_label


def known_parents(rabbit_id):
    """{"s"/"d": (herd rabbit or outside rabbit, relative row or None)} from one rabbit's records."""
    found = {}
    for entry in PedigreeEntry.objects.filter(rabbit_id=rabbit_id).select_related("herd_rabbit", "outside"):
        found[entry.position] = (entry.ancestor, None)
    for row in Relative.objects.filter(rabbit_id=rabbit_id, relationship__in=["dam", "sire"]).select_related("herd_rabbit", "outside"):
        found.setdefault("d" if row.relationship == "dam" else "s", (row.other, row))
    return found


def build_tree(rabbit, generations=PEDIGREE_GENERATIONS):
    """{position: cell} for every position up to the given generation."""
    tree = {}
    queue = [("", rabbit)]
    while queue:
        base, subject = queue.pop(0)
        for path, (other, row) in known_parents(subject.pk).items():
            position = base + path
            if len(position) > generations or position in tree:
                continue
            tree[position] = cell(position, other, row)
            if isinstance(other, Rabbit) and len(position) < generations:
                queue.append((position, other))
    return tree


def cell(position, other, row):
    herd = isinstance(other, Rabbit) and not other.deleted_at  # a deleted rabbit shows, unlinked
    color = (other.color if herd else "") or (row.color if row else "")
    breed = (other.short_breed if herd else "") or (row.breed if row else "") or ("" if herd else other.details)
    return {
        "position": position, "label": position_label(position), "name": other.name, "herd": herd,
        "rabbit": other, "avatar": {1: "lg", 2: "md"}.get(len(position), "sm"),
        "pk": other.pk if herd else None, "tattoo": other.tattoo if herd else "",
        "breed": breed, "color": color, "line": (other.line if herd else "") or (row.line if row else ""),
        "born": other.birth_date if herd else None,
    }


def generations(tree, depth=PEDIGREE_GENERATIONS):
    """Positions per generation, sire's side first: [["s","d"], ["ss","sd","ds","dd"], ...]."""
    rows, current = [], [""]
    for _ in range(depth):
        current = [path + step for path in current for step in "sd"]
        rows.append([{"position": p, "label": position_label(p), "cell": tree.get(p),
                      "sex": "Buck" if p.endswith("s") else "Doe"} for p in current])
    return rows


@login_required
def rabbit_pedigree(request, pk):
    rabbit = get_object_or_404(Rabbit.objects.select_related("purebred"), owner=request.user, pk=pk)
    tree = build_tree(rabbit)
    gens = generations(tree)
    for span, slots in zip([4, 2, 1], gens):
        for index, slot in enumerate(slots):
            slot["row"] = index * span + 1
    from .models import prefs

    return render(request, "rabbits/pedigree.html", {
        "herd_prefs": prefs(request.user),
        "rabbit": rabbit, "generations": gens, "known": len(tree), "wide": True,
        "titles": ["Parents", "Grandparents", "Great-grandparents"],
        "columns": list(zip(["Parents", "Grandparents", "Great-grandparents"], gens, [4, 2, 1])),
    })
