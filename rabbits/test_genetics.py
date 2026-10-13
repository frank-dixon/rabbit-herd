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


class HiddenNotesTests(TestCase):
    def test_notes_from_genotype(self):
        from . import genetics as g
        notes = " ".join(g.hidden_notes({"C": ("c", "c"), "A": ("A", "a"), "E": ("E", "e")}))
        self.assertIn("hides whatever it carries at A, B, D, E, V and Si", notes)
        self.assertIn("Carries red (e)", notes)
        notes = " ".join(g.hidden_notes({"A": ("a", "a"), "E": ("Es", "E"), "Si": ("Si", "si"), "V": ("V", "v")}))
        self.assertIn("steel (Es)", notes)
        self.assertIn("silvering (si)", notes)
        self.assertIn("Vienna (v)", notes)
        self.assertEqual(g.hidden_notes({"A": ("a", "a"), "C": ("C", "C")}), [])

    def test_shown_on_rabbit_and_pairing_pages(self):
        import datetime
        from django.urls import reverse
        from .models import Gene, Pairing, Rabbit
        from .test_contacts import user
        owner = user("hidden@example.com")
        self.client.force_login(owner)
        base = {"owner": owner, "breed": "New Zealand", "color": "White", "birth_date": datetime.date(2025, 1, 1)}
        doe = Rabbit.objects.create(name="Snow", sex="doe", **base)
        buck = Rabbit.objects.create(name="Coal", sex="buck", **base)
        Gene.objects.create(rabbit=doe, locus="C", genotype="c/c", certainty="known")
        Gene.objects.create(rabbit=buck, locus="E", genotype="E/e", certainty="known")
        page = self.client.get(reverse("rabbit_detail", args=[doe.pk]))
        self.assertContains(page, "data-hidden-notes")
        pairing = Pairing.objects.create(owner=owner, doe=doe, buck=buck)
        page = self.client.get(reverse("pairing_detail", args=[pairing.pk]))
        self.assertContains(page, "Snow: c/c (ruby-eyed white)")
        self.assertContains(page, "Coal: Carries red (e)")


class CarrierOddsTests(FlowTestMixin, TestCase):
    def parents(self, dam_c, sire_c):
        for relationship, genotype in (("dam", dam_c), ("sire", sire_c)):
            outside = OutsideRabbit.objects.create(owner=self.user, name=relationship.title())
            row = Relative.objects.create(rabbit=self.juniper, relationship=relationship, outside=outside)
            Gene.objects.create(relative=row, locus="C", genotype=genotype, certainty="known")

    def test_two_thirds_when_showing_full_color_from_two_carriers(self):
        self.parents("C/c", "C/c")
        Gene.objects.create(rabbit=self.juniper, locus="C", genotype="C_", certainty="known")
        self.assertEqual(genetics.carrier_odds(self.juniper),
                         ["C: 2/3 chance of carrying c, from Dam C/c × Sire C/c."])

    def test_half_without_a_recorded_gene(self):
        self.parents("C/C", "C/c")
        self.assertEqual(genetics.carrier_odds(self.juniper),
                         ["C: 1/2 chance of carrying c, from Dam C/C × Sire C/c."])

    def test_nothing_when_known_or_parents_missing(self):
        self.assertEqual(genetics.carrier_odds(self.juniper), [])
        self.parents("C/c", "C/c")
        Gene.objects.create(rabbit=self.juniper, locus="C", genotype="C/C", certainty="known")
        self.assertEqual(genetics.carrier_odds(self.juniper), [])

    def test_shown_on_rabbit_page(self):
        self.parents("C/c", "C/c")
        self.client.force_login(self.user)
        from django.urls import reverse
        page = self.client.get(reverse("rabbit_detail", args=[self.juniper.pk]))
        self.assertContains(page, "Carrier odds from the parents")


class TestMateTests(FlowTestMixin, TestCase):
    def test_suggests_a_homozygous_recessive_mate(self):
        Gene.objects.create(rabbit=self.juniper, locus="C", genotype="C_", certainty="known")
        Gene.objects.create(rabbit=self.pepper, locus="C", genotype="c/c", certainty="known")
        [item] = genetics.test_mates(self.juniper)
        self.assertEqual(item["mates"], ["Pepper"])
        self.assertIn("Pair with Pepper (c/c)", item["note"])

    def test_says_when_no_mate_can_test(self):
        Gene.objects.create(rabbit=self.juniper, locus="D", genotype="D/d", certainty="probable")
        Gene.objects.create(rabbit=self.juniper, locus="A", genotype="a/a", certainty="known")
        [item] = genetics.test_mates(self.juniper)
        self.assertEqual(item["locus"], "D")
        self.assertIn("No d/d buck recorded", item["note"])

    def test_known_genes_need_no_test(self):
        Gene.objects.create(rabbit=self.juniper, locus="B", genotype="B/B", certainty="known")
        self.assertEqual(genetics.test_mates(self.juniper), [])

    def test_shown_on_rabbit_page(self):
        Gene.objects.create(rabbit=self.juniper, locus="C", genotype="C_", certainty="known")
        self.client.force_login(self.user)
        from django.urls import reverse
        self.assertContains(self.client.get(reverse("rabbit_detail", args=[self.juniper.pk])), "To confirm")
