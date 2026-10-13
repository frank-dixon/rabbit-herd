import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Rabbit, ShowEntry
from .test_contacts import user


class ShowTests(TestCase):
    def setUp(self):
        self.owner = user("shows@example.com")
        self.client.force_login(self.owner)
        self.rabbit = Rabbit.objects.create(owner=self.owner, name="Juniper", sex="doe", breed="Mini Rex", color="Black",
                                            birth_date=datetime.date(2025, 1, 1))
        self.today = timezone.localdate()
        self.detail = reverse("rabbit_detail", args=[self.rabbit.pk])
        self.add = reverse("rabbit_show_add", args=[self.rabbit.pk])

    def data(self, **extra):
        return {"show_name": "Keystone Classic", "show_date": self.today.isoformat(), "location": "Harrisburg, PA",
                "show_class": "Senior Doe", "placing": "1", "out_of": "9", "award": "Best of Breed",
                "judge": "R. Alvarez", "leg": "on", "notes": "Strong shoulders", **extra}

    def test_add_edit_remove_and_legs(self):
        self.client.post(self.add, self.data())
        entry = ShowEntry.objects.get()
        self.assertEqual(entry.placing_text, "1st of 9")
        page = self.client.get(self.detail)
        for text in ("Keystone Classic", "Senior Doe", "1st of 9", "Best of Breed", "Judge: R. Alvarez", "1 of 3 legs"):
            self.assertContains(page, text)
        editing = self.client.get(self.detail + f"?show={entry.pk}")
        self.assertContains(editing, "Edit Keystone Classic")
        self.assertContains(editing, 'value="Harrisburg, PA"')
        self.assertContains(editing, " checked>")
        self.client.post(reverse("rabbit_show_edit", args=[entry.pk]), self.data(placing="2", leg=""))
        entry.refresh_from_db()
        self.assertEqual((entry.placing, entry.leg), (2, False))
        self.assertNotContains(self.client.get(self.detail), "data-show-legs")
        for _ in range(3):
            self.client.post(self.add, self.data())
        self.assertContains(self.client.get(self.detail), "enough for grand champion")
        self.client.post(reverse("rabbit_show_delete", args=[entry.pk]))
        self.assertEqual(ShowEntry.objects.count(), 3)

    def test_bad_input(self):
        for extra, msg in (
            ({"show_name": ""}, "show&#x27;s name"),
            ({"show_date": ""}, "show&#x27;s date"),
            ({"show_date": (self.today + datetime.timedelta(days=2)).isoformat()}, "in the future"),
            ({"placing": "first"}, "whole numbers"),
            ({"placing": "10", "out_of": "9"}, "larger than the class size"),
        ):
            self.assertContains(self.client.post(self.add, self.data(**extra), follow=True), msg)
        self.assertFalse(ShowEntry.objects.exists())
        self.client.post(self.add, self.data(placing="", out_of="", leg=""))
        self.assertEqual(ShowEntry.objects.get().placing_text, "")
        self.assertEqual(ShowEntry(placing=12).placing_text, "12th")
        self.assertEqual(ShowEntry(placing=22).placing_text, "22nd")

    def test_owner_scope(self):
        entry = ShowEntry.objects.create(rabbit=self.rabbit, show_name="X", date=self.today)
        self.client.force_login(user("x@example.com"))
        self.assertEqual(self.client.post(self.add, self.data()).status_code, 404)
        self.assertEqual(self.client.post(reverse("rabbit_show_edit", args=[entry.pk]), self.data()).status_code, 404)
        self.assertEqual(self.client.post(reverse("rabbit_show_delete", args=[entry.pk])).status_code, 404)
