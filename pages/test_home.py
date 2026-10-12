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
        self.assertContains(page, "Nothing yet.")
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
        self.assertContains(page, "3 active rabbits")
        self.assertContains(page, "Pepper died")
        self.assertContains(page, "Died kindling")
        self.assertContains(page, "Archived Old")
        self.assertNotContains(page, "Stranger")

    def test_recent_lists_newest_first_and_links_to_the_rabbit(self):
        older = self.add("Older")
        Rabbit.objects.filter(pk=older.pk).update(created_at=timezone.now() - datetime.timedelta(days=3))
        newer = self.add("Newer")
        recent = self.client.get(reverse("index")).context["recent"]
        self.assertEqual([item["title"] for item in recent[:2]], ["Added Newer to the herd", "Added Older to the herd"])
        self.assertEqual(recent[0]["when"], "Today")
        self.assertContains(self.client.get(reverse("index")), f'href="{reverse("rabbit_detail", args=[newer.pk])}"')
