"""merge_herd: merging a dumpdata export by natural keys, from a fixture built here."""

import datetime
import io
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from .models import Litter, Pairing, Rabbit, Weight

User = get_user_model()


def make_source():
    """The other database's herd: Frank's rabbits, a pairing and litter, weights, and a demo user."""
    frank = User.objects.create_user(email="frank@example.com", password="x-strong-Pass-1")
    demo = User.objects.create_user(email="demo@example.com", password="x-strong-Pass-1")
    hazel = Rabbit.objects.create(owner=frank, name="Hazel", sex="doe", birth_date=datetime.date(2025, 3, 1), color="Black")
    pip = Rabbit.objects.create(owner=frank, name="Pip", sex="buck", birth_date=datetime.date(2025, 2, 1), color="Fawn")
    Rabbit.objects.create(owner=demo, name="Demo Bun", sex="doe", birth_date=datetime.date(2025, 1, 1))
    Weight.objects.create(rabbit=hazel, date=datetime.date(2026, 9, 1), grams=2100)
    Weight.objects.create(rabbit=pip, date=datetime.date(2026, 9, 1), grams=2300)
    pairing = Pairing.objects.create(owner=frank, doe=hazel, buck=pip)
    Litter.objects.create(owner=frank, pairing=pairing, bred_on=datetime.date(2026, 9, 10))


class MergeHerdTests(TestCase):
    def setUp(self):
        make_source()
        self.export = Path(tempfile.mkdtemp()) / "export.json"
        call_command("dumpdata", "accounts", "rabbits", output=str(self.export), verbosity=0)
        # The target database: the same keeper, who already has Hazel (in another color) and one weight.
        Rabbit.objects.all().delete()
        User.objects.all().delete()
        frank = User.objects.create_user(email="frank@example.com", password="x-strong-Pass-1")
        hazel = Rabbit.objects.create(owner=frank, name="Hazel", sex="doe", birth_date=datetime.date(2025, 3, 1), color="Chocolate")
        Weight.objects.create(rabbit=hazel, date=datetime.date(2026, 9, 1), grams=2100)
        self.frank = frank

    def merge(self, *args):
        out = io.StringIO()
        call_command("merge_herd", str(self.export), *args, stdout=out)
        return out.getvalue()

    def snapshot(self):
        return (User.objects.count(), Rabbit.objects.count(), Weight.objects.count(), Pairing.objects.count(), Litter.objects.count())

    def test_dry_run_reports_and_writes_nothing(self):
        before = self.snapshot()
        report = self.merge("--dry-run")
        self.assertIn("dry run, nothing written", report)
        self.assertIn("rabbits.rabbit: 1 conflict, 1 demo skipped, 1 new", report)
        self.assertEqual(self.snapshot(), before)

    def test_merge_adds_missing_rows_keeps_target_values_and_skips_demo(self):
        report = self.merge()
        self.assertEqual(sorted(Rabbit.objects.values_list("name", flat=True)), ["Hazel", "Pip"])
        self.assertFalse(User.objects.filter(email__startswith="demo").exists())
        hazel = Rabbit.objects.get(name="Hazel")
        self.assertEqual(hazel.color, "Chocolate")  # conflict: the target keeps its value
        self.assertIn("color: kept 'Chocolate', source 'Black'", report)
        self.assertEqual(Weight.objects.count(), 2)  # Hazel's weight was a duplicate, Pip's is new
        pip = Rabbit.objects.get(name="Pip")
        self.assertEqual(pip.owner, self.frank)
        litter = Litter.objects.get()
        self.assertEqual((litter.pairing.doe, litter.pairing.buck, litter.owner), (hazel, pip, self.frank))

    def test_running_twice_doubles_nothing(self):
        self.merge()
        after_first = self.snapshot()
        report = self.merge()
        self.assertEqual(self.snapshot(), after_first)
        self.assertNotIn(" new", report.split("Conflicts")[0].replace("rabbits.rabbit: 1 conflict, 1 demo skipped", ""))

    def test_a_bad_file_is_a_clear_error(self):
        from django.core.management.base import CommandError

        self.export.write_text(json.dumps({"not": "a list"}))
        with self.assertRaises(CommandError):
            self.merge()

    def test_include_demo_merges_demo_users_and_their_rabbits(self):
        self.merge("--include-demo")
        demo = User.objects.get(email="demo@example.com")
        self.assertEqual(list(Rabbit.objects.filter(owner=demo).values_list("name", flat=True)), ["Demo Bun"])

    def test_natural_key_export_is_a_clear_error(self):
        from django.core.management.base import CommandError

        call_command("dumpdata", "accounts", "rabbits", output=str(self.export), verbosity=0,
                     use_natural_foreign_keys=True, use_natural_primary_keys=True)
        before = self.snapshot()
        with self.assertRaisesMessage(CommandError, "natural keys"):
            self.merge()
        self.assertEqual(self.snapshot(), before)
