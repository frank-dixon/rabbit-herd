"""The breeding planner's genetics: target odds, kept kits, litters and Wright's COI."""
from fractions import Fraction as F

from django.test import SimpleTestCase

from . import planner as p

BROKEN_BLACK = {"A": "aa", "B": "B_", "C": "C_", "D": "D_", "E": "E_", "En": "Enen"}


def genes(**texts):
    return p.read_genes({k.replace("En_", "En"): v for k, v in texts.items()})


WILLOW = genes(A="aa", B="BB", C="CC", D="DD", E="EE", En="Enen")
BLACKBERRY = genes(A="Aa", B="BB", C="CC", D="DD", E="EE", En="enen")
THISTLE = genes(A="aa", B="BB", C="CC", D="DD", E="EE", En="enen")


class OddsTests(SimpleTestCase):
    def test_board_pairings(self):
        self.assertEqual(p.target_odds(BROKEN_BLACK, WILLOW, THISTLE), (F(1, 2), F(1, 2)))
        self.assertEqual(p.target_odds(BROKEN_BLACK, WILLOW, BLACKBERRY), (F(1, 4), F(1, 4)))
        pepper = genes(A="aa", B="BB", C="CC", D="DD", E="EE", En="enen")
        self.assertEqual(p.target_odds(BROKEN_BLACK, pepper, BLACKBERRY)[1], 0)

    def test_unknown_alleles_give_a_range(self):
        speedwell = genes(A="A_", B="BB", C="CC", D="DD", E="E_", En="enen")
        low, high = p.target_odds(BROKEN_BLACK, WILLOW, speedwell)
        self.assertEqual((low, high), (F(0), F(1, 4)))  # A_ could be AA (no aa kits) or Aa
        self.assertEqual(p.range_text(low, high), "0–25%")

    def test_outcomes_and_kept_doe(self):
        rows = p.outcomes(BROKEN_BLACK, WILLOW, BLACKBERRY)
        self.assertEqual({r["name"]: r["chance"] for r in rows},
                         {"Broken black": F(1, 4), "Broken chestnut": F(1, 4), "Black": F(1, 4), "Chestnut": F(1, 4)})
        self.assertTrue(next(r for r in rows if r["name"] == "Broken black")["target"])
        kept = p.kept_genes(BROKEN_BLACK, WILLOW, BLACKBERRY)
        self.assertEqual((kept["A"], kept["En"]), (("a", "a"), ("En", "en")))
        self.assertEqual(p.kept_odds(BROKEN_BLACK, WILLOW, BLACKBERRY, THISTLE), F(1, 2))

    def test_broken_to_broken_makes_charlies(self):
        rows = {r["name"]: r["chance"] for r in p.outcomes(BROKEN_BLACK, WILLOW, WILLOW)}
        self.assertEqual(rows["Charlie black"], F(1, 4))

    def test_litter_chances(self):
        self.assertAlmostEqual(float(p.at_least(7, 2, F(1, 2))), 0.9375)
        self.assertAlmostEqual(float(p.at_least(7, 2, F(1, 4))), 0.5551, places=3)
        self.assertEqual(p.expected_text(7, F(1, 4)), "About 2 of 7")
        self.assertEqual(p.expected_text(7, F(1, 2)), "About 3–4 of 7")


class WrightTests(SimpleTestCase):
    def test_classic_matings(self):
        ped = p.Pedigree({"kid1": ("S", "D"), "kid2": ("S", "D"), "kid3": ("S", "D2"), "daughter": ("S", "D")})
        self.assertEqual(ped.coi("kid1", "kid2"), F(1, 4))      # full siblings
        self.assertEqual(ped.coi("kid1", "kid3"), F(1, 8))      # half siblings
        self.assertEqual(ped.coi("S", "daughter"), F(1, 4))     # father x daughter
        self.assertEqual(ped.coi("S", "D"), 0)                  # unrelated

    def test_an_inbred_common_ancestor_counts_1_plus_f(self):
        # A is from a full-sib mating (F_A = 1/4); half siblings through A get 1/8 * (1 + 1/4).
        ped = p.Pedigree({"s1": ("P", "Q"), "s2": ("P", "Q"), "A": ("s1", "s2"), "x": ("A", "M"), "y": ("A", "N")})
        self.assertEqual(ped.inbreeding("A"), F(1, 4))
        self.assertEqual(ped.coi("x", "y"), F(1, 8) * F(5, 4))

    def test_related_common_ancestors_are_not_double_counted(self):
        # Full siblings whose parents are themselves full siblings: Wright gives 3/8, not more.
        ped = p.Pedigree({"S": ("G1", "G2"), "D": ("G1", "G2"), "x": ("S", "D"), "y": ("S", "D")})
        self.assertEqual(ped.coi("S", "D"), F(1, 4))
        self.assertEqual(ped.coi("x", "y"), F(3, 8))


class PlanRowsTests(SimpleTestCase):
    def test_grouped_keeps_target_and_merges_tail_and_charlies(self):
        from fractions import Fraction as Fr

        from .program_plan import grouped
        rows = [{"name": "Broken blue", "target": True, "chance": Fr(1, 8)},
                {"name": "Charlie blue", "target": False, "chance": Fr(1, 16)},
                {"name": "Charlie black", "target": False, "chance": Fr(3, 16)}]
        rows += [{"name": f"C{i}", "target": False, "chance": Fr(1, 10) - Fr(i, 100)} for i in range(6)]
        out = grouped(rows)
        self.assertEqual([r["name"] for r in out], ["Broken blue", "C0", "C1", "C2", "C3", "Other colors", "Charlies"])
        self.assertEqual(out[-1]["chance"], Fr(1, 4))
        self.assertEqual(sum(r["chance"] for r in out), sum(r["chance"] for r in rows))
