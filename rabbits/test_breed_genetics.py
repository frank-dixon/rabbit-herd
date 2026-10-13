from django.test import SimpleTestCase

from . import breed_genetics as bg


class BreedGeneticsTests(SimpleTestCase):
    def test_thirty_one_varieties_all_parse_at_every_locus(self):
        self.assertEqual(len(bg.VARIETIES), 31)
        self.assertEqual(len(bg.BY_SLUG), 31)
        for variety in bg.VARIETIES:
            self.assertEqual(set(bg.genes(variety.genotype)), {"A", "B", "C", "D", "E", "En", "V", "Si"}, variety.name)

    def test_lookup_and_genes(self):
        creme = bg.typical("Crème d'Argent")
        self.assertEqual(bg.slug(creme.name), "creme-dargent")
        genes = bg.genes(creme.genotype)
        self.assertEqual(genes["E"], ("e", "e"))
        self.assertEqual(genes["Si"], ("si", "si"))
        self.assertEqual(genes["B"], ("B", "_"))
        self.assertEqual(bg.filled(creme)["B"], ("B", "B"))
        self.assertEqual(bg.genes(bg.typical("american-chinchilla").genotype)["C"], ("cchd", "_"))
        self.assertIsNone(bg.typical("Holland Lop"))
