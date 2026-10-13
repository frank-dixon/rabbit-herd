import datetime

from django.test import TestCase
from django.urls import reverse

from .models import OutsideRabbit, PedigreeEntry, Rabbit, Relative
from .pedigree import build_tree
from .test_contacts import user


class PedigreeTests(TestCase):
    def setUp(self):
        self.owner = user("ped@example.com")
        self.client.force_login(self.owner)
        mk = lambda name, sex, **kw: Rabbit.objects.create(owner=self.owner, name=name, sex=sex, breed="Rex", color="Black",
                                                           birth_date=datetime.date(2024, 1, 1), **kw)
        self.kit = mk("Clover", "doe", tattoo="CL1")
        self.dam = mk("Hazel", "doe")
        self.granddam = mk("Pepper", "doe")
        self.oreo = OutsideRabbit.objects.create(owner=self.owner, name="Oreo", details="Broken black NZ")
        self.old = OutsideRabbit.objects.create(owner=self.owner, name="Old Tom")
        Relative.objects.create(rabbit=self.kit, relationship="dam", herd_rabbit=self.dam)
        Relative.objects.create(rabbit=self.kit, relationship="sire", outside=self.oreo, color="Broken black")
        Relative.objects.create(rabbit=self.dam, relationship="dam", herd_rabbit=self.granddam)
        PedigreeEntry.objects.create(rabbit=self.granddam, position="s", outside=self.old)

    def test_tree_follows_herd_ancestors_up(self):
        tree = build_tree(self.kit)
        self.assertEqual({p: c["name"] for p, c in tree.items()}, {"d": "Hazel", "s": "Oreo", "dd": "Pepper", "dds": "Old Tom"})
        self.assertEqual(tree["s"]["color"], "Broken black")
        self.assertEqual(tree["s"]["breed"], "Broken black NZ")

    def test_own_pedigree_entry_wins_over_relatives(self):
        other = OutsideRabbit.objects.create(owner=self.owner, name="Recorded sire")
        PedigreeEntry.objects.create(rabbit=self.kit, position="s", outside=other)
        self.assertEqual(build_tree(self.kit)["s"]["name"], "Recorded sire")

    def test_page_and_link(self):
        page = self.client.get(reverse("rabbit_pedigree", args=[self.kit.pk]))
        self.assertContains(page, "Pedigree: Clover")
        self.assertContains(page, "4 of 14 ancestors recorded")
        self.assertContains(page, 'data-pedigree-cell="dds"')
        self.assertContains(page, "Dam&#x27;s dam&#x27;s sire")
        self.assertContains(page, "Not recorded")
        self.assertContains(page, "grid-row: 5 / span 4")
        self.assertContains(self.client.get(reverse("rabbit_detail", args=[self.kit.pk])), 'href="/rabbits/%d/pedigree/"' % self.kit.pk)
        self.client.force_login(user("x@example.com"))
        self.assertEqual(self.client.get(reverse("rabbit_pedigree", args=[self.kit.pk])).status_code, 404)
