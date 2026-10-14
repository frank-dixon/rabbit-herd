from django.test import SimpleTestCase

from . import gene_inference as gi


def n(name, color, sire=None, dam=None, breed="Mini Rex", genes=None):
    return {"name": name, "color": color, "sire": sire, "dam": dam, "breed": breed, "genes": genes or {}}


FAMILY = {
    "frost": n("Frost", "Ruby-eyed white"),
    "willow": n("Willow", "Black"),
    "granite": n("Granite", "Broken black"),
    "ash": n("Ash", "Broken black", sire="granite", dam="willow"),
    "fern": n("Fern", "Chinchilla"),
    "hazel": n("Hazel", "Chinchilla", dam="fern"),
    "juniper": n("Juniper", "Broken chinchilla", sire="ash", dam="hazel"),
    "snow": n("Snow", "Ruby-eyed white", sire="ash", dam="hazel"),
}
FAMILY["willow"]["dam"] = "frost"


def pair(result, key, locus):
    return [(r["allele"], r["level"], r["origin"]) for r in result[key][locus]["pair"]]


class InferenceTests(SimpleTestCase):
    def setUp(self):
        self.r = gi.infer(FAMILY)

    def test_rew_kit_proves_both_parents_carry_c(self):
        ash = {r["allele"]: r for r in self.r["ash"]["C"]["pair"]}
        self.assertEqual(ash["c"]["level"], gi.KNOWN)
        self.assertIn("Snow", ash["c"]["why"])
        self.assertIn(("c", gi.KNOWN), [(r["allele"], r["level"]) for r in self.r["hazel"]["C"]["pair"]])

    def test_albino_parent_passes_c(self):
        self.assertIn(("c", gi.KNOWN, "dam"), pair(self.r, "willow", "C"))

    def test_only_allele_that_fits(self):
        # Ash is C c; Juniper shows chinchilla, so Ash must have passed c, and Hazel cchd.
        self.assertEqual(pair(self.r, "juniper", "C"), [("c", gi.KNOWN, "sire"), ("cchd", gi.KNOWN, "dam")])
        self.assertIn("Only allele that fits", self.r["juniper"]["C"]["pair"][0]["why"])

    def test_founders_without_evidence_stay_unknown(self):
        # Granite shows black at B; his second B allele has nothing to go on: no breed priors.
        levels = [r["level"] for r in self.r["granite"]["B"]["pair"]]
        self.assertIn(gi.UNKNOWN_LEVEL, levels)
        self.assertNotIn(gi.PROBABLE, levels)

    def test_probable_from_parent_odds(self):
        kits = dict(FAMILY, kit=n("Kit", "Black", sire="frost", dam="willow"))
        r = gi.infer(kits)
        # Willow is c from Frost plus C from the coat: Kit gets c from Frost (sure) and C from... coat.
        self.assertEqual(sorted(x["allele"] for x in r["kit"]["C"]["pair"]), ["C", "c"])

    def test_coin_toss_is_a_guess(self):
        fam = dict(FAMILY, pepper=n("Pepper", "Broken black", sire="ash", dam="hazel"))
        c = self.r and gi.infer(fam)["pepper"]["C"]["pair"]
        self.assertTrue(all(x["level"] != gi.PROBABLE or x["pct"] > 50 for x in c))

    def test_recorded_known_gene(self):
        fam = {"a": n("A", "Black", genes={"B": ("Bb", "known")})}
        self.assertEqual(sorted(x["allele"] for x in gi.infer(fam)["a"]["B"]["pair"]), ["B", "b"])

    def test_thread_runs_from_source_to_kits(self):
        t = gi.thread(FAMILY, self.r, "C", "c")
        self.assertIn("frost", t["sources"])
        self.assertIn(("frost", "willow", gi.KNOWN), t["edges"])
        self.assertIn(("ash", "juniper", gi.KNOWN), t["edges"])
        self.assertEqual(t["nodes"]["snow"][0], "expressed")

    def test_changes_lists_new_look_and_proof(self):
        kinds = {c["kind"] for c in gi.changes(FAMILY, self.r, "snow")}
        self.assertIn("new", kinds)
        self.assertIn("proven", {c["kind"] for c in gi.changes(FAMILY, self.r, "ash")})
        self.assertIn("inherited", {c["kind"] for c in gi.changes(FAMILY, self.r, "juniper")})
