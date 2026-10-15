"""Compare every genetics output before and after the genes cleanup.

Reads everything with GENETICS_READ="old" on the database as it is ("new" if
it was already cleaned), then,
inside a transaction that is always rolled back, applies the cleanup plan,
reads everything again with GENETICS_READ="new", and compares. Nothing is
written. Exit status 1 when anything differs.

    python manage.py genetics_parity            # whole database
    python manage.py genetics_parity --owner a@b.c
"""

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test.utils import override_settings


class Rollback(Exception):
    pass


def clean(value):
    """Plain, comparable JSON: model objects become (model, pk), sets become sorted lists."""
    from django.db.models import Model

    if isinstance(value, Model):
        return [value._meta.label_lower, value.pk]
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((clean(v) for v in value), key=repr)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def snapshot(owner_ids):
    """{area: {item: output}} for every rabbit, pairing and program in scope."""
    from rabbits import color_odds, family_tree, gene_card, genetics, pairings, pedigree, program_plan
    from rabbits import derived
    from rabbits.models import Pairing, Program, Rabbit

    cache.clear()
    out = {k: {} for k in ("gene_card", "gene_thread", "pedigree", "family_tree", "pairing", "program", "genes")}
    rabbits = Rabbit.all_objects.filter(owner_id__in=owner_ids).select_related("owner", "purebred").order_by("pk")
    for r in rabbits:
        key = str(r.pk)
        out["genes"][key] = derived.gene_key(derived.genes_of(r))
        card = gene_card.rows(r)
        out["gene_card"][key] = clean([card, gene_card.summary(card)])
        out["gene_thread"][key] = clean({
            "c_carrier": genetics.c_carrier_suggestion(r),
            "recorded": color_odds.recorded(r),
            "hidden": genetics.hidden_notes(color_odds.recorded(r)),
            "parents": genetics.parent_pairs(r),
            "carrier_odds": genetics.carrier_odds(r),
            "test_mates": genetics.test_mates(r),
            "planning": program_plan.planning_genes(r),
        })
        tree = pedigree.build_tree(r)
        out["pedigree"][key] = clean({p: {k: v for k, v in c.items() if k != "rabbit"} | {"who": c["rabbit"]}
                                      for p, c in sorted(tree.items())})
        if not r.deleted_at:
            out["family_tree"][key] = clean(family_tree.payload(r))
        out["pedigree"][key + ":ancestors"] = clean(sorted(pairings.ancestors(r).items(), key=repr))
    for p in Pairing.objects.filter(owner_id__in=owner_ids).select_related("doe", "buck").order_by("pk"):
        out["pairing"][str(p.pk)] = clean({
            "predict": color_odds.predict(p.doe, p.buck),
            "inbreeding": pairings.inbreeding_warnings(p.doe, p.buck),
            "notes": genetics.pairing_notes(p.doe.name, color_odds.recorded(p.doe), p.buck.name, color_odds.recorded(p.buck)),
        })
    for uid in owner_ids:
        user = get_user_model().objects.get(pk=uid)
        out["program"][f"user{uid}:unknown"] = program_plan.unknown_gene_count(user)
        out["program"][f"user{uid}:ped"] = clean(sorted(program_plan.pedigree(user).parents.items(), key=repr))
    for prog in Program.objects.filter(owner_id__in=owner_ids).order_by("pk"):
        out["program"][str(prog.pk)] = clean(program_plan.build(prog))
    return out


def first_diff(x, y, path=""):
    """The first path where two cleaned values differ, with both sides."""
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            if k not in x or k not in y:
                return f"{path}/{k}", x.get(k, "<missing>"), y.get(k, "<missing>")
            found = first_diff(x[k], y[k], f"{path}/{k}")
            if found:
                return found
        return None
    if isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
        for i, (a, b) in enumerate(zip(x, y)):
            found = first_diff(a, b, f"{path}[{i}]")
            if found:
                return found
        return None
    return None if x == y else (path, x, y)


def compare(a, b, limit):
    diffs = []
    for area in a:
        for item in sorted(set(a[area]) | set(b[area])):
            x, y = a[area].get(item), b[area].get(item)
            if json.dumps(x, sort_keys=True, default=str) != json.dumps(y, sort_keys=True, default=str):
                diffs.append((area, item, x, y))
    return diffs


class Command(BaseCommand):
    help = "Prove the genes cleanup changes no genetics output (read-only; always rolls back)."

    def add_arguments(self, parser):
        parser.add_argument("--owner", action="append", default=[], help="Only this account's email (repeatable).")
        parser.add_argument("--show", type=int, default=10, help="Mismatches to print in full.")
        parser.add_argument("--dump", help="Also save the baseline outputs as JSON (to compare two databases).")

    def handle(self, *args, **opts):
        from rabbits import genes_cleanup
        from rabbits.models import Rabbit

        users = get_user_model().objects.all()
        if opts["owner"]:
            users = users.filter(email__in=opts["owner"])
            if not users.exists():
                raise CommandError("No such account.")
        owner_ids = sorted(set(Rabbit.all_objects.filter(owner__in=users).values_list("owner_id", flat=True)))

        # Before any cleanup nothing is flagged and "old" (stored rows only) is the
        # baseline. A database already cleaned (or seeded by the new seed_demo)
        # has flagged rabbits, so its baseline is "new" as it is served today.
        baseline = "new" if Rabbit.all_objects.filter(genes_implied=True).exists() else "old"
        with override_settings(GENETICS_READ=baseline):
            before = snapshot(owner_ids)
        if opts.get("dump"):
            with open(opts["dump"], "w") as fh:
                json.dump(before, fh, sort_keys=True, default=str)
        p = genes_cleanup.plan()
        result = {}
        try:
            with transaction.atomic():
                result = genes_cleanup.apply(p)
                with override_settings(GENETICS_READ="new"):
                    after = snapshot(owner_ids)
                raise Rollback
        except Rollback:
            pass
        cache.clear()

        checked = {area: len(items) for area, items in before.items()}
        diffs = compare(before, after, opts["show"])
        self.stdout.write(f"Baseline reads: {baseline}. Accounts: {len(owner_ids)}. Checked: " + ", ".join(f"{k} {v}" for k, v in checked.items()))
        self.stdout.write(f"Cleanup plan (rolled back): {result.get('genes', 0)} gene rows, "
                          f"{result.get('pedigree', 0)} pedigree rows, {result.get('flagged', 0)} rabbits flagged.")
        by_area = {}
        for area, *_ in diffs:
            by_area[area] = by_area.get(area, 0) + 1
        for area, item, x, y in diffs[: opts["show"]]:
            where, old, new = first_diff(x, y) or ("", x, y)
            self.stdout.write(f"MISMATCH {area} {item} at {where}\n  old: {json.dumps(old, default=str)[:400]}\n  new: {json.dumps(new, default=str)[:400]}")
        if by_area:
            self.stdout.write("Mismatches by area: " + ", ".join(f"{k} {v}" for k, v in sorted(by_area.items())))
        self.stdout.write(f"Mismatches: {len(diffs)}")
        if diffs:
            raise SystemExit(1)
