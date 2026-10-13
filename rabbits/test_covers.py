"""Breeding sessions: several covers per litter; the bred date follows the first that took."""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Cover, Litter, Pairing, Rabbit


class CoverTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="cov@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        mk = lambda name, sex: Rabbit.objects.create(owner=self.user, name=name, sex=sex, breed="Rex", birth_date=datetime.date(2024, 1, 1))
        self.pairing = Pairing.objects.create(owner=self.user, doe=mk("Hazel", "doe"), buck=mk("Basil", "buck"))
        self.today = timezone.localdate()
        self.client.post(reverse("litter_create", args=[self.pairing.pk]), {"bred_on": (self.today - datetime.timedelta(days=3)).isoformat()})
        self.litter = Litter.objects.get(pairing=self.pairing)
        self.add = reverse("cover_add", args=[self.litter.pk])

    def test_starting_a_litter_records_the_first_cover(self):
        self.assertEqual(list(self.litter.covers.values_list("date", "outcome")), [(self.litter.bred_on, "covered")])
        page = self.client.get(reverse("litter_detail", args=[self.litter.pk]))
        self.assertContains(page, 'id="covers"')
        self.assertContains(page, "data-counts")

    def test_more_covers_and_the_bred_date_follows_the_first_that_took(self):
        earlier = self.today - datetime.timedelta(days=4)
        self.client.post(self.add, {"date": earlier.isoformat(), "time": "07:30", "outcome": "refused", "note": "Ran"})
        self.litter.refresh_from_db()
        self.assertEqual(self.litter.bred_on, self.today - datetime.timedelta(days=3))
        self.client.post(self.add, {"date": earlier.isoformat(), "time": "18:00", "outcome": "covered"})
        self.litter.refresh_from_db()
        self.assertEqual(self.litter.bred_on, earlier)
        self.assertEqual(self.litter.covers.count(), 3)
        page = self.client.get(reverse("litter_detail", args=[self.litter.pk]))
        self.assertContains(page, "7:30 AM")
        self.assertContains(page, "Refused")

    def test_removing_the_counted_cover_moves_the_date_to_the_next(self):
        later = self.today - datetime.timedelta(days=2)
        self.client.post(self.add, {"date": later.isoformat(), "outcome": "covered"})
        first = self.litter.covers.order_by("date").first()
        self.client.post(reverse("cover_delete", args=[self.litter.pk, first.pk]))
        self.litter.refresh_from_db()
        self.assertEqual(self.litter.bred_on, later)

    def test_bad_input_saves_nothing(self):
        for data in ({"date": ""}, {"date": (self.today + datetime.timedelta(days=1)).isoformat()},
                     {"date": self.today.isoformat(), "outcome": "maybe"}, {"date": self.today.isoformat(), "time": "25:99"}):
            self.client.post(self.add, data)
        self.assertEqual(self.litter.covers.count(), 1)

    def test_strangers_cannot_add_or_remove(self):
        other = get_user_model().objects.create_user(email="cov2@example.com", password="x-strong-Pass-1")
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.add, {"date": self.today.isoformat()}).status_code, 404)
        cover = self.litter.covers.first()
        self.assertEqual(self.client.post(reverse("cover_delete", args=[self.litter.pk, cover.pk])).status_code, 404)
        self.assertTrue(Cover.objects.filter(pk=cover.pk).exists())
