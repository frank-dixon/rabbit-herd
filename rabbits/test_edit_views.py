"""The edit pages: an overview with Change links to the add-a-rabbit cards."""

from django.test import TestCase
from django.urls import reverse

from . import flow
from .models import Breed, Rabbit
from .test_flow_rules import FlowTestMixin


def pk(name):
    return str(Breed.objects.get(name=name).pk)


class EditFlowTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.juniper.breed = "Cross: 50% Creme d'Argent, 25% Flemish Giant, 25% New Ze…"
        self.juniper.save()
        self.overview = reverse("rabbit_edit", args=[self.juniper.pk])

    def card(self, slug, rabbit=None):
        return reverse("rabbit_edit_step", args=[(rabbit or self.juniper).pk, slug])

    def test_overview_shows_answers_with_change_links(self):
        page = self.client.get(self.overview)
        self.assertContains(page, "Cross: 50% Creme d&#x27;Argent, 25% Flemish Giant, 25% New Zealand")
        for slug in flow.EDIT_SLUGS:
            self.assertContains(page, f'href="{self.card(slug)}"')
        self.assertNotContains(page, 'name="breed"')

    def test_breed_card_is_prefilled_with_mix_rows(self):
        page = self.client.get(self.card("breed"))
        self.assertContains(page, "Which breeds make up Juniper")
        self.assertContains(page, 'name="cross-2-percent"')
        self.assertContains(page, 'value="25"')

    def test_change_the_mix_then_save(self):
        self.client.post(self.card("breed"), {
            "cross-0-breed": pk("Creme d'Argent"), "cross-0-percent": "50",
            "cross-1-breed": pk("New Zealand"), "cross-1-percent": "25",
            "cross-2-breed": pk("New Zealand"), "cross-2-percent": "25", "action": "next",
        })
        page = self.client.get(self.overview)
        self.assertContains(page, "Cross: 50% Creme d&#x27;Argent, 50% New Zealand")
        self.client.post(self.overview, {"action": "save"})
        self.juniper.refresh_from_db()
        self.assertEqual(self.juniper.breed, "Cross: 50% Creme d'Argent, 50% New Zealand")
        self.assertEqual(self.juniper.breed_shares.count(), 2)
        self.assertNotIn(flow.edit_key(self.juniper.pk), self.client.session)

    def test_a_generational_mix_with_fractional_shares_saves(self):
        from decimal import Decimal

        card = self.client.get(self.card("breed"))
        self.assertContains(card, 'step="0.01"')
        self.assertContains(card, 'inputmode="decimal"')
        self.client.post(self.card("breed"), {
            "cross-0-breed": pk("Creme d'Argent"), "cross-0-percent": "75",
            "cross-1-breed": pk("Flemish Giant"), "cross-1-percent": "12.5",
            "cross-2-breed": pk("New Zealand"), "cross-2-percent": "12.5", "action": "next",
        })
        self.assertContains(self.client.get(self.overview), "Cross: 75% Creme d&#x27;Argent, 12.5% Flemish Giant, 12.5% New Zealand")
        self.client.post(self.overview, {"action": "save"})
        self.juniper.refresh_from_db()
        self.assertEqual(
            sorted(self.juniper.breed_shares.values_list("percent", flat=True)),
            [Decimal("12.5"), Decimal("12.5"), Decimal("75")],
        )
        self.assertContains(self.client.get(reverse("rabbit_detail", args=[self.juniper.pk])), "12.5% Flemish Giant")
        again = self.client.get(self.card("breed"))
        self.assertContains(again, 'value="12.5"')

    def test_one_breed_at_100_becomes_purebred_and_the_color_card_follows(self):
        nz = pk("New Zealand")
        done = self.client.post(self.card("breed"), {
            "cross-0-breed": nz, "cross-0-percent": "50", "cross-1-breed": nz, "cross-1-percent": "50",
            "cross-2-breed": "", "cross-2-percent": "", "action": "next",
        })
        self.assertRedirects(done, self.overview, fetch_redirect_response=False)
        self.assertContains(self.client.get(self.card("color")), "recognized colors for the New Zealand")

    def test_done_on_any_card_saves_it_and_returns_to_the_summary(self):
        draft = flow.load_draft({flow.edit_key(self.juniper.pk): flow.draft_from_rabbit(self.juniper)}, flow.edit_key(self.juniper.pk))
        changes = {"name": {"name": "June"}, "line": {"line": "Hollow Creek"}}
        for slug in flow.EDIT_SLUGS:
            data = flow.form_data(draft) | changes.get(slug, {}) | {"action": "next"}
            if slug == "relatives":
                data["relatives-count"] = "0"
            done = self.client.post(self.card(slug), data)
            self.assertRedirects(done, self.overview, fetch_redirect_response=False, msg_prefix=slug)
        page = self.client.get(self.overview)
        self.assertContains(page, "June")
        self.assertContains(page, "Hollow Creek")
        self.juniper.refresh_from_db()
        self.assertEqual(self.juniper.name, "Juniper", "Done keeps changes in the draft until Save")

    def test_done_with_a_problem_stays_on_the_card(self):
        done = self.client.post(self.card("name"), {"name": "", "action": "next"})
        self.assertRedirects(done, self.card("name") + "?check=1", fetch_redirect_response=False)

    def test_a_new_breed_type_asks_for_the_breed_on_the_same_card(self):
        done = self.client.post(self.card("breed-type"), {"breed_type": "purebred", "action": "next"}, follow=True)
        self.assertRedirects(done, self.card("breed-type") + "?check=1")
        self.assertContains(done, 'data-breed-section="purebred">')

    def test_unreadable_legacy_breed_asks_for_the_breed(self):
        self.pepper.breed = "barn mix"
        self.pepper.save()
        page = self.client.get(reverse("rabbit_edit", args=[self.pepper.pk]))
        self.assertContains(page, "doesn't match the breed list")
        self.assertRedirects(
            self.client.get(self.card("breed", self.pepper)), self.card("breed-type", self.pepper) + "?check=1"
        )
        saved = self.client.post(reverse("rabbit_edit", args=[self.pepper.pk]), {"action": "save"})
        self.assertRedirects(saved, self.card("breed-type", self.pepper) + "?check=1")

    def test_back_and_cancel_keep_the_rabbit_unchanged(self):
        self.client.post(self.card("name"), {"name": "Other", "action": "back"})
        self.assertContains(self.client.get(self.overview), "changes that aren")
        self.client.post(self.overview, {"action": "discard"})
        self.juniper.refresh_from_db()
        self.assertEqual(self.juniper.name, "Juniper")
        self.assertNotContains(self.client.get(self.overview), "changes that aren")

    def test_drafts_are_kept_per_rabbit(self):
        self.client.post(self.card("name"), {"name": "June", "action": "next"})
        self.assertContains(self.client.get(reverse("rabbit_edit", args=[self.pepper.pk])), "Pepper")
        self.assertContains(self.client.get(self.overview), "June")

    def test_a_rabbit_cannot_be_its_own_relative(self):
        self.client.post(self.card("relatives"), {"action": "add-relative"})
        page = self.client.post(self.card("relatives"), {
            "relatives-0-relationship": "sibling", "relatives-0-ref": f"h:{self.juniper.pk}", "action": "next",
        }, follow=True)
        self.assertContains(page, "can&#x27;t be its own relative")
        self.assertNotContains(self.client.get(self.card("relatives")), f'value="h:{self.juniper.pk}"')

    def test_only_the_owner_can_open_or_save(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.overview).status_code, 404)
        self.assertEqual(self.client.get(self.card("breed")).status_code, 404)
        self.assertEqual(self.client.post(self.overview, {"action": "save"}).status_code, 404)
        self.assertEqual(self.client.post(self.card("name"), {"name": "x"}).status_code, 404)

    def test_unknown_card_is_404(self):
        self.assertEqual(self.client.get(self.card("review")).status_code, 404)
