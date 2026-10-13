import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rabbits.models import Rabbit


class HomeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="home@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)

    def add(self, name, **extra):
        return Rabbit.objects.create(owner=self.user, name=name, birth_date="2024-03-10", **{"sex": "doe", **extra})

    def test_a_new_account_sees_empty_states_and_no_example_numbers(self):
        page = self.client.get(reverse("index"))
        self.assertContains(page, "No rabbits yet.")
        self.assertContains(page, "Add a rabbit")
        for fake in ("Willow", "Snow", "Nest box", "Kindling due", "7 kits"):
            self.assertNotContains(page, fake)

    def test_counts_come_from_the_herd(self):
        self.add("Willow", status="breeding")
        self.add("Jet", sex="buck", status="breeding")
        self.add("Fern", status="growing")
        self.add("Pepper", status="deceased", death_date=datetime.date(2026, 5, 18), death_cause="Died kindling")
        self.add("Old", archived_at=timezone.now())
        Rabbit.objects.create(owner=get_user_model().objects.create_user(email="o@example.com", password="x-strong-Pass-1"),
                              name="Stranger", sex="doe", birth_date="2024-01-01")
        page = self.client.get(reverse("index"))
        herd = page.context["herd"]
        self.assertEqual((herd["active"], herd["does"], herd["bucks"], herd["deceased"], herd["archived"]), (3, 2, 1, 1, 1))
        self.assertEqual([(s["label"], s["count"]) for s in herd["statuses"]], [("Breeding", 2), ("Growing out", 1)])
        self.assertContains(page, "3 rabbits</a> · 2 does · 1 buck · 2 breeding · 1 growing out")
        self.assertNotContains(page, "Stranger")

    def test_recent_lists_newest_first_and_links_to_the_rabbit(self):
        older = self.add("Older")
        Rabbit.objects.filter(pk=older.pk).update(created_at=timezone.now() - datetime.timedelta(days=3))
        newer = self.add("Newer")
        recent = self.client.get(reverse("index")).context["recent"]
        self.assertEqual([item["title"] for item in recent[:2]], ["Added Newer to the herd", "Added Older to the herd"])
        self.assertEqual(recent[0]["when"], "Today")


    def test_today_sections_from_real_data(self):
        from rabbits.models import HealthNote, Litter, Pairing, Task, Weight
        today = timezone.localdate()
        doe, buck = self.add("Lily"), self.add("Rook", sex="buck")
        overdue = Task.objects.create(owner=self.user, title="Clean hutch", due_on=today - datetime.timedelta(days=2))
        Task.objects.create(owner=self.user, title="Trim nails", due_on=today + datetime.timedelta(days=3))
        Task.objects.create(owner=self.user, title="Far off", due_on=today + datetime.timedelta(days=30))
        pairing = Pairing.objects.create(owner=self.user, doe=doe, buck=buck)
        litter = Litter.objects.create(owner=self.user, pairing=pairing, bred_on=today - datetime.timedelta(days=52),
                                       kindled_on=today - datetime.timedelta(days=21), born_alive=3)
        for name, grams in (("Kit A", 330), ("Kit B", 320), ("Kit C", 200)):
            kit = self.add(name, litter=litter)
            Weight.objects.create(rabbit=kit, date=today, grams=grams, unit="kg")
        followup = Task.objects.create(owner=self.user, title="Recheck ears", due_on=today, rabbit=doe)
        HealthNote.objects.create(rabbit=doe, date=today - datetime.timedelta(days=5), kind="treatment",
                                  follow_up_on=today, task=followup)
        page = self.client.get(reverse("index"))
        ctx = page.context
        self.assertEqual([i["title"] for i in ctx["due_now"]], ["Clean hutch", "Recheck ears"])
        self.assertTrue(ctx["due_now"][0]["overdue"])
        self.assertIn("Trim nails", [i["title"] for i in ctx["this_week"]])
        self.assertNotIn("Far off", [i["title"] for i in ctx["this_week"]])
        row = ctx["litters"][0]
        self.assertEqual((row["age"], row["kits"], row["behind"], row["average"]), (21, 3, 1, 283))
        titles = [w["title"] for w in ctx["watch"]]
        self.assertEqual(titles, ["Lily · treatment", "Kit C"])
        self.assertContains(page, f'action="/tasks/{overdue.pk}/done/"')
        self.assertContains(page, "data-quick-done")

    def test_empty_today_sections_say_so(self):
        self.add("Lily")
        page = self.client.get(reverse("index"))
        self.assertContains(page, "All caught up.")
        self.assertContains(page, "No litters on the ground.")
        self.assertNotContains(page, "Watch list")
