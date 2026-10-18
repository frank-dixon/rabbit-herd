"""Whole-herd operations on one account's records: copying a herd into another
account (the demo herd), moving a guest's herd into a real account (merge on
sign-in), and asking whether an account holds any records at all.

Every model that belongs to an account is listed in HERD_MODELS, in an order
where each row's required parents come first. A test fails when a model with
an owner (or a parent chain to one) is missing, so a new model can't be
silently left behind by a merge or a demo copy."""

import datetime

from django.apps import apps
from django.db import transaction

# (model, path from the row to its owning user). Order matters for copying:
# required foreign keys always point at an earlier model. Nullable ones that
# point forward (Rabbit.litter, Task.next_occurrence, Program.sire_outside...)
# are filled in a second pass.
HERD_MODELS = (
    ("BreedingSchedule", "owner"),
    ("Location", "owner"),
    ("Contact", "owner"),
    ("OutsideRabbit", "owner"),
    ("Rabbit", "owner"),
    ("BreedShare", "rabbit__owner"),
    ("Weight", "rabbit__owner"),
    ("Relative", "rabbit__owner"),
    ("PedigreeEntry", "rabbit__owner"),
    ("Gene", None),  # on a rabbit or on a relative; see rows()
    ("Pairing", "owner"),
    ("Litter", "owner"),
    ("Task", "owner"),
    ("HealthNote", "rabbit__owner"),
    ("RabbitPhoto", "rabbit__owner"),
    ("LitterKit", "litter__owner"),
    ("LitterNote", "litter__owner"),
    ("LitterCheck", "litter__owner"),
    ("KitCheck", "litter_check__litter__owner"),
    ("CullNote", "rabbit__owner"),
    ("Cover", "litter__owner"),
    ("ShowEntry", "rabbit__owner"),
    ("Expense", "owner"),
    ("WaitlistEntry", "owner"),
    ("HistoryEntry", "rabbit__owner"),
    ("Program", "owner"),
    ("ProgramBreeder", "program__owner"),
    ("HerdSettings", "user"),
    ("SyncOp", "owner"),
)
# Rows that belong to an account but aren't herd records: never copied into a demo.
NOT_COPIED = {"SyncOp"}
# Shared reference data, pointed at as-is.
SHARED = {"rabbits.breed"}


def model(name):
    return apps.get_model("rabbits", name)


def rows(name, user):
    """Every row of one model that belongs to user, including soft-deleted rabbits and samples."""
    from django.db.models import Q

    m = model(name)
    manager = m._base_manager
    if name == "Gene":
        return manager.filter(Q(rabbit__owner=user) | Q(relative__rabbit__owner=user))
    path = dict(HERD_MODELS)[name]
    return manager.filter(**{path: user})


def has_herd_data(user, *, ignore_samples=True):
    """Whether the account holds anything worth keeping (sample records don't count)."""
    for name in ("Rabbit", "Location", "Contact", "OutsideRabbit", "Pairing", "Litter", "Task",
                 "Expense", "WaitlistEntry", "Program", "BreedingSchedule"):
        qs = rows(name, user)
        if ignore_samples and any(f.name == "is_sample" for f in model(name)._meta.fields):
            qs = qs.filter(is_sample=False)
        if qs.exists():
            return True
    return False


def _shifted(value, days):
    if value is None or not days:
        return value
    return value + datetime.timedelta(days=days)


