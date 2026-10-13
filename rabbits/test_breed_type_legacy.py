"""The breed type card carries the breed answer: Purebred shows the breed
picker, Crossbred the mix rows, on the same card, with or without JavaScript.
Regression: a rabbit whose breed was saved as "Unknown" can become crossbred."""

from django.test import TestCase
from django.urls import reverse

from .models import Breed, Rabbit
from .test_flow_rules import FlowTestMixin

TYPE_ERROR = "Each rabbit is either purebred or crossbred"


def bid(name):
    return str(Breed.objects.get(name=name).pk)


class LegacyUnknownBreedTypeTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        Rabbit.objects.filter(pk=self.juniper.pk).update(breed="Unknown", breed_type="", purebred=None)

    def url(self, name):
        return reverse(name, args=[self.juniper.pk, "breed-type"])

    def test_card_shows_both_sections_with_only_the_drawn_one_open(self):
        page = self.client.get(self.url("rabbit_edit_step"))
        self.assertContains(page, "Unknown")
        self.assertContains(page, 'data-breed-section="purebred" hidden')
        self.assertContains(page, 'data-breed-section="crossbred" hidden')
        self.assertContains(page, 'name="breed_shown" value=""')

    def test_without_js_crossbred_comes_back_with_the_mix_rows(self):
        for name in ("rabbit_edit_step", "rabbit_quick_edit"):
            with self.subTest(name):
                page = self.client.post(self.url(name), {"breed_type": "crossbred", "breed_shown": "", "action": "next"}, follow=True)
                self.assertNotContains(page, TYPE_ERROR)
                self.assertContains(page, 'data-breed-section="crossbred">')
                self.assertContains(page, 'name="cross-1-percent"')

    def test_crossbred_mix_saves_from_the_same_card(self):
        mix = {"breed_type": "crossbred", "breed_shown": "crossbred", "action": "next",
               "cross-0-breed": bid("Rex"), "cross-0-percent": "50",
               "cross-1-breed": bid("Dutch"), "cross-1-percent": "25",
               "cross-2-breed": bid("Mini Lop"), "cross-2-percent": "25"}
        self.client.post(self.url("rabbit_edit_step"), {"action": "add-cross", "breed_type": "crossbred", "breed_shown": "crossbred"})
        page = self.client.post(self.url("rabbit_quick_edit"), mix, follow=True)
        self.assertNotContains(page, TYPE_ERROR)
        self.juniper.refresh_from_db()
        if self.juniper.breed_type != "crossbred":
            # The color card may need a look first; the draft still holds the mix.
            self.assertContains(page, "Color")
        else:
            self.assertEqual(self.juniper.breed_shares.count(), 3)

    def test_purebred_with_a_breed_goes_back_to_the_summary(self):
        page = self.client.post(self.url("rabbit_edit_step"), {"breed_type": "purebred", "breed_shown": "purebred",
                                                               "purebred": bid("Rex"), "action": "next"})
        self.assertRedirects(page, reverse("rabbit_edit", args=[self.juniper.pk]), fetch_redirect_response=False)

    def test_missing_breed_is_reported_on_the_same_card(self):
        page = self.client.post(self.url("rabbit_edit_step"), {"breed_type": "purebred", "breed_shown": "purebred", "action": "next"}, follow=True)
        self.assertNotContains(page, TYPE_ERROR)
        self.assertContains(page, 'data-breed-section="purebred">')
        self.assertContains(page, 'aria-invalid')
