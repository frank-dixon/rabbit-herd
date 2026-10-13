"""Today, herd first: herd cards, former herd, tiles, pairing progress, weights."""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rabbits.models import Litter, Pairing, Rabbit, Task, Weight


class TodayHerdFirstTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="t@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        mk = lambda name, **kw: Rabbit.objects.create(owner=self.user, name=name, birth_date="2024-03-10", **{"sex": "doe", "status": "breeding", **kw})
        self.willow, self.jet = mk("Willow"), mk("Jet", sex="buck")
        self.sold, self.culled = mk("Lily", status="sold"), mk("Juniper", status="culled", death_date=self.today - datetime.timedelta(days=20))
        pairing = Pairing.objects.create(owner=self.user, doe=self.willow, buck=self.jet)
        self.litter = Litter.objects.create(owner=self.user, pairing=pairing, bred_on=self.today - datetime.timedelta(days=10))
        Weight.objects.create(rabbit=self.jet, date=self.today - datetime.timedelta(days=9), grams=4000)
        Weight.objects.create(rabbit=self.jet, date=self.today - datetime.timedelta(days=2), grams=4113)
        Task.objects.create(owner=self.user, title="Trim nails", due_on=self.today - datetime.timedelta(days=1), rabbit=self.willow)

    def test_sections_use_real_data(self):
        page = self.client.get(reverse("index"))
        c = page.context
        self.assertEqual([card["rabbit"].name for card in c["herd_cards"]], ["Willow", "Jet"])
        self.assertEqual(c["herd_cards"][0]["chip"], "Bred")
        self.assertTrue(c["herd_cards"][0]["overdue"])
        self.assertIn("Weighed", c["herd_cards"][1]["next"])
        self.assertEqual({chip["rabbit"].name for chip in c["former_chips"]}, {"Lily", "Juniper"})
        tiles = c["tiles"]
        self.assertEqual((tiles["herd"], tiles["bucks"], tiles["does"], tiles["bred"], tiles["sold"], tiles["culled"]), (2, 1, 1, 1, 1, 1))
        self.assertEqual(tiles["next_kindling"]["due"], self.litter.due_on)
        self.assertEqual([s["label"] for s in c["pairings_progress"][0]["steps"]], ["Bred", "Palpate", "Due"])
        self.assertEqual(c["recent_weights"][0]["delta"], "+4 oz")
        self.assertContains(page, "Overdue and today")
        self.assertContains(page, "data-quick-done")
        self.assertContains(page, "Willow × Jet")

    def test_former_and_sold_rabbits_never_show_as_herd_cards(self):
        names = [card["rabbit"].name for card in self.client.get(reverse("index")).context["herd_cards"]]
        self.assertNotIn("Lily", names)
        self.assertNotIn("Juniper", names)


class TodayCountsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="c@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        mk = lambda name, status: Rabbit.objects.create(owner=self.user, name=name, sex="doe", birth_date="2024-03-10", status=status)
        self.a, self.b = mk("Basil", "breeding"), mk("Fern", "growing")
        mk("Juniper", "culled")
        mk("Lily", "sold")

    def test_culled_and_sold_rabbits_are_not_counted_as_the_herd(self):
        page = self.client.get(reverse("index"))
        self.assertEqual(page.context["herd"]["active"], 2)
        self.assertEqual(page.context["tiles"]["herd"], 2)
        self.assertContains(page, "2 rabbits</a> · 2 does · 0 bucks · 1 breeding · 1 growing out")

    def test_recent_weights_show_one_row_per_rabbit(self):
        today = timezone.localdate()
        for days in range(4):
            Weight.objects.create(rabbit=self.a, date=today - datetime.timedelta(days=days), grams=4000 + days)
        Weight.objects.create(rabbit=self.b, date=today - datetime.timedelta(days=9), grams=3000)
        rows = self.client.get(reverse("index")).context["recent_weights"]
        self.assertEqual([r["rabbit"].name for r in rows], ["Basil", "Fern"])