@transaction.atomic
def clone_herd(source, target, *, shift_days=0):
    """Copy every herd record of source into target, remapping links between them
    and moving every date by shift_days. Photo files are shared, not copied: the
    copies point at the same stored names (accounts.demo protects those files)."""
    User = source.__class__
    mapping = {}  # model label -> {old pk: new pk}
    later = []  # (model, new pk, field name, related label, old related pk)
    for name, _path in HERD_MODELS:
        if name in NOT_COPIED:
            continue
        m = model(name)
        label = m._meta.label_lower
        mapping[label] = {}
        old_rows = list(rows(name, source).order_by("pk"))
        if not old_rows:
            continue
        fresh = []
        for row in old_rows:
            values = {}
            pending = []
            for field in m._meta.concrete_fields:
                if field.primary_key:
                    continue
                value = getattr(row, field.attname)
                if field.is_relation:
                    related = field.related_model
                    rlabel = related._meta.label_lower
                    if related is User:
                        value = target.pk
                    elif rlabel in SHARED or value is None:
                        pass
                    elif value in mapping.get(rlabel, {}):
                        value = mapping[rlabel][value]
                    elif field.null:
                        pending.append((field.name, rlabel, value))
                        value = None
                    else:
                        raise ValueError(f"{label}.{field.name} points at a row outside the herd")
                elif field.get_internal_type() in ("DateField", "DateTimeField"):
                    value = _shifted(value, shift_days)
                values[field.attname] = value
            obj = m(**values)
            fresh.append((row.pk, obj, pending))
        created = m._base_manager.bulk_create([obj for _, obj, _ in fresh])
        for (old_pk, _, pending), obj in zip(fresh, created):
            mapping[label][old_pk] = obj.pk
            for field_name, rlabel, old in pending:
                later.append((m, obj.pk, field_name, rlabel, old))
    # Second pass, batched per model: the forward links (a rabbit's birth litter, a task's next one).
    grouped = {}
    for m, pk, field_name, rlabel, old in later:
        new = mapping.get(rlabel, {}).get(old)
        if new is not None:
            grouped.setdefault(m, {}).setdefault(pk, {})[f"{field_name}_id"] = new
    for m, rows_by_pk in grouped.items():
        fields = sorted({f for values in rows_by_pk.values() for f in values})
        objs = list(m._base_manager.filter(pk__in=rows_by_pk).only("pk", *fields))
        for obj in objs:
            for f, v in rows_by_pk[obj.pk].items():
                setattr(obj, f, v)
        m._base_manager.bulk_update(objs, [f[:-3] for f in fields], batch_size=500)
    return mapping


def _free_name(taken, name, suffix):
    if name.upper() not in taken:
        return name
    n = 1
    while True:
        candidate = f"{name} ({suffix}{'' if n == 1 else ' ' + str(n)})"
        if candidate.upper() not in taken:
            return candidate
        n += 1


@transaction.atomic
def move_herd(source, target):
    """Move every record from source (a guest) to target. Nothing is lost: a
    tattoo, location or schedule name the target already uses gets a
    "(guest)" suffix. The target keeps its own herd settings. Returns the
    number of rabbits moved."""
    from django.db.models.functions import Upper

    Rabbit, Location, Schedule = model("Rabbit"), model("Location"), model("BreedingSchedule")
    taken = set(Rabbit._base_manager.filter(owner=target, deleted_at__isnull=True).exclude(tattoo="")
                .annotate(t=Upper("tattoo")).values_list("t", flat=True))
    for rabbit in Rabbit._base_manager.filter(owner=source, deleted_at__isnull=True).exclude(tattoo=""):
        fresh = _free_name(taken, rabbit.tattoo, "guest")
        if fresh != rabbit.tattoo:
            Rabbit._base_manager.filter(pk=rabbit.pk).update(tattoo=fresh[:Rabbit._meta.get_field("tattoo").max_length])
        taken.add(fresh.upper())
    for m in (Location, Schedule):
        names = {n.upper() for n in m._base_manager.filter(owner=target).values_list("name", flat=True)}
        for row in m._base_manager.filter(owner=source):
            fresh = _free_name(names, row.name, "guest")
            if fresh != row.name:
                m._base_manager.filter(pk=row.pk).update(name=fresh[:m._meta.get_field("name").max_length])
            names.add(fresh.upper())
    moved = Rabbit._base_manager.filter(owner=source).count()
    for name, path in HERD_MODELS:
        if path in ("owner", "user"):
            if name == "HerdSettings":
                if model(name)._base_manager.filter(user=target).exists():
                    model(name)._base_manager.filter(user=source).delete()
                else:
                    model(name)._base_manager.filter(user=source).update(user=target)
                continue
            model(name)._base_manager.filter(owner=source).update(owner=target)
    return moved
