import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import HistoryEntry, Rabbit, Weight

User = get_user_model()


class HistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="frank@example.com", password="x-strong-Pass-1")
        self.rabbit = Rabbit.objects.create(owner=self.user, name="Hazel", sex="doe", breed="Mini Rex", color="Black",
                                            birth_date=datetime.date(2025, 3, 1))

    def test_add_change_and_record_edits_are_logged_with_old_and_new(self):
        self.rabbit.color = "Castor"
        self.rabbit.status = "growing"
        self.rabbit.save()
        weight = Weight.objects.create(rabbit=self.rabbit, date=datetime.date(2026, 10, 13), grams=1985)
        weight.delete()
        entries = list(HistoryEntry.objects.filter(rabbit=self.rabbit).order_by("id"))
        self.assertEqual([e.action for e in entries], ["added", "changed", "added", "deleted"])
        self.assertIn({"field": "Color", "old": "Black", "new": "Castor"}, entries[1].changes)
        self.assertIn({"field": "Status", "old": "Breeding", "new": "Growing out"}, entries[1].changes)
        self.assertEqual(entries[2].summary, "Added weight 4 lb 6 oz on Tue, Oct 13.")

    def test_saving_without_changes_logs_nothing_and_deleting_the_rabbit_is_clean(self):
        self.rabbit.save()
        self.assertEqual(HistoryEntry.objects.count(), 1)
        Weight.objects.create(rabbit=self.rabbit, date=datetime.date(2026, 10, 13), grams=1985)
        self.rabbit.delete()
        self.assertEqual(HistoryEntry.objects.count(), 0)

    def test_history_page_is_owner_only(self):
        url = reverse("rabbit_history", args=[self.rabbit.pk])
        other = User.objects.create_user(email="o@example.com", password="x-strong-Pass-1")
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(url), "Added Hazel.")
