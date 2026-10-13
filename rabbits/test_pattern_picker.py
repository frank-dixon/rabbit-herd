"""The En locus on the genes card is a Solid / Broken / Charlie picker made
of plain radios, so it works without JavaScript."""

from django.test import TestCase
from django.urls import reverse

from . import flow
from .flow_views import pattern_choices
from .models import Rabbit
from .test_flow_rules import FlowTestMixin, breed_id


def step(slug):
    return reverse("rabbit_flow_step", args=[slug])


class PatternChoiceTests(TestCase):
    def test_each_pattern_names_one_genotype(self):
        values = {c["key"]: c["value"] for c in pattern_choices("")}
        self.assertEqual(values, {"none": "", "solid": "enen", "broken": "Enen", "charlie": "EnEn"})

    def test_a_filled_en_blank_stays_on_broken(self):
        broken = next(c for c in pattern_choices("En_") if c["key"] == "broken")
        self.assertEqual(broken["value"], "En_")
        self.assertTrue(broken["checked"])

    def test_an_odd_recorded_value_is_kept(self):
        last = pattern_choices("En/en?")[-1]
        self.assertEqual((last["key"], last["value"], last["checked"]), ("recorded", "En/en?", True))


class PickerFlowTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        session = self.client.session
        session[flow.SESSION_KEY] = self.draft(purebred=breed_id("Holland Lop"), color="Black", step="genes")
        session.save()

    def test_card_shows_three_patterns_as_radios(self):
        page = self.client.get(step("genes"))
        self.assertContains(page, "data-pattern-picker")
        for value in ("enen", "Enen", "EnEn"):
            self.assertContains(page, f'type="radio" name="gene_En" value="{value}"')
        self.assertNotContains(page, 'id="id_gene_En"')

    def test_choosing_charlie_without_javascript_saves_EnEn(self):
        self.client.get(step("genes"))
        draft = self.client.session[flow.SESSION_KEY]
        post = {key: draft[key] for key in flow.GENE_KEYS}
        post.update(gene_auto=draft["gene_auto"], gene_En="EnEn", action="next")
        self.assertRedirects(self.client.post(step("genes"), post), step("review"))
        self.client.post(step("review"), {"action": "next"})
        rabbit = Rabbit.objects.get(name="Hazel")
        self.assertEqual(rabbit.genes.get(locus="En").genotype, "EnEn")
