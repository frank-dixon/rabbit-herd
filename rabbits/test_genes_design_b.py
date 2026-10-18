"""Genes design B: computed genes, the parity tool, the reversible cleanup and the prune commands."""

import datetime
import io
import json
import tempfile
import uuid
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from rabbits import derived, genes_cleanup
from rabbits.models import Gene, HistoryEntry, PedigreeEntry, Rabbit, SyncOp


def rabbit(owner, name, color="Black", sex="doe", **extra):
    return Rabbit.objects.create(owner=owner, name=name, sex=sex, breed="New Zealand", color=color,
                                 birth_date=datetime.date(2025, 1, 1), **extra)


def store_implied(r, certainty="probable", note=""):
    for g in derived.implied_genes(r):
        Gene.objects.create(rabbit=r, locus=g.locus, genotype=g.genotype, certainty=certainty, note=note)


class DesignBTests(TestCase):
    def setUp(self):
        self.demo = User.objects.create_user(email=genes_cleanup.DEMO_EMAIL)
        self.keeper = User.objects.create_user(email="keeper@example.com")
        self.dam = rabbit(self.demo, "Dam")
        self.sire = rabbit(self.demo, "Sire", sex="buck")
        self.gdam = rabbit(self.demo, "Granddam")
        self.kit = rabbit(self.demo, "Kit")
        store_implied(self.kit)
        self.assertTrue(derived.implied_genes(self.kit), "Black New Zealand should prove some genes")
        PedigreeEntry.objects.create(rabbit=self.dam, position="d", herd_rabbit=self.gdam)
        PedigreeEntry.objects.create(rabbit=self.kit, position="d", herd_rabbit=self.dam)
        PedigreeEntry.objects.create(rabbit=self.kit, position="s", herd_rabbit=self.sire)
        self.copy = PedigreeEntry.objects.create(rabbit=self.kit, position="dd", herd_rabbit=self.gdam)

    def test_plan_only_takes_computable_app_written_rows(self):
        mine = rabbit(self.keeper, "Mine")
        store_implied(mine)  # a keeper's own rows: never touched
        known = rabbit(self.demo, "Known")
        store_implied(known, certainty="known")
        noted = rabbit(self.demo, "Noted")
        store_implied(noted, note="Seller said so")
        p = genes_cleanup.plan()
        kit_genes = set(Gene.objects.filter(rabbit=self.kit).values_list("pk", flat=True))
        self.assertEqual(set(p["genes"]), kit_genes)
        self.assertEqual(p["flag"], [self.kit.pk])
        self.assertEqual(p["pedigree"], [self.copy.pk])

    def test_parity_is_zero_and_writes_nothing(self):
        before = (Gene.objects.count(), PedigreeEntry.objects.count())
        out = io.StringIO()
        call_command("genetics_parity", stdout=out)
        self.assertIn("Mismatches: 0", out.getvalue())
        self.assertEqual((Gene.objects.count(), PedigreeEntry.objects.count()), before)
        self.assertFalse(Rabbit.objects.filter(genes_implied=True).exists())

    def test_cleanup_dry_run_remove_and_restore(self):
        old = derived.gene_key(derived.genes_of(Rabbit.objects.get(pk=self.kit.pk)))
        out = io.StringIO()
        call_command("genes_cleanup", "--dry-run", stdout=out)
        self.assertIn("Dry run", out.getvalue())
        self.assertTrue(Gene.objects.filter(rabbit=self.kit).exists())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "backup.json"
            call_command("genes_cleanup", "--backup", str(path), stdout=io.StringIO())
            self.assertFalse(Gene.objects.filter(rabbit=self.kit).exists())
            self.assertFalse(PedigreeEntry.objects.filter(pk=self.copy.pk).exists())
            kit = Rabbit.objects.get(pk=self.kit.pk)
            self.assertTrue(kit.genes_implied)
            self.assertEqual(derived.gene_key(derived.genes_of(kit)), old)
            self.assertFalse(HistoryEntry.objects.filter(rabbit=kit, subject="gene", action="deleted").exists())
            self.assertTrue(json.loads(path.read_text())["genes"])
            call_command("genes_cleanup", "--restore", str(path), stdout=io.StringIO())
        self.assertTrue(PedigreeEntry.objects.filter(pk=self.copy.pk).exists())
        kit = Rabbit.objects.get(pk=self.kit.pk)
        self.assertFalse(kit.genes_implied)
        self.assertEqual(derived.gene_key(list(kit.genes.all())), old)

    def test_coat_change_and_gene_edit_store_computed_genes_first(self):
        genes_cleanup.apply(genes_cleanup.plan())
        kit = Rabbit.objects.get(pk=self.kit.pk)
        shown = derived.gene_key(derived.genes_of(kit))
        kit.color = "Ruby-eyed white"
        kit.save()
        kit = Rabbit.objects.get(pk=self.kit.pk)
        self.assertFalse(kit.genes_implied)
        self.assertEqual(derived.gene_key(list(kit.genes.all())), shown)


class PruneTests(TestCase):
    def test_prune_sync_ops_keeps_recent(self):
        user = User.objects.create_user(email="s@example.com")
        old = SyncOp.objects.create(op_id=uuid.uuid4(), owner=user, kind="weight")
        SyncOp.objects.filter(pk=old.pk).update(applied_at=timezone.now() - datetime.timedelta(days=31))
        SyncOp.objects.create(op_id=uuid.uuid4(), owner=user, kind="weight")
        call_command("prune_sync_ops", "--dry-run", stdout=io.StringIO())
        self.assertEqual(SyncOp.objects.count(), 2)
        call_command("prune_sync_ops", stdout=io.StringIO())
        self.assertEqual(SyncOp.objects.count(), 1)

    def test_prune_history_age_and_cap(self):
        user = User.objects.create_user(email="h@example.com")
        r = rabbit(user, "H")
        HistoryEntry.objects.all().delete()
        for i in range(60):
            HistoryEntry.objects.create(rabbit=r, action="changed", subject="rabbit", summary=str(i))
        aged = HistoryEntry.objects.create(rabbit=r, action="changed", subject="rabbit", summary="old")
        HistoryEntry.objects.filter(pk=aged.pk).update(created_at=timezone.now() - datetime.timedelta(days=800))
        call_command("prune_history", "--keep", "50", stdout=io.StringIO())
        self.assertEqual(HistoryEntry.objects.count(), 50)
        self.assertFalse(HistoryEntry.objects.filter(pk=aged.pk).exists())
