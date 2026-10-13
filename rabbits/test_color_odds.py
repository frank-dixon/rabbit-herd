import datetime

from django.test import TestCase
from django.urls import reverse

from . import color_odds
from .models import Gene, Pairing, Rabbit
from .test_contacts import user


class ParseTests(TestCase):
    def test_genotypes_read_however_written(self):
        self.assertEqual(color_odds.parse("A", "A/at"), ("A", "at"))
        self.assertEqual(color_odds.parse("A", "A at"), ("A", "at"))
        self.assertEqual(color_odds.parse("C", "cchdc"), ("cchd", "c"))
        self.assertEqual(color_odds.parse("En", "Enen"), ("En", "en"))
        self.assertEqual(color_odds.parse("B", "B/?"), ("B", "_"))
        self.assertEqual(color_odds.parse("B", "B"), ("B", "_"))
        self.assertIsNone(color_odds.parse("A", "zz"))
        self.assertIsNone(color_odds.parse("D", "D/d/d"))

    def test_punnett_square(self):
        odds = color_odds.cross("C", ("C", "c"), ("C", "c"))
        self.assertEqual({k: float(v) for k, v in odds.items()}, {("C", "C"): .25, ("C", "c"): .5, ("c", "c"): .25})

    def test_names(self):
        name = color_odds.color_name
        self.assertEqual(name("A", "B", "C", "D", "E"), "Chestnut")
        self.assertEqual(name("a", "b", "C", "d", "E"), "Lilac")
        self.assertEqual(name("at", "B", "C", "D", "E"), "Black otter")
        self.assertEqual(name("A", "B", "cchd", "d", "E"), "Squirrel")
        self.assertEqual(name("a", "B", "C", "D", "e"), "Black tortoise")
        self.assertEqual(name("A", "B", "C", "d", "e"), "Fawn")
        self.assertEqual(name("A", "B", "ch", "D", "E"), "Himalayan (black points)")
        self.assertEqual(name("A", "B", "c", "D", "E"), "Ruby-eyed white")


class PairingOddsTests(TestCase):
    def setUp(self):
        self.owner = user("odds@example.com")
        self.client.force_login(self.owner)
        base = {"owner": self.owner, "breed": "Holland Lop", "color": "Black", "birth_date": datetime.date(2025, 1, 1)}
        self.doe = Rabbit.objects.create(name="Clover", sex="doe", **base)
        self.buck = Rabbit.objects.create(name="Basil", sex="buck", **base)
        self.pairing = Pairing.objects.create(owner=self.owner, doe=self.doe, buck=self.buck)

    def genes(self, rabbit, certainty="known", **loci):
        for locus, genotype in loci.items():
            Gene.objects.create(rabbit=rabbit, locus=locus, genotype=genotype, certainty=certainty)

    def page(self):
        return self.client.get(reverse("pairing_detail", args=[self.pairing.pk]))

    def test_named_colors_from_two_black_carriers(self):
        self.genes(self.doe, A="a/a", B="B/b", C="C/c", D="D/D", E="E/E", En="en en")
        self.genes(self.buck, certainty="probable", A="a/a", B="B/B", C="C/c", D="D/d", E="E/E", En="En/en")
        odds = color_odds.predict(self.doe, self.buck)
        self.assertEqual(odds["colors_missing"], [])
        colors = dict(odds["colors"])
        self.assertEqual(colors["Ruby-eyed white"], "25%")
        self.assertEqual(colors["Black"], "75%")
        self.assertEqual(odds["pattern"], [("Broken", "50%"), ("Solid", "50%")])
        self.assertEqual(odds["probable"], ["Basil"])
        response = self.page()
        self.assertContains(response, "Color odds")
        self.assertContains(response, "Broken 50% · Solid 50%")
        self.assertContains(response, "C/C 25%")
        self.assertContains(response, "probable, not confirmed, genes for Basil")

    def test_dilute_quarter(self):
        self.genes(self.doe, A="A/A", B="B/B", C="C/C", D="D/d", E="E/E")
        self.genes(self.buck, A="A/A", B="B/B", C="C/C", D="D/d", E="E/E")
        self.assertEqual(color_odds.predict(self.doe, self.buck)["colors"], [("Chestnut", "75%"), ("Opal", "25%")])

    def test_missing_and_unknown_genes_show_per_gene_odds_only(self):
        self.genes(self.doe, A="A/_", D="d/d", E="nonsense")
        self.genes(self.buck, A="a/a", D="D/d")
        response = self.page()
        self.assertContains(response, "Record A, B, C, E with both alleles")
        self.assertContains(response, "A/a 50%")
        self.assertContains(response, "a/_ 50%")
        self.assertContains(response, "D/d 50%")
        self.assertContains(response, "Not recorded for Clover or Basil")
        self.assertContains(response, "“nonsense”, can't be read as a genotype")

    def test_other_keepers_pairing_is_hidden(self):
        self.client.force_login(user("someone@example.com"))
        self.assertEqual(self.page().status_code, 404)


class ViennaSilverLociTests(TestCase):
    def test_v_and_si_parse(self):
        self.assertEqual(color_odds.parse("V", "Vv"), ("V", "v"))
        self.assertEqual(color_odds.parse("Si", "si/si"), ("si", "si"))
        self.assertEqual(color_odds.parse("Si", "Sisi"), ("Si", "si"))

    def test_v_and_si_can_be_recorded(self):
        owner = user("vsi@example.com")
        rabbit = Rabbit.objects.create(owner=owner, name="Pearl", sex="doe", breed="Silver Fox",
                                       color="Black", birth_date=datetime.date(2025, 1, 1))
        Gene.objects.create(rabbit=rabbit, locus="V", genotype="V/v")
        Gene.objects.create(rabbit=rabbit, locus="Si", genotype="si/si")
        self.assertEqual(sorted(rabbit.genes.values_list("locus", flat=True)), ["Si", "V"])
