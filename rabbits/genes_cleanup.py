"""Which stored genetics rows are computable copies, and removing them reversibly.

Only rows that nobody typed are ever considered: the seeded demo account and
sample content (is_sample). Of those:

- Gene: probable rows with no note whose genotype is exactly what the rabbit's
  breed, color and eye color prove, on rabbits where every proven locus has a
  stored row. The rabbit gets genes_implied=True and reads the same value back
  from rabbits.derived.genes_of. Known rows, rows with a note and every other
  owner's rows are never touched.
- PedigreeEntry: grandparent and older rows whose first step is a herd rabbit
  that already names the same ancestor at the rest of the path, so walking
  dam and sire up the herd (pedigree.build_tree) gives it back unchanged.

The parity tool (manage.py genetics_parity) applies a plan inside a rolled-back
transaction and compares every genetics output before and after.
"""

import json

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

DEMO_EMAIL = "demo@bramble-burrow.app"


def scope_q(prefix="", owner_ids=None):
    """Rabbits whose rows were written by the app, not typed by a keeper: the
    seeded demo account and sample content. owner_ids narrows it further."""
    demo = get_user_model().objects.filter(email__iexact=DEMO_EMAIL).values_list("pk", flat=True)
    q = Q(**{f"{prefix}owner_id__in": list(demo)}) | Q(**{f"{prefix}is_sample": True})
    if owner_ids is not None:
        q &= Q(**{f"{prefix}owner_id__in": list(owner_ids)})
    return q


def plan(owner_ids=None):
    """{"genes": [gene ids], "flag": [rabbit ids], "pedigree": [entry ids]}."""
    from . import derived
    from .models import Gene, PedigreeEntry, Rabbit
    from .pedigree import build_tree

    gene_ids, flag = [], []
    rabbits = Rabbit.all_objects.filter(scope_q(owner_ids=owner_ids)).prefetch_related("genes")
    for rabbit in rabbits:
        implied = {g.locus: g.genotype for g in derived.implied_genes(rabbit)}
        if not implied:
            continue
        stored = {g.locus: g for g in rabbit.genes.all()}
        if any(locus not in stored for locus in implied):
            continue  # flagging would add a gene the rabbit does not show today
        drop = [g.pk for locus, g in stored.items() if locus in implied and g.genotype == implied[locus]
                and g.certainty == Gene.Certainty.PROBABLE and not g.note]
        if drop:
            gene_ids += drop
            flag.append(rabbit.pk)

    entry_ids = []
    trees = {}

    def tree_of(rabbit):
        if rabbit.pk not in trees:
            trees[rabbit.pk] = {p: c["rabbit"] for p, c in build_tree(rabbit).items()}
        return trees[rabbit.pk]

    entries = (PedigreeEntry.objects.filter(scope_q("rabbit__", owner_ids)).select_related("herd_rabbit", "outside", "rabbit"))
    by_rabbit = {}
    for e in entries:
        by_rabbit.setdefault(e.rabbit_id, []).append(e)
    for rabbit_id, rows in by_rabbit.items():
        tree = tree_of(rows[0].rabbit)
        for e in rows:
            if len(e.position) < 2:
                continue
            parent = tree.get(e.position[0])
            if not isinstance(parent, Rabbit) or parent.deleted_at:
                continue
            up = tree_of(parent).get(e.position[1:])
            if up is not None and type(up) is type(e.ancestor) and up.pk == e.ancestor.pk:
                entry_ids.append(e.pk)
    return {"genes": sorted(gene_ids), "flag": sorted(flag), "pedigree": sorted(entry_ids)}


def backup(p):
    """A JSON-ready copy of every row the plan removes, for restore()."""
    from .models import Gene, PedigreeEntry

    return {
        "genes": list(Gene.objects.filter(pk__in=p["genes"]).values()),
        "pedigree": list(PedigreeEntry.objects.filter(pk__in=p["pedigree"]).values()),
        "flag": p["flag"],
    }


def apply(p):
    """Remove the rows and set the flags. History is not logged: nothing the keeper sees changes."""
    from .history import quiet
    from .models import Gene, PedigreeEntry, Rabbit

    with transaction.atomic(), quiet():
        genes = Gene.objects.filter(pk__in=p["genes"]).delete()[0]
        pedigree = PedigreeEntry.objects.filter(pk__in=p["pedigree"]).delete()[0]
        flagged = Rabbit.all_objects.filter(pk__in=p["flag"]).update(genes_implied=True)
    return {"genes": genes, "pedigree": pedigree, "flagged": flagged}


def restore(data):
    """Put a backup back exactly (same ids) and clear the flags it set."""
    from .history import quiet
    from .models import Gene, PedigreeEntry, Rabbit

    with transaction.atomic(), quiet():
        Rabbit.all_objects.filter(pk__in=data["flag"]).update(genes_implied=False)
        Gene.objects.bulk_create([Gene(**row) for row in data["genes"]], ignore_conflicts=True)
        PedigreeEntry.objects.bulk_create([PedigreeEntry(**row) for row in data["pedigree"]], ignore_conflicts=True)
    return {"genes": len(data["genes"]), "pedigree": len(data["pedigree"]), "unflagged": len(data["flag"])}


def dumps(data):
    return json.dumps(data, default=str, indent=1)
