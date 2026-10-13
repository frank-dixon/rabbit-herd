"""Merge a herd export (dumpdata JSON) into this database without losing or
doubling anything.

    python manage.py merge_herd export.json --dry-run
    python manage.py merge_herd export.json --source-media /path/to/media

Rows are matched by natural keys (a rabbit is owner + name + birth date +
tattoo; a litter is dam + sire + bred date; a weight is rabbit + date + grams;
a photo is the hash of its file). Foreign keys are remapped to the matching
target rows. An exact duplicate is skipped. A match whose other fields differ
is a conflict: the target keeps its values and the difference is reported,
never overwritten. Demo users (email starting "demo") are left out unless --include-demo. With
--dry-run nothing is written and the same report is printed."""

import hashlib
import json
import os
from collections import Counter, defaultdict

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Processing order and natural keys. A key part "a.b" follows a foreign key.
SPEC = [
    ("rabbits.breed", ("name",)),
    ("accounts.user", ("email",)),
    ("rabbits.herdsettings", ("user",)),
    ("rabbits.breedingschedule", ("owner", "name")),
    ("rabbits.location", ("owner", "name")),
    ("rabbits.contact", ("owner", "name")),
    ("rabbits.outsiderabbit", ("owner", "name", "details")),
    ("rabbits.rabbit", ("owner", "name", "birth_date", "tattoo")),
    ("rabbits.breedshare", ("rabbit", "breed")),
    ("rabbits.weight", ("rabbit", "date", "grams")),
    ("rabbits.relative", ("rabbit", "relationship", "herd_rabbit", "outside")),
    ("rabbits.pedigreeentry", ("rabbit", "position")),
    ("rabbits.gene", ("rabbit", "relative", "locus")),
    ("rabbits.pairing", ("owner", "doe", "buck", "created_at")),
    ("rabbits.litter", ("pairing.doe", "pairing.buck", "bred_on")),
    ("rabbits.cover", ("litter", "date", "time")),
    ("rabbits.task", ("owner", "title", "due_on")),
    ("rabbits.healthnote", ("rabbit", "date", "kind", "notes")),
    ("rabbits.cullnote", ("rabbit", "date", "decision")),
    ("rabbits.showentry", ("rabbit", "show_name", "date", "show_class")),
    ("rabbits.expense", ("owner", "date", "description", "amount")),
    ("rabbits.waitlistentry", ("owner", "buyer", "requested_on")),
    ("rabbits.rabbitphoto", ("rabbit", "#file")),
]
IGNORED_FIELDS = {"created_at", "updated_at", "uploaded_at", "last_login", "date_joined"}


def is_demo(fields):
    return str(fields.get("email", "")).lower().startswith("demo")


class NaturalKeyExport(Exception):
    pass


