"""Compare siblings: growth chart and kit cards for one litter."""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CullNote, Litter, Pairing, Rabbit, Weight
from .siblings import at_age


class SiblingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="sib@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        born = datetime.date(2026, 6, 1)
        mk = lambda name, sex, **kw: Rabbit.objects.create(owner=self.user, name=name, sex=sex, breed="Rex",
                                                           birth_date=kw.pop("birth_date", datetime.date(2024, 1, 1)), **kw)
        pairing = Pairing.objects.create(owner=self.user, doe=mk("Magnolia", "doe"), buck=mk("Ash", "buck"))
        self.litter = Litter.objects.create(owner=self.user, pairing=pairing, bred_on=born - datetime.timedelta(days=31), kindled_on=born)
        self.juniper = mk("Juniper", "doe", litter=self.litter, birth_date=born)
        self.rowan = mk("Rowan", "buck", litter=self.litter, birth_date=born)
        self.wren = mk("Wren", "doe", litter=self.litter, birth_date=born)
        for kit, grams in ((self.juniper, (100, 1000, 2270)), (self.rowan, (100, 950, 2100))):
            for day, g in zip((0, 28, 56), grams):
                Weight.objects.create(rabbit=kit, date=born + datetime.timedelta(days=day), grams=g)
        CullNote.objects.create(rabbit=self.rowan, date=born + datetime.timedelta(days=56), decision="keep", reason="Good shoulders")
        self.url = reverse("litter_siblings", args=[self.litter.pk])

    def test_chart_cards_ranks_and_milestones(self):
        page = self.client.get(self.url)
        body = page.content.decode()
        self.assertContains(page, "data-growth-chart")
        self.assertContains(page, "Age (weeks)")
        self.assertContains(page, "Weight (lb)")
        self.assertContains(page, 'data-series="avg"')
        self.assertEqual(body.count("data-kit-card>"), 3)
        # Juniper is heaviest, so first and rank 1; Wren has no weights and comes last, unranked.
        self.assertLess(body.index(">Juniper<"), body.index(">Rowan<"))
        self.assertLess(body.index(">Rowan<", body.index("data-kit-cards")), body.index(">Wren<", body.index("data-kit-cards")))
        self.assertContains(page, "Rank 1 of 2")
        self.assertContains(page, "5.0")  # Juniper at 8 weeks, in lb
        self.assertContains(page, "Good shoulders")
        self.assertContains(page, f'href="{reverse("litter_weigh_in", args=[self.litter.pk])}"')

    def test_sort_by_name_and_legend_works_without_js(self):
        body = self.client.get(self.url + "?sort=name").content.decode()
        cards = body[body.index("data-kit-cards"):]
        self.assertLess(cards.index(">Juniper<"), cards.index(">Rowan<"))
        self.assertIn('type="checkbox" id="series-0" checked', body)
        self.assertIn(':has(#series-0:not(:checked)) [data-series="0"]', body)

    def test_litter_page_links_here_and_strangers_get_404(self):
        self.assertContains(self.client.get(reverse("litter_detail", args=[self.litter.pk])), f'href="{self.url}"')
        other = get_user_model().objects.create_user(email="sib2@example.com", password="x-strong-Pass-1")
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_interpolates_between_weighings_only(self):
        points = [(0, 100), (28, 1000)]
        self.assertEqual(at_age(points, 14), 550)
        self.assertIsNone(at_age(points, 35))
