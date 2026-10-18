"""Critic v3 L3/L4: the litter page's back link goes where the user came from (Litters by default),
and every displayed date uses the one shared style (the |day filter)."""
import datetime
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Litter, Pairing, Rabbit

ROOT = Path(__file__).resolve().parents[1]


class LitterBackTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("back@example.com", "pw-12345678")
        self.client.force_login(user)
        self.doe = Rabbit.objects.create(owner=user, name="Willow", sex="doe", breed="Rex", birth_date=datetime.date(2024, 1, 1))
        buck = Rabbit.objects.create(owner=user, name="Jet", sex="buck", breed="Rex", birth_date=datetime.date(2024, 1, 1))
        self.pairing = Pairing.objects.create(owner=user, doe=self.doe, buck=buck)
        self.litter = Litter.objects.create(owner=user, pairing=self.pairing, bred_on=datetime.date(2025, 9, 19))
        self.url = reverse("litter_detail", args=[self.litter.pk])

    def back(self, referer=None):
        extra = {"HTTP_REFERER": f"http://testserver{referer}"} if referer else {}
        page = self.client.get(self.url, **extra)
        return page.context["back_label"], page.context["back_href"]

    def test_defaults_to_litters(self):
        self.assertEqual(self.back(), ("Litters", reverse("litter_list")))
        self.assertEqual(self.back(reverse("litter_list") + "?archived=1"), ("Litters", reverse("litter_list")))

    def test_returns_to_where_the_user_came_from(self):
        pairing = reverse("pairing_detail", args=[self.pairing.pk])
        self.assertEqual(self.back(pairing), ("Pairing", pairing))
        self.assertEqual(self.back("/"), ("Today", "/"))
        doe = reverse("rabbit_detail", args=[self.doe.pk])
        self.assertEqual(self.back(doe), ("Willow", doe))

    def test_another_site_is_ignored(self):
        page = self.client.get(self.url, HTTP_REFERER="https://example.org/")
        self.assertEqual(page.context["back_label"], "Litters")

    def test_dates_share_one_style(self):
        body = self.client.get(self.url).content.decode()
        self.assertIn("Litter bred Fri, Sep 19, 2025", body)
        self.assertIn("Bred Fri, Sep 19, 2025 ·", body)
        self.assertNotIn("Friday", body)


class OneDateStyleTests(SimpleTestCase):
    def test_templates_show_dates_through_the_day_filter(self):
        for path in (ROOT / "templates").rglob("*.html"):
            for fmt in re.findall(r"""\|date:["']([^"']+)["']""", path.read_text()):
                self.assertIn(fmt, ("Y-m-d", "c"), f"{path.name} formats a date as {fmt!r}; use |day")


class LitterPlaceholderTests(TestCase):
    setUp = LitterBackTests.setUp

    def test_no_photo_uses_the_plain_placeholder(self):
        # Frank, 2026-10-18: the litter card uses the app's one plain placeholder, not a stock newborn photo.
        from .litters import litter_main_card

        self.assertIsNone(litter_main_card(self.litter, [], [], "g")["img"])
        self.litter.kindled_on = datetime.date(2025, 10, 20)
        self.litter.born_alive = 2
        self.litter.save()
        body = self.client.get(self.url).content.decode()
        self.assertNotIn("Stock newborn photo", body)
        self.assertNotIn("data-placeholder-tag", body)
        if "data-litter-card" in body:
            self.assertIn("coat-swatch", body.split('data-photo-target="litter"', 1)[1][:600])
