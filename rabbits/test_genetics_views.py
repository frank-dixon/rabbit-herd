from django.test import TestCase
from django.urls import reverse

from .models import Gene, OutsideRabbit, Relative
from .test_flow_rules import FlowTestMixin


class CarrierNoteTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        snow = OutsideRabbit.objects.create(owner=self.user, name="Snow")
        dam = Relative.objects.create(
            rabbit=self.juniper, relationship="dam", outside=snow, color="Ruby-eyed white", line="Ridgeview"
        )
        Gene.objects.create(relative=dam, locus="C", genotype="c/c", certainty="known")
        self.detail = reverse("rabbit_detail", args=[self.juniper.pk])
        self.action = reverse("rabbit_c_carrier", args=[self.juniper.pk])

    def test_the_detail_page_suggests_a_c_carrier_and_shows_parent_traits(self):
        page = self.client.get(self.detail)
        self.assertContains(page, "Probable carrier of c (albino)")
        self.assertContains(page, "Ruby-eyed white · Line Ridgeview")
        self.assertContains(page, "C: c/c (known)")

    def test_confirm_records_c_carrier_as_probable(self):
        self.client.post(self.action, {"action": "confirm"})
        gene = self.juniper.genes.get()
        self.assertEqual((gene.locus, gene.genotype, gene.certainty), ("C", "C/c", "probable"))
        page = self.client.get(self.detail)
        self.assertNotContains(page, "Suggested gene")
        self.assertContains(page, 'data-gene-level="probable"')
        self.assertContains(page, '<span class="font-mono ">C/c</span>', html=False)

    def test_remove_hides_the_note_for_good(self):
        self.client.post(self.action, {"action": "remove"})
        self.juniper.refresh_from_db()
        self.assertTrue(self.juniper.c_carrier_dismissed)
        self.assertFalse(self.juniper.genes.exists())
        self.assertNotContains(self.client.get(self.detail), "Suggested gene")

    def test_only_the_owner_and_only_by_post(self):
        self.assertEqual(self.client.get(self.action).status_code, 405)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.action, {"action": "confirm"}).status_code, 404)
        self.assertFalse(self.juniper.genes.exists())


class GenesPageTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.url = reverse("rabbit_genes", args=[self.juniper.pk])

    def test_genes_save_update_and_clear_without_javascript(self):
        self.assertRedirects(self.client.get(self.url), reverse("rabbit_edit_step", args=[self.juniper.pk, "genes"]))
        self.client.post(self.url, {"gene_C": "C/c", "cert_C": "known", "gene_other": "Vienna carrier"})
        self.assertEqual(
            sorted((g.locus, g.genotype, g.certainty) for g in self.juniper.genes.all()),
            [("C", "C/c", "known"), ("other", "Vienna carrier", "probable")],
        )
        self.client.post(self.url, {"gene_C": "C/c", "cert_C": "probable"})
        self.assertEqual([(g.locus, g.certainty) for g in self.juniper.genes.all()], [("C", "probable")])
        self.assertContains(self.client.get(reverse("rabbit_detail", args=[self.juniper.pk])), 'data-gene-level="probable"')

    def test_too_long_genotype_is_refused_and_others_cannot_open_it(self):
        response = self.client.post(self.url, {"gene_C": "x" * 41})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.juniper.genes.exists())
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_the_edit_page_has_the_line(self):
        edit = reverse("rabbit_edit_step", args=[self.juniper.pk, "line"])
        self.assertContains(self.client.get(edit), 'name="line"')


class EditGenesLinkTests(FlowTestMixin, TestCase):
    def test_detail_edit_genes_opens_the_genes_card(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse("rabbit_detail", args=[self.juniper.pk]))
        card = reverse("rabbit_edit_step", args=[self.juniper.pk, "genes"])
        self.assertContains(page, f'href="{card}"')
        self.assertContains(self.client.get(card), "data-pattern-picker")
