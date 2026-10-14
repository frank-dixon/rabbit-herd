"""The genes card fills a rabbit's genes from its breed, color and eye
color, in the add and edit flows, without overwriting what people set."""

from django.test import TestCase
from django.urls import reverse

from . import flow
from .models import Gene, Rabbit, Relative
from .test_flow_rules import FlowTestMixin, breed_id


def step(slug):
    return reverse("rabbit_flow_step", args=[slug])


def genes(rabbit):
    return {gene.locus: gene.genotype for gene in rabbit.genes.all()}


class FillRuleTests(FlowTestMixin, TestCase):
    def test_empty_loci_fill_and_are_marked(self):
        draft = self.draft(purebred=breed_id("Creme d'Argent"), color_choice="Creme", color="")
        filled = flow.fill_genes(draft, self.user)
        self.assertEqual(draft["gene_E"], "ee")
        self.assertIn("E", filled)
        self.assertIn("E=ee", draft["gene_auto"])

    def test_eye_color_follows_the_genes_until_it_is_picked(self):
        draft = self.draft(purebred=breed_id("Florida White"), color_choice="", color="White")
        flow.fill_genes(draft, self.user)
        self.assertEqual(draft["eye_color"], "ruby")  # cc
        self.assertIn("eye=ruby", draft["gene_auto"])
        draft["eye_color"] = "brown"  # the keeper's answer wins from here on
        flow.fill_genes(draft, self.user)
        self.assertEqual(draft["eye_color"], "brown")
        self.assertNotIn("eye=", draft["gene_auto"])

    def test_a_value_set_by_hand_is_never_replaced(self):
        draft = self.draft(purebred=breed_id("Creme d'Argent"), color_choice="Creme", color="", gene_E="Ee")
        flow.fill_genes(draft, self.user)
        self.assertEqual(draft["gene_E"], "Ee")
        self.assertNotIn("E=", draft["gene_auto"])

    def test_a_changed_filled_value_becomes_the_keepers(self):
        draft = self.draft(purebred=breed_id("Holland Lop"), color="Black")
        flow.fill_genes(draft, self.user)
        self.assertEqual(draft["gene_A"], "aa")
        draft["gene_B"] = "Bb"
        draft["color"] = "Lilac"
        flow.fill_genes(draft, self.user)
        self.assertEqual(draft["gene_B"], "Bb")
        self.assertEqual(draft["gene_D"], "dd")

    def test_ruby_eyes_on_white_refill_to_cc(self):
        draft = self.draft(purebred=breed_id("Holland Lop"), color="White")
        flow.fill_genes(draft, self.user)
        self.assertEqual(draft["gene_C"], "")
        draft["eye_color"] = "ruby"
        flow.fill_genes(draft, self.user)
        self.assertEqual(draft["gene_C"], "cc")

    def test_a_listed_ruby_eyed_white_reads_its_hint(self):
        draft = self.draft(purebred=breed_id("New Zealand"), color_choice="White", color="")
        flow.fill_genes(draft, self.user)
        self.assertEqual(draft["gene_C"], "cc")

    def test_a_recessive_parent_narrows(self):
        dam = self.rabbit("Dam", "doe")
        Gene.objects.create(rabbit=dam, locus="D", genotype="dd", certainty="known")
        draft = self.draft(color="Black")
        draft["relatives"] = [dict(flow.blank_relative(), relationship="dam", ref=f"h:{dam.pk}")]
        flow.fill_genes(draft, self.user)
        self.assertEqual(draft["gene_D"], "Dd")


class AddFlowTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        session = self.client.session
        session[flow.SESSION_KEY] = self.draft(
            purebred=breed_id("Creme d'Argent"), color_choice="Creme", color="", step="genes"
        )
        session.save()

    def test_card_shows_dropdowns_filled_from_the_breed(self):
        page = self.client.get(step("genes"))
        self.assertContains(page, "Which genes does Hazel carry?")
        self.assertContains(page, '<option value="ee" selected>ee</option>', html=False)
        self.assertContains(page, "Empty dropdowns were filled from Creme d&#x27;Argent, Creme.")
        self.assertContains(page, 'value="fill"')

    def test_save_without_javascript_keeps_hand_choices(self):
        self.client.get(step("genes"))
        draft = self.client.session[flow.SESSION_KEY]
        post = {key: draft[key] for key in flow.GENE_KEYS}
        post.update(gene_auto=draft["gene_auto"], eye_color="brown", gene_A="AA", action="next")
        self.assertRedirects(self.client.post(step("genes"), post), step("relatives"))
        self.assertRedirects(self.client.post(step("relatives"), {"action": "next"}), step("review"))
        self.client.post(step("review"), {"action": "next"})
        rabbit = Rabbit.objects.get(name="Hazel")
        self.assertEqual(rabbit.eye_color, "brown")
        saved = {gene.locus: gene for gene in rabbit.genes.all()}
        self.assertEqual(saved["A"].genotype, "AA")
        self.assertEqual(saved["A"].certainty, "probable")
        self.assertEqual(saved["E"].genotype, "ee")
        self.assertEqual(saved["E"].certainty, "known")
        self.assertEqual(saved["Si"].genotype, "sisi")

    def test_skipping_the_card_still_fills_on_save(self):
        session = self.client.session
        session[flow.SESSION_KEY] = dict(session[flow.SESSION_KEY], step="review")
        session.save()
        self.client.post(step("review"), {"action": "next"})
        self.assertEqual(genes(Rabbit.objects.get(name="Hazel"))["En"], "enen")

    def test_unreadable_long_text_is_refused(self):
        response = self.client.post(step("genes"), {"gene_A": "x" * 41, "action": "next"})
        self.assertRedirects(response, step("genes") + "?check=1")


class EditFlowTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        Gene.objects.create(rabbit=self.juniper, locus="B", genotype="B/b", certainty="known")

    def card(self, slug):
        return reverse("rabbit_edit_step", args=[self.juniper.pk, slug])

    def test_edit_card_keeps_recorded_genes_and_fills_the_rest(self):
        page = self.client.get(self.card("genes"))
        self.assertContains(page, '<option value="Bb" selected>Bb</option>', html=False)
        self.assertContains(page, '<option value="aa" selected>aa</option>', html=False)
        self.client.post(reverse("rabbit_edit", args=[self.juniper.pk]), {"action": "save"})
        saved = {gene.locus: gene for gene in self.juniper.genes.all()}
        self.assertEqual(saved["B"].genotype, "B/b")
        self.assertEqual(saved["B"].certainty, "known")
        self.assertEqual(saved["A"].genotype, "aa")

    def test_overview_lists_genes(self):
        self.assertContains(self.client.get(reverse("rabbit_edit", args=[self.juniper.pk])), self.card("genes"))

    def test_a_draft_from_before_the_genes_card_keeps_recorded_genes(self):
        key = flow.edit_key(self.juniper.pk)
        old = flow.draft_from_rabbit(self.juniper)
        for name in flow.GENE_KEYS + ("eye_color", "gene_auto"):
            old.pop(name)
        session = self.client.session
        session[key] = old
        session.save()
        self.client.get(self.card("genes"))
        self.client.post(reverse("rabbit_edit", args=[self.juniper.pk]), {"action": "save"})
        self.assertEqual(genes(self.juniper)["B"], "B/b")

    def test_a_filled_value_never_replaces_a_saved_gene(self):
        self.client.get(self.card("genes"))
        Gene.objects.create(rabbit=self.juniper, locus="A", genotype="Aa", certainty="known")
        self.client.post(reverse("rabbit_edit", args=[self.juniper.pk]), {"action": "save"})
        self.assertEqual(genes(self.juniper)["A"], "Aa")