class Merger:
    def __init__(self, rows, source_media=None, dry_run=False, log=print, include_demo=False):
        self.include_demo = include_demo
        self.rows = rows
        self.media = source_media
        self.dry = dry_run
        self.log = log
        self.map = defaultdict(dict)  # label -> {source pk: target pk}
        self.counts = defaultdict(Counter)
        self.conflicts = []
        self.deferred = []  # (label, target pk, field, source fk pk, related label)
        self.fake = 0

    # helpers
    def model(self, label):
        return apps.get_model(label)

    def target_fk(self, field, source_pk):
        if source_pk is None:
            return None
        return self.map[field.related_model._meta.label_lower].get(source_pk)

    def file_hash_source(self, name):
        if not self.media or not name:
            return None
        path = os.path.join(self.media, name)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    @staticmethod
    def file_hash_target(photo):
        try:
            with photo.image.open("rb") as handle:
                return hashlib.sha256(handle.read()).hexdigest()
        except Exception:
            return None

    def key_value(self, model, values, part):
        """Resolve one key part to a comparable value for the target."""
        if part == "#file":
            return values.get("#hash") or os.path.basename(str(values.get("image") or ""))
        head, _, rest = part.partition(".")
        value = values.get(head)
        if rest:
            related = model._meta.get_field(head).related_model
            obj = related.objects.filter(pk=value).values(rest).first() if value and value > 0 else None
            return obj[rest] if obj else ("pending", head, value)
        field = model._meta.get_field(head)
        if field.get_internal_type() == "DateTimeField" and value is not None:
            return str(value)[:10]
        return value

    def find_target(self, model, values, key):
        if not key:
            return None
        if "#file" in key:
            candidates = model.objects.filter(rabbit_id=values.get("rabbit"))
            wanted = self.key_value(model, values, "#file")
            for photo in candidates:
                theirs = self.file_hash_target(photo) if values.get("#hash") else os.path.basename(photo.image.name)
                if theirs == wanted:
                    return photo
            return None
        filters = {}
        for part in key:
            head, _, rest = part.partition(".")
            value = self.key_value(model, values, part)
            if isinstance(value, tuple):
                return None
            field = model._meta.get_field(head)
            if rest:
                filters[f"{head}__{rest}"] = value
            elif field.is_relation:
                if value is not None and value < 0:
                    return None
                filters[f"{head}_id"] = value
            elif field.get_internal_type() == "DateTimeField":
                filters[f"{head}__date"] = value
            else:
                filters[head] = value
        return model.objects.filter(**filters).first()

    def differs(self, model, target, values):
        out = []
        for field in model._meta.concrete_fields:
            if field.primary_key or field.name in IGNORED_FIELDS or field.name == "password" or field.name not in values:
                continue
            mine = getattr(target, field.attname)
            theirs = values[field.name]
            if field.is_relation:
                if theirs is None and mine is None:
                    continue
            if hasattr(mine, "isoformat"):
                mine = mine.isoformat()
            if str(mine if mine is not None else "") != str(theirs if theirs is not None else ""):
                out.append((field.name, mine, theirs))
        return out

    def run(self):
        by_label = defaultdict(list)
        for row in self.rows:
            by_label[row["model"].lower()].append(row)
        known = {label for label, _ in SPEC}
        for label in sorted(set(by_label) - known):
            if not label.startswith(("auth.", "contenttypes.", "sessions.", "admin.")):
                self.log(f"skip {label}: not merged ({len(by_label[label])} rows)")
        self.check_plain_keys(by_label)
        demo_users = set() if self.include_demo else {row["pk"] for row in by_label.get("accounts.user", []) if is_demo(row["fields"])}
        for label, key in SPEC:
            if label not in by_label:
                continue
            model = self.model(label)
            for row in by_label[label]:
                self.merge_row(model, label, key, row, demo_users)
        for label, target_pk, field, source_pk, related in self.deferred:
            mapped = self.map[related].get(source_pk)
            if mapped is not None and not self.dry:
                self.model(label).objects.filter(pk=target_pk).update(**{field.attname: mapped})
        return self.report()

    def check_plain_keys(self, by_label):
        """Natural-key exports (dumpdata --natural-primary/--natural-foreign) can't be merged; say so clearly."""
        for label, _ in SPEC:
            model = self.model(label)
            relations = [f.name for f in model._meta.get_fields() if f.is_relation and f.concrete]
            for row in by_label.get(label, []):
                fields = row.get("fields", {})
                if "pk" not in row or any(isinstance(fields.get(n), list) and any(isinstance(v, list) for v in fields[n])
                                          or (isinstance(fields.get(n), list) and not model._meta.get_field(n).many_to_many)
                                          for n in relations if n in fields):
                    raise NaturalKeyExport(
                        f"{label} uses natural keys. Re-export without --natural-primary/--natural-foreign: "
                        "python manage.py dumpdata accounts rabbits > export.json")

    def merge_row(self, model, label, key, row, demo_users):
        fields = dict(row["fields"])
        owner_field = next((n for n in ("owner", "user") if n in fields), None)
        if label == "accounts.user" and row["pk"] in demo_users:
            self.counts[label]["demo skipped"] += 1
            return
        if owner_field and fields[owner_field] in demo_users:
            self.counts[label]["demo skipped"] += 1
            return
        values, later = {}, []
        for field in model._meta.concrete_fields:
            if field.primary_key or field.name not in fields:
                continue
            raw = fields[field.name]
            if field.is_relation:
                target = self.target_fk(field, raw)
                if raw is not None and target is None:
                    related = field.related_model._meta.label_lower
                    if field.null:
                        later.append((field, raw, related))
                        values[field.name] = None
                        continue
                    self.counts[label]["missing parent"] += 1
                    return
                values[field.name] = target
            else:
                values[field.name] = field.to_python(raw)  # e.g. BinaryField arrives base64
        if label == "rabbits.rabbitphoto":
            values["#hash"] = self.file_hash_source(fields.get("image"))
        existing = self.find_target(model, values, key)
        if existing is not None:
            self.map[label][row["pk"]] = existing.pk
            diff = self.differs(model, existing, values)
            if diff:
                self.counts[label]["conflict"] += 1
                self.conflicts.append((label, existing.pk, diff))
            else:
                self.counts[label]["duplicate"] += 1
            return
        self.counts[label]["new"] += 1
        if self.dry:
            self.fake -= 1
            self.map[label][row["pk"]] = self.fake
            return
        create = {}
        for name, value in values.items():
            if name.startswith("#"):
                continue
            field = model._meta.get_field(name)
            create[field.attname if field.is_relation else name] = value
        if label == "rabbits.rabbitphoto":
            name = fields.get("image") or ""
            path = os.path.join(self.media, name) if self.media and name else None
            if not path or not os.path.exists(path):
                self.counts[label]["new"] -= 1
                self.counts[label]["file missing"] += 1
                return
            obj = model(**{k: v for k, v in create.items() if k != "image"})
            with open(path, "rb") as handle:
                obj.image.save(os.path.basename(name), ContentFile(handle.read()), save=False)
            obj.save()
        else:
            obj = model.objects.create(**create)
        self.map[label][row["pk"]] = obj.pk
        for field, raw, related in later:
            self.deferred.append((label, obj.pk, field, raw, related))

    def report(self):
        lines = ["merge_herd report" + (" (dry run, nothing written)" if self.dry else "")]
        for label, _ in SPEC:
            if self.counts.get(label):
                parts = ", ".join(f"{n} {k}" for k, n in sorted(self.counts[label].items()))
                lines.append(f"  {label}: {parts}")
        if self.conflicts:
            lines.append("Conflicts (target kept, source value shown):")
            for label, pk, diff in self.conflicts:
                lines.append(f"  {label} #{pk}: " + "; ".join(f"{name}: kept {mine!r}, source {theirs!r}" for name, mine, theirs in diff))
        return "\n".join(lines)


class Command(BaseCommand):
    help = "Merge a dumpdata export into this database by natural keys, skipping duplicates and logging conflicts."

    def add_arguments(self, parser):
        parser.add_argument("export", help="dumpdata JSON file")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--source-media", help="MEDIA_ROOT of the source, to copy and hash photos")
        parser.add_argument("--include-demo", action="store_true",
                            help="also merge demo users (email starting 'demo') and everything they own")

    def handle(self, export, dry_run=False, source_media=None, include_demo=False, **options):
        try:
            with open(export) as handle:
                rows = json.load(handle)
        except (OSError, ValueError) as error:
            raise CommandError(f"Can't read {export}: {error}")
        if not isinstance(rows, list):
            raise CommandError("Expected a dumpdata JSON list.")
        merger = Merger(rows, source_media=source_media, dry_run=dry_run, log=self.stdout.write, include_demo=include_demo)
        with transaction.atomic():
            try:
                report = merger.run()
            except NaturalKeyExport as error:
                raise CommandError(str(error))
            if dry_run:
                transaction.set_rollback(True)
        self.stdout.write(report)
