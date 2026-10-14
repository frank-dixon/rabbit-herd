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
