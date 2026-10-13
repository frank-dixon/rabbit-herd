"""Rabbit list tabs: Active is the living herd, Former holds sold, culled and
deceased rabbits, Archived stays separate. Counts match the lists."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Rabbit, Weight


class ListTabTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="l@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        mk = lambda name, status, **kw: Rabbit.objects.create(owner=self.user, name=name, sex="doe", birth_date="2024-01-01", status=status, **kw)
        mk("Willow", "breeding")
        mk("Fern", "growing")
        mk("Lily", "sold")
        mk("Juniper", "culled")
        mk("Pepper", "deceased")
        mk("Old", "breeding", archived_at=timezone.now())

    def names(self, **params):
        page = self.client.get(reverse("rabbit_list"), {"view": "list", **params})
        return page, sorted(r.name for r in page.context["rabbits"])

    def test_each_status_lands_in_its_tab(self):
        page, active = self.names()
        self.assertEqual(active, ["Fern", "Willow"])
        self.assertEqual(self.names(tab="former")[1], ["Juniper", "Lily", "Pepper"])
        self.assertEqual(self.names(tab="archived")[1], ["Old"])
        self.assertEqual(self.names(tab="deceased")[1], ["Juniper", "Lily", "Pepper"])  # the old link

    def test_counts_and_subtitle_match(self):
        page, active = self.names()
        c = page.context
        self.assertEqual((c["active_count"], c["former_count"], c["archived_count"]), (2, 3, 1))
        self.assertEqual(c["subtitle"], "2 active rabbits in your herd")
        self.assertEqual(self.names(tab="former")[0].context["subtitle"], "3 former rabbits")
        self.assertContains(page, "Former")
        self.assertNotContains(page, ">Deceased <")

    def test_list_rows_show_columns_without_the_scale_button(self):
        willow = Rabbit.objects.get(name="Willow")
        Weight.objects.create(rabbit=willow, date="2026-10-01", grams=4113)
        page, _ = self.names()
        self.assertContains(page, "Last weight")
        self.assertContains(page, "9 lb 1 oz")
        self.assertNotContains(page, 'title="Log weight"')
        self.assertContains(page, "data-status-chip")
