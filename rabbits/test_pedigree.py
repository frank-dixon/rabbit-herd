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


class PedigreeThumbTests(TestCase):
    def test_each_recorded_ancestor_gets_a_thumbnail_sized_to_its_generation(self):
        from datetime import date
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        from .models import OutsideRabbit, Rabbit, Relative
        user = get_user_model().objects.create_user(email="pt@example.com", password="x-strong-Pass-1")
        self.client.force_login(user)
        kit = Rabbit.objects.create(owner=user, name="Kit", sex="doe", breed="Rex", birth_date=date(2025, 1, 1))
        dam = Rabbit.objects.create(owner=user, name="Maple", sex="doe", breed="Rex", birth_date=date(2023, 1, 1))
        Relative.objects.create(rabbit=kit, relationship="dam", herd_rabbit=dam)
        Relative.objects.create(rabbit=dam, relationship="dam", outside=OutsideRabbit.objects.create(owner=user, name="Olive"))
        body = self.client.get(reverse("rabbit_pedigree", args=[kit.pk])).content.decode()
        tree = body[body.index("data-pedigree-tree"):body.index("data-pedigree-list")]
        cell = lambda pos: tree[tree.index(f'data-pedigree-cell="{pos}"'):][:900]
        self.assertIn("md:h-14", cell("d"))
        self.assertIn(">M</span>", cell("d"))
        self.assertIn("h-12 w-12 rounded-lg text-base", cell("dd"))
        self.assertIn(">O</span>", cell("dd"))
        self.assertNotIn("data-avatar", cell("s")[:cell("s").index("</div>\n</div>")])
