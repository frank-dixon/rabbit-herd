import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import HealthNote, Rabbit, ShowEntry, Task
from .test_contacts import user


class IndexPageTests(TestCase):
    def setUp(self):
        self.owner = user("index@example.com")
        self.client.force_login(self.owner)
        self.today = timezone.localdate()
        self.rabbit = Rabbit.objects.create(owner=self.owner, name="Hazel", sex="doe", breed="Rex", color="Black",
                                            birth_date=datetime.date(2024, 1, 1))

    def test_view_defaults_differ_per_page_and_are_remembered_per_page(self):
        self.assertEqual(self.client.get(reverse("show_list")).context["view"], "list")
        self.assertEqual(self.client.get(reverse("health_list")).context["view"], "list")
        self.assertEqual(self.client.get(reverse("program_list")).context["view"], "grid")
        self.client.get(reverse("show_list") + "?view=grid")
        self.assertEqual(self.client.get(reverse("show_list")).context["view"], "grid")
        self.assertEqual(self.client.get(reverse("health_list")).context["view"], "list")
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.ui_views, {"shows": "grid"})

    def test_herd_pages_default_to_list_and_health_has_no_toggle(self):
        # Frank, 2026-10-18: Grid/List on Rabbits, Pairings and Litters, list by default; Health and Weights get none.
        for name in ("rabbit_list", "pairing_list", "litter_list"):
            page = self.client.get(reverse(name))
            self.assertEqual(page.context["view"], "list", name)
            self.assertContains(page, 'aria-label="Layout"')
        health = self.client.get(reverse("health_list") + "?view=grid")
        self.assertEqual(health.context["view"], "list")
        self.assertNotContains(health, 'aria-label="Layout"')
        self.assertNotContains(self.client.get(reverse("weights_hub")), 'aria-label="Layout"')

    def test_resolve_closes_note_and_its_follow_up_task(self):
        task = Task.objects.create(owner=self.owner, title="Follow up", due_on=self.today, rabbit=self.rabbit)
        note = HealthNote.objects.create(rabbit=self.rabbit, date=self.today, kind="illness", notes="Snuffles", follow_up_on=self.today, task=task)
        self.client.post(reverse("health_resolve", args=[note.pk]))
        note.refresh_from_db(); task.refresh_from_db()
        self.assertTrue(note.resolved)
        self.assertIsNotNone(task.done_at)
        page = self.client.get(reverse("health_list"))
        self.assertEqual(page.context["items"], [])  # the Open tab is the default
        self.assertEqual(len(self.client.get(reverse("health_list") + "?tab=resolved").context["items"]), 1)
        self.client.post(reverse("health_resolve", args=[note.pk]))
        note.refresh_from_db()
        self.assertFalse(note.resolved)

    def test_overdue_follow_up_is_counted(self):
        HealthNote.objects.create(rabbit=self.rabbit, date=self.today, kind="illness", follow_up_on=self.today - datetime.timedelta(days=2))
        stats = {s["label"]: s["value"] for s in self.client.get(reverse("health_list")).context["stats"]}
        self.assertEqual(stats["Overdue"], 1)

    def test_show_counts_come_from_entries(self):
        for back, leg in ((10, True), (40, True), (400, False)):
            ShowEntry.objects.create(rabbit=self.rabbit, show_name="Open", date=self.today - datetime.timedelta(days=back), placing=1, leg=leg)
        stats = {s["label"]: s for s in self.client.get(reverse("show_list")).context["stats"]}
        self.assertEqual(stats["Legs earned"]["value"], 2)
        self.assertEqual(stats["Closest to GC"]["value"], "Hazel · 2 of 3")

    def test_shows_sort_by_place_from_shared_header(self):
        for back, place in ((10, 3), (20, 1), (30, 2)):
            ShowEntry.objects.create(rabbit=self.rabbit, show_name=f"Show {place}", date=self.today - datetime.timedelta(days=back), placing=place)
        page = self.client.get(reverse("show_list") + "?sort=place")
        self.assertEqual([it["sort"]["place"] for it in page.context["items"]], [1, 2, 3])
        self.assertContains(page, 'aria-sort="ascending"')


class OneGridCardTests(TestCase):
    """Critic v4 G1: Pairings and Litters use the Rabbits grid card (components/grid_card.html):
    the pair's thumbs, the title, one meta line and one pill; no old detail or photo cards."""

    def setUp(self):
        from .models import Litter, Pairing

        self.owner = user("grid@example.com")
        self.client.force_login(self.owner)
        doe = Rabbit.objects.create(owner=self.owner, name="Hazel", sex="doe", breed="Rex", birth_date=datetime.date(2024, 1, 1))
        buck = Rabbit.objects.create(owner=self.owner, name="Moss", sex="buck", breed="Rex", birth_date=datetime.date(2024, 1, 1))
        pairing = Pairing.objects.create(owner=self.owner, doe=doe, buck=buck)
        self.litter = Litter.objects.create(owner=self.owner, pairing=pairing, bred_on=timezone.localdate() - datetime.timedelta(days=10))

    def card(self, name):
        body = self.client.get(reverse(name), {"view": "grid"}).content.decode()
        self.assertIn('data-view="grid"', body)
        return body.split('class="gcard"', 1)[1].split("</a>", 1)[0]

    def test_pairings_grid_card(self):
        card = self.card("pairing_list")
        self.assertIn("Hazel × Moss", card)
        self.assertIn("gcard-thumb is-pair", card)
        self.assertEqual(card.count('class="pill'), 1)
        from .templatetags.dates import short_date
        self.assertIn(f"Due {short_date(self.litter.due_on)}", card)
        self.assertNotIn("Predicted colors", card)

    def test_litters_grid_card(self):
        card = self.card("litter_list")
        self.assertIn("Hazel × Moss", card)
        self.assertIn("gcard-thumb is-pair", card)
        self.assertIn(">Expecting<", card)
        self.assertIn("Due ", card)
        self.assertNotIn("Next:", card)  # the truncated "Next: Kindli…" line is gone (L2)
