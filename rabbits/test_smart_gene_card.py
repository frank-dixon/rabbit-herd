"""The smart genes card lists every locus with a certainty level."""

from django.test import TestCase
from django.urls import reverse

from . import gene_card
from .models import Gene
from .test_flow_rules import FlowTestMixin


class SmartGeneCardTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.bun = self.rabbit("Bun", "doe")
        self.bun.breed, self.bun.color = "Creme d'Argent", "Creme"
        self.bun.save()

    def levels(self):
        return {row["locus"]: (row["level"], row["genotype"]) for row in gene_card.rows(self.bun)}

    def test_recorded_genes_keep_their_certainty(self):
        Gene.objects.create(rabbit=self.bun, locus="D", genotype="Dd", certainty="known")
        Gene.objects.create(rabbit=self.bun, locus="B", genotype="Bb", certainty="probable")
        levels = self.levels()
        self.assertEqual(levels["D"], ("known", "Dd"))
        self.assertEqual(levels["B"], ("probable", "Bb"))

    def test_breed_and_color_fill_gaps_as_possible(self):
        levels = self.levels()
        self.assertEqual(levels["E"], ("possible", "ee"))
        self.bun.breed, self.bun.color = "", ""
        self.assertEqual(self.levels()["V"], ("unknown", ""))

    def test_summary_skips_zero_levels(self):
        Gene.objects.create(rabbit=self.bun, locus="D", genotype="Dd", certainty="known")
        text = gene_card.summary(gene_card.rows(self.bun))
        self.assertTrue(text.startswith("1 known · "))
        self.assertNotIn("probable", text)

    def test_detail_page_shows_every_locus_and_the_legend(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse("rabbit_detail", args=[self.bun.pk]))
        self.assertContains(page, "data-gene-card")
        self.assertContains(page, 'data-gene-level="possible"')
        self.assertContains(page, "What the levels mean")
        self.assertContains(page, "From breed and color")

    def test_nothing_recorded_or_implied_keeps_the_short_empty_state(self):
        self.bun.breed, self.bun.color = "", ""
        self.bun.save()
        self.client.force_login(self.user)
        page = self.client.get(reverse("rabbit_detail", args=[self.bun.pk]))
        self.assertContains(page, "No genes recorded.")
        self.assertNotContains(page, "data-gene-card")
