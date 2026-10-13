import datetime

from django.test import TestCase
from django.urls import reverse

from .models import Litter, Pairing, Rabbit, Weight
from .test_contacts import user


class WeighInTests(TestCase):
    def setUp(self):
        self.owner = user("weigh@example.com")
        self.client.force_login(self.owner)
        born = datetime.date(2026, 9, 1)
        base = {"owner": self.owner, "breed": "Dutch", "color": "Black"}
        doe = Rabbit.objects.create(name="Mom", sex="doe", birth_date=datetime.date(2024, 1, 1), **base)
        buck = Rabbit.objects.create(name="Dad", sex="buck", birth_date=datetime.date(2024, 1, 1), **base)
        self.litter = Litter.objects.create(owner=self.owner, pairing=Pairing.objects.create(owner=self.owner, doe=doe, buck=buck),
                                            bred_on=datetime.date(2026, 8, 1), kindled_on=born, born_alive=2)
        self.ash = Rabbit.objects.create(name="Ash", sex="doe", birth_date=born, litter=self.litter, **base)
        self.birch = Rabbit.objects.create(name="Birch", sex="buck", birth_date=born, litter=self.litter, **base)
        self.url = reverse("litter_weigh_in", args=[self.litter.pk])

    def test_first_kit_with_keypad_and_link(self):
        page = self.client.get(self.url)
        self.assertContains(page, "data-keypad")
        self.assertContains(page, 'inputmode="decimal"')
        self.assertEqual(page.context["kit"], self.ash)
        self.assertContains(self.client.get(reverse("litter_detail", args=[self.litter.pk])), "data-weigh-link")

    def test_save_steps_on_and_replaces_same_day(self):
        response = self.client.post(self.url, {"kit": 0, "value": "150", "unit": "g"})
        self.assertIn("kit=1", response["Location"])
        self.client.post(self.url, {"kit": 0, "value": "160", "unit": "g"})
        self.assertEqual(list(self.ash.weights.values_list("grams", flat=True)), [160])

    def test_ounces_convert(self):
        self.client.post(self.url, {"kit": 0, "value": "2", "unit": "oz"})
        self.assertEqual(self.ash.weights.get().grams, 57)

    def test_skip_on_last_kit_returns_to_litter(self):
        response = self.client.post(self.url, {"kit": 1, "skip": "1", "unit": "g"})
        self.assertTrue(response["Location"].endswith(reverse("litter_detail", args=[self.litter.pk]) + "#kits"))
        self.assertFalse(Weight.objects.exists())

    def test_bad_value_is_flagged(self):
        page = self.client.post(self.url, {"kit": 0, "value": "abc", "unit": "g"})
        self.assertContains(page, 'aria-invalid="true"')
        self.assertFalse(Weight.objects.exists())

    def test_owner_only(self):
        self.client.force_login(user("other@example.com"))
        self.assertEqual(self.client.get(self.url).status_code, 404)
