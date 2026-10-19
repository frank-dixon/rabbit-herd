import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import growth_curve as G
from .models import Rabbit, Weight
from .test_contacts import user
from .weights_page import change_30, weigh_note


class CurveTests(TestCase):
    def test_interpolates_inside_the_measured_range_only(self):
        self.assertEqual(G.expected(G.NZ, 28), 590)
        self.assertEqual(G.expected(G.NZ, 35), (590 + 1105) / 2)
        self.assertIsNone(G.expected(G.NZ, 21))
        self.assertIsNone(G.expected(G.NZ, 90))
        self.assertAlmostEqual(G.versus(G.NZ, 56, 1344.6), -0.1, places=3)

    def test_breed_picks_the_curve(self):
        r = lambda breed: Rabbit(breed=breed)
        self.assertIs(G.curve_for(r("New Zealand"))[0], G.NZ)
        self.assertIs(G.curve_for(r("NZ × Californian"))[0], G.NZ_X_CAL)
        self.assertIsNone(G.curve_for(r("Rex"))[0])


class ChangeTests(TestCase):
    def test_thirty_day_change_uses_the_weigh_in_nearest_30_days_back(self):
        d = datetime.date(2026, 9, 1)
        ws = [Weight(date=d, grams=3000), Weight(date=d + datetime.timedelta(days=28), grams=3200),
              Weight(date=d + datetime.timedelta(days=58), grams=3500)]
        self.assertEqual(change_30(ws), 300)
        self.assertIsNone(change_30(ws[:1]))


class WeighNoteTests(TestCase):
    def test_note_uses_the_overdue_intervals_and_says_every_day_for_one(self):
        self.assertEqual(weigh_note(), "Weigh adults every 30 days and juniors every 7 days.")
        self.assertEqual(weigh_note(1, 7), "Weigh adults every day and juniors every 7 days.")
        self.assertEqual(weigh_note(14, 1), "Weigh adults every 14 days and juniors every day.")


class WeightsPageTests(TestCase):
    def test_phone_row_keeps_the_date_on_one_line(self):
        """Critic v7 M2: "Tue, Oct / 6" no longer breaks at 390."""
        day = timezone.localdate()
        self.assertContains(self.client.get(reverse("weights_hub")), f'<span class="whitespace-nowrap">{day:%a}, {day:%b} {day.day}</span>', html=False)

    def test_overdue_card_shows_the_weigh_note(self):
        self.assertContains(self.client.get(reverse("weights_hub")), "Weigh adults every 30 days and juniors every 7 days.")

    def setUp(self):
        self.owner = user("wp@example.com")
        self.client.force_login(self.owner)
        today = timezone.localdate()
        self.kit = Rabbit.objects.create(owner=self.owner, name="Ember J3", sex="unknown", breed="New Zealand", color="Red",
                                         birth_date=today - datetime.timedelta(days=56), status="growing")
        Weight.objects.create(rabbit=self.kit, date=today, grams=1200)  # NZ curve at 8 wk: 1494 g, so 20% behind

    def test_table_by_default_chart_remembered(self):
        page = self.client.get(reverse("weights_hub"))
        self.assertEqual(page.context["view"], "table")
        self.assertEqual(page.context["rows"][0]["vs_tone"], "r")
        self.assertEqual(page.context["stats"]["behind"], 1)
        self.client.get(reverse("weights_hub"), {"view": "chart"})
        page = self.client.get(reverse("weights_hub"))
        self.assertEqual(page.context["view"], "chart")
        self.assertTrue(page.context["sel"]["chart"]["by_age"])

    def test_inline_log_and_weigh_a_group(self):
        res = self.client.post(reverse("weights_log", args=[self.kit.pk]), {"lb": "3", "oz": "2"}, HTTP_ACCEPT="application/json")
        self.assertTrue(res.json()["ok"])
        res = self.client.post(reverse("weights_log", args=[self.kit.pk]), {"lb": ""}, HTTP_ACCEPT="application/json")
        self.assertEqual(res.status_code, 400)
        self.client.post(reverse("weigh_group"), {"ids": str(self.kit.pk), f"w{self.kit.pk}-lb": "3", f"w{self.kit.pk}-oz": "6"})
        self.assertEqual(self.kit.weights.count(), 3)
