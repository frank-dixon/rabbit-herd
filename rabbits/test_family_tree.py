import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .family_tree import payload
from .models import OutsideRabbit, PedigreeEntry, Rabbit, Relative
from .test_contacts import user


class FamilyTreeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = user("tree@example.com")
        self.client.force_login(self.owner)
        mk = lambda name, sex, color: Rabbit.objects.create(owner=self.owner, name=name, sex=sex, breed="Mini Rex", color=color,
                                                            birth_date=datetime.date(2025, 1, 1))
        self.kit, self.snow = mk("Juniper", "doe", "Broken chinchilla"), mk("Snow", "doe", "Ruby-eyed white")
        self.sire, self.dam = mk("Ash", "buck", "Broken black"), mk("Hazel", "doe", "Chinchilla")
        for kid in (self.kit, self.snow):
            Relative.objects.create(rabbit=kid, relationship="sire", herd_rabbit=self.sire)
            Relative.objects.create(rabbit=kid, relationship="dam", herd_rabbit=self.dam)
        frost = OutsideRabbit.objects.create(owner=self.owner, name="Frost", details="Ruby-eyed white buck · Mini Rex")
        PedigreeEntry.objects.create(rabbit=self.sire, position="s", outside=frost)

    def test_payload_has_tree_relatives_and_proven_thread(self):
        data = payload(self.kit)
        names = {n["name"]: k for k, n in data["nodes"].items()}
        self.assertEqual(data["places"]["1"], names["Juniper"])
        self.assertEqual(data["places"]["4"], names["Frost"])
        self.assertEqual(data["nodes"][names["Snow"]]["lateral"]["kind"], "sibling")
        self.assertEqual(data["nodes"][names["Frost"]]["color"], "Ruby-eyed white")
        c = next(chip for chip in data["chips"] if chip["id"] == "C-c")
        self.assertIn([names["Ash"], names["Snow"], "known"], c["edges"])
        self.assertIn(names["Frost"], c["sources"])
        hazel_c = [r for r in data["nodes"][names["Hazel"]]["genes"]["C"]["pair"] if r["allele"] == "c"]
        self.assertEqual(hazel_c[0]["level"], "known")
        self.assertTrue(data["nodes"][names["Frost"]]["placeholder"])

    def test_results_are_cached_per_rabbit_until_records_change(self):
        payload(self.kit)
        self.assertIsNotNone(cache.get(f"family-genes:{self.kit.pk}"))
        digest = cache.get(f"family-genes:{self.kit.pk}")["digest"]
        self.dam.color = "Black"
        self.dam.save()
        payload(self.kit)
        self.assertNotEqual(cache.get(f"family-genes:{self.kit.pk}")["digest"], digest)

    def test_view_toggle(self):
        url = reverse("rabbit_pedigree", args=[self.kit.pk])
        classic = self.client.get(url)
        self.assertContains(classic, "data-pedigree-tree")
        self.assertContains(classic, "Family tree")
        family = self.client.get(url + "?view=family")
        self.assertContains(family, "data-family-tree")
        self.assertContains(family, 'id="family-tree-data"')
        self.assertNotContains(family, "data-pedigree-tree")
