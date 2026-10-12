from django.test import TestCase

from . import genetics
from .models import Gene, OutsideRabbit, Relative
from .test_flow_rules import FlowTestMixin


class GeneticsTests(FlowTestMixin, TestCase):
    def parent(self, rabbit, relationship="dam", color="", genotype=None):
        outside = OutsideRabbit.objects.create(owner=self.user, name="Snow")
        row = Relative.objects.create(rabbit=rabbit, relationship=relationship, outside=outside, color=color)
        if genotype:
            Gene.objects.create(relative=row, locus="C", genotype=genotype, certainty="known")
        return row

    def test_genotypes_read_the_same_however_written(self):
        self.assertEqual(genetics.normalize(" c / c "), "cc")
        self.assertEqual(genetics.normalize("C/c"), "Cc")

    def test_an_albino_dam_by_color_suggests_a_c_carrier(self):
        self.parent(self.juniper, color="Ruby-Eyed White")
        note = genetics.c_carrier_suggestion(self.juniper)
        self.assertIn("Probable carrier of c (albino)", note)
        self.assertIn("dam, Snow, is c/c", note)

    def test_an_albino_sire_by_genes_suggests_a_c_carrier(self):
        self.parent(self.juniper, "sire", color="Black", genotype="c/c")
        self.assertIn("sire", genetics.c_carrier_suggestion(self.juniper))

    def test_a_herd_parent_counts_by_its_own_color(self):
        self.pepper.color = "REW"
        self.pepper.save()
        Relative.objects.create(rabbit=self.juniper, relationship="sire", herd_rabbit=self.pepper)
        self.assertIn("Pepper", genetics.c_carrier_suggestion(self.juniper))

    def test_no_note_without_an_albino_parent_or_once_handled(self):
        self.parent(self.juniper, color="Broken black")
        self.assertEqual(genetics.c_carrier_suggestion(self.juniper), "")
        self.parent(self.pepper, color="Ruby-eyed white")
        self.pepper.c_carrier_dismissed = True
        self.assertEqual(genetics.c_carrier_suggestion(self.pepper), "")
        self.pepper.c_carrier_dismissed = False
        Gene.objects.create(rabbit=self.pepper, locus="C", genotype="C/c", certainty="known")
        self.assertEqual(genetics.c_carrier_suggestion(self.pepper), "")

    def test_an_albino_kit_gets_no_carrier_note(self):
        self.juniper.color = "Ruby-eyed white"
        self.parent(self.juniper, color="Ruby-eyed white")
        self.assertEqual(genetics.c_carrier_suggestion(self.juniper), "")
