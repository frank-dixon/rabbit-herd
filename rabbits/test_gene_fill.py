from django.test import SimpleTestCase

from .gene_fill import canonical, from_breed_and_color, narrow_with_parents, options


def fill(color, breed="", eye=""):
    return from_breed_and_color(breed, color, eye)


class ColorRulesTests(SimpleTestCase):
    def test_self_colors(self):
        self.assertEqual(fill("Black"), {"A": "aa", "B": "B_", "C": "C_", "D": "D_", "E": "E_", "En": "enen", "V": "V_"})
        self.assertEqual(fill("Blue"), {"A": "aa", "B": "B_", "C": "C_", "D": "dd", "E": "E_", "En": "enen", "V": "V_"})
        self.assertEqual(fill("Chocolate"), {"A": "aa", "B": "bb", "C": "C_", "D": "D_", "E": "E_", "En": "enen", "V": "V_"})
        self.assertEqual(fill("Lilac"), {"A": "aa", "B": "bb", "C": "C_", "D": "dd", "E": "E_", "En": "enen", "V": "V_"})

    def test_agouti_colors(self):
        self.assertEqual(fill("Chestnut agouti"), {"A": "A_", "B": "B_", "C": "C_", "D": "D_", "E": "E_", "En": "enen", "V": "V_"})
        self.assertEqual(fill("Opal")["D"], "dd")
        self.assertEqual(fill("Lynx"), {"A": "A_", "B": "bb", "C": "C_", "D": "dd", "E": "E_", "En": "enen", "V": "V_"})
        self.assertEqual(fill("Chinchilla")["C"], "cchd_")
        self.assertEqual(fill("Squirrel")["D"], "dd")

    def test_tan_pattern(self):
        self.assertEqual(fill("Black otter")["A"], "at_")
        self.assertEqual(fill("Blue otter")["D"], "dd")
        self.assertEqual(fill("Black", breed="Tan")["A"], "at_")

    def test_orange_and_tort(self):
        self.assertEqual(fill("Red")["E"], "ee")
        self.assertEqual(fill("Red")["A"], "A_")
        self.assertEqual(fill("Tortoise")["A"], "aa")
        self.assertEqual(fill("Blue tortoise")["D"], "dd")
        self.assertEqual(fill("Cream")["D"], "dd")

    def test_shaded_and_pointed(self):
        self.assertEqual(fill("Sable")["C"], "cchl_")
        self.assertEqual(fill("Seal")["C"], "cchlcchl")
        self.assertEqual(fill("Smoke pearl")["D"], "dd")
        self.assertEqual(fill("Black pointed white"), {"A": "aa", "B": "B_", "C": "ch_", "D": "D_", "E": "E_", "En": "enen", "V": "V_"})

    def test_broken(self):
        self.assertEqual(fill("Broken black")["En"], "En_")
        self.assertEqual(fill("Charlie black")["En"], "EnEn")
        self.assertEqual(fill("Harlequin")["E"], "ej_")
        self.assertEqual(fill("Steel")["E"], "Es_")

    def test_whites(self):
        self.assertEqual(fill("Ruby-eyed white"), {"C": "cc"})
        self.assertEqual(fill("White", eye="ruby"), {"C": "cc"})
        self.assertEqual(fill("White"), {})
        self.assertEqual(fill("Blue-eyed white"), {"V": "vv"})
        self.assertEqual(fill("White", eye="blue"), {"V": "vv"})

    def test_pointed_white_with_pink_eyes_is_not_albino(self):
        self.assertEqual(fill("White with black points", eye="ruby")["C"], "ch_")

    def test_unknown_color_fills_nothing(self):
        self.assertEqual(fill("Frosty"), {})
        self.assertEqual(fill(""), {})


class BreedTests(SimpleTestCase):
    def test_fixed_varieties_fill_from_breed_alone(self):
        creme = fill("", breed="Creme d'Argent")
        self.assertEqual(creme["E"], "ee")
        self.assertEqual(creme["Si"], "sisi")
        self.assertEqual(creme["A"], "aa")  # every Creme variety is a silvered self orange
        self.assertEqual(fill("", breed="Champagne d'Argent")["A"], "aa")
        self.assertEqual(fill("", breed="Florida White"), {"C": "cc"})
        self.assertEqual(fill("", breed="Californian")["C"], "ch_")
        self.assertEqual(fill("", breed="American Chinchilla")["C"], "cchd_")

    def test_breed_spelling_is_forgiving(self):
        self.assertEqual(fill("", breed="Crème d’Argent")["E"], "ee")

    def test_breed_wins_over_color_words(self):
        self.assertEqual(fill("Brown", breed="Silver")["A"], "A_")
        self.assertEqual(fill("Brown", breed="Silver")["B"], "B_")
        self.assertEqual(fill("Brown", breed="Silver")["Si"], "sisi")
        self.assertEqual(fill("Blue", breed="Himalayan")["C"], "ch_")
        self.assertEqual(fill("Blue", breed="Himalayan")["D"], "dd")
        self.assertEqual(fill("Black", breed="Checkered Giant")["En"], "En_")

    def test_new_zealand_white(self):
        self.assertEqual(fill("White Ruby-eyed white", breed="New Zealand"), {"C": "cc"})
        self.assertEqual(fill("White", breed="Flemish Giant"), {"C": "cc"})


class ParentTests(SimpleTestCase):
    def test_homozygous_recessive_parent_narrows(self):
        self.assertEqual(narrow_with_parents({"A": "A_"}, [{"A": "aa"}]), {"A": "Aa"})
        self.assertEqual(narrow_with_parents({"D": "D_"}, [{"D": "dd"}, {}]), {"D": "Dd"})

    def test_unhelpful_parents_leave_it(self):
        self.assertEqual(narrow_with_parents({"A": "A_"}, [{"A": "AA"}]), {"A": "A_"})
        self.assertEqual(narrow_with_parents({"A": "A_"}, [{"A": "Aa"}]), {"A": "A_"})
        self.assertEqual(narrow_with_parents({"A": "aa"}, [{"A": "AA"}]), {"A": "aa"})


class SpellingTests(SimpleTestCase):
    def test_options(self):
        self.assertEqual(options("A"), ["AA", "Aat", "Aa", "A_", "atat", "ata", "at_", "aa"])
        self.assertIn("cchdc", options("C"))
        self.assertIn("ej_", options("E"))
        self.assertEqual(options("En"), ["EnEn", "Enen", "En_", "enen"])
        self.assertEqual(options("Si"), ["SiSi", "Sisi", "Si_", "sisi"])

    def test_canonical(self):
        self.assertEqual(canonical("C", "C/c"), "Cc")
        self.assertEqual(canonical("A", "_/A"), "A_")
        self.assertEqual(canonical("A", ""), "")
        self.assertIsNone(canonical("A", "zebra"))


class EyeTests(SimpleTestCase):
    def test_eye_color_from_genes(self):
        from rabbits.gene_fill import eye_from_genes as eye
        self.assertEqual(eye({"C": "cc", "D": "D_"}), "ruby")
        self.assertEqual(eye({"C": "ch_"}), "ruby")
        self.assertEqual(eye({"C": "cchd_", "D": "D_"}), "brown")
        self.assertEqual(eye({"C": "C_", "D": "dd"}), "blue-gray")
        self.assertEqual(eye({"V": "vv"}), "blue")
        self.assertEqual(eye({"D": "D_"}), "")  # C unknown: could be an albino
