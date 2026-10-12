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
        self.assertContains(page, "Snow · Ruby-eyed white, Ridgeview")
        self.assertContains(page, "C: c/c (known)")

    def test_confirm_records_c_carrier_as_probable(self):
        self.client.post(self.action, {"action": "confirm"})
        gene = self.juniper.genes.get()
        self.assertEqual((gene.locus, gene.genotype, gene.certainty), ("C", "C/c", "probable"))
        page = self.client.get(self.detail)
        self.assertNotContains(page, "Suggested gene")
        self.assertContains(page, "C: C/c (probable)")

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
