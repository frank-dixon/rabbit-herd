"""Stacked litter cards: growing-out kits of one litter fold into one entry on
the Active tab; singles, other statuses and other tabs stay normal cards."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .litter_stacks import LitterStack
from .models import Litter, OutsideRabbit, Pairing, Rabbit, Relative


class LitterStackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="s@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        self.mk = lambda name, status="growing", sex="doe", **kw: Rabbit.objects.create(
            owner=self.user, name=name, sex=sex, birth_date=kw.pop("born", "2026-09-01"), status=status, **kw)
        self.dam, self.sire = self.mk("Juniper", "breeding"), self.mk("Speedwell", "breeding", sex="buck")
        self.litter = Litter.objects.create(owner=self.user, bred_on="2026-07-28",
                                            pairing=Pairing.objects.create(owner=self.user, doe=self.dam, buck=self.sire))
        for i in range(1, 4):
            self.mk(f"Juniper kit {i}", litter=self.litter)

    def entries(self, **params):
        page = self.client.get(reverse("rabbit_list"), params)
        return page, page.context["entries"]

    def stacks(self, entries):
        return [e for e in entries if isinstance(e, LitterStack)]

    def test_litter_kits_fold_into_one_stack(self):
        page, entries = self.entries(view="grid")
        [stack] = self.stacks(entries)
        self.assertEqual((stack.count, stack.title), (3, "Juniper × Speedwell"))
        self.assertEqual(len(page.context["rabbits"]), 5)  # counts stay per rabbit
        self.assertEqual(page.context["subtitle"], "5 active rabbits in your herd")
        self.assertContains(page, 'data-litter-toggle="l%d"' % self.litter.pk)
        self.assertContains(page, 'aria-expanded="false"')
        self.assertContains(page, "3 kits")
        self.assertContains(page, "Juniper kit 2")  # kit cards are in the (hidden) band
        self.assertContains(page, "/static/js/app.js")  # the toggle needs the app script on the page

    def test_list_view_has_group_row_and_hidden_kit_rows(self):
        page, _ = self.entries(view="list")
        self.assertContains(page, "litter-stack-row")
        self.assertContains(page, 'data-litter-of="l%d" hidden' % self.litter.pk, count=3)

    def test_non_growing_and_single_kits_stay_cards(self):
        Rabbit.objects.filter(name__in=["Juniper kit 1", "Juniper kit 2"]).update(status="breeding")
        _, entries = self.entries()
        self.assertEqual(self.stacks(entries), [])
        self.assertEqual(len(entries), 5)

    def test_same_dam_sire_birthdate_without_litter_link(self):
        out = OutsideRabbit.objects.create(owner=self.user, name="Hopper")
        kits = [self.mk(f"Loose {i}", born="2026-08-15") for i in range(2)]
        for kit in kits:
            Relative.objects.create(rabbit=kit, relationship="dam", herd_rabbit=self.dam)
            Relative.objects.create(rabbit=kit, relationship="sire", outside=out)
        _, entries = self.entries()
        titles = sorted(s.title for s in self.stacks(entries))
        self.assertEqual(titles, ["Juniper × Hopper", "Juniper × Speedwell"])

    def test_filter_match_renders_open(self):
        page, entries = self.entries(q="kit", view="grid")
        self.assertEqual(len(self.stacks(entries)), 1)
        self.assertContains(page, 'aria-expanded="true"')
        self.assertNotContains(page, 'data-litter-of="l%d" hidden' % self.litter.pk)

    def test_other_tabs_do_not_stack(self):
        Rabbit.objects.filter(litter=self.litter).update(status="sold")
        _, entries = self.entries(tab="former")
        self.assertEqual(self.stacks(entries), [])
