from fractions import Fraction as F

from django.test import SimpleTestCase

from . import routes as R
from .planner import read_genes

CHOC = {"B": "bb"}


def rabbit(key, sex, state="ready", **genes):
    return {"key": key, "name": key, "sex": sex, "state": state, "genes": read_genes(genes)}


class RouteTests(SimpleTestCase):
    def test_one_and_two_generation_odds(self):
        carrier, black = read_genes({"B": "Bb"}), read_genes({"B": "BB"})
        self.assertEqual(R.one_gen(CHOC, carrier, carrier), F(1, 4))
        self.assertEqual(R.one_gen(CHOC, carrier, black), 0)
        # Bb x BB kit (1/2 carrier) back to the Bb parent: 1/2 * 1/4.
        self.assertEqual(R.two_gen(CHOC, carrier, black, carrier), F(1, 8))
        # Siblings from Bb x BB: both carriers 1/4, then 1/4.
        self.assertEqual(R.two_gen(CHOC, carrier, black), F(1, 16))

    def test_shortest_prefers_one_generation_and_ready_rabbits(self):
        herd = [rabbit("doe", "doe", B="Bb"), rabbit("buck", "buck", B="BB"), rabbit("sold", "buck", "access", B="Bb")]
        ready, overall = R.shortest(CHOC, herd)
        self.assertEqual((overall["generations"], overall["state"]), (1, "access"))
        self.assertEqual(ready["generations"], 2)
        self.assertEqual({r["key"] for r in ready["rabbits"]}, {"doe", "buck"})

    def test_deceased_only_route_is_evidence(self):
        herd = [rabbit("doe", "doe", B="Bb"), rabbit("gone", "buck", "evidence", B="bb")]
        ready, overall = R.shortest(CHOC, herd)
        self.assertIsNone(ready)
        self.assertEqual(overall["state"], "evidence")

    def test_shopping_spec(self):
        # A BB doe needs a chocolate (bb) buck, then a kit back to him.
        spec = R.shopping(CHOC, rabbit("doe", "doe", B="BB"))
        self.assertEqual((spec["genes"]["B"], spec["generations"], spec["odds"]), (("b", "b"), 2, F(1, 2)))
        # A carrier doe: the most dominant mate that still works in one generation is a carrier.
        spec = R.shopping({"B": "bb", "En": "Enen"}, rabbit("doe", "doe", B="Bb", En="Enen"))
        self.assertEqual(spec["generations"], 1)
        self.assertEqual(spec["genes"]["En"], ("en", "en"))  # solid: no charlies risk at 1/2 broken
        self.assertEqual(spec["genes"]["B"], ("b", "b"))
