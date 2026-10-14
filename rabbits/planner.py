"""Breeding program genetics: target odds, kept-kit genotypes, inbreeding and
the litter-count chances behind the program page. Pure functions on plain
data, so the views stay thin and the math is testable on its own.

Genotypes are {locus: (allele, allele)} as color_odds.parse reads them, with
"_" for an allele not known. A target is {locus: pattern}, each pattern either
"X_" (shows X: at least one X, nothing more dominant) or an exact pair such as
"aa" or "Enen".

Inbreeding follows Wright: F_X = sum over each common ancestor A of the
parents and each pair of paths from the sire and the dam up to A that share
no rabbit but A, of (1/2)^(n1 + n2 + 1) * (1 + F_A), where n1 and n2 count
the steps on each path. F_A comes from A's own parents the same way.
"""

from fractions import Fraction
from functools import lru_cache
from itertools import product
from math import comb

from .color_odds import SERIES, UNKNOWN, color_name, cross, order, parse, pattern_name, shown

PLAN_LOCI = ["A", "B", "C", "D", "E", "En"]
MAX_GENERATIONS = 6
HALF = Fraction(1, 2)


# Genotypes and targets --------------------------------------------------------

def read_genes(texts):
    """{locus: pair} from {locus: genotype text}; unreadable or blank loci are (_, _)."""
    out = {}
    for locus in PLAN_LOCI:
        pair = parse(locus, texts.get(locus)) if texts.get(locus) else None
        out[locus] = order(locus, pair) if pair else (UNKNOWN, UNKNOWN)
    return out


def read_pattern(locus, pattern):
    """("X", "_") for "X_", or an ordered exact pair; None if unreadable."""
    pair = parse(locus, pattern)
    if pair is None:
        return None
    return (pair[0], UNKNOWN) if pair[1] == UNKNOWN else order(locus, pair)


def matches(locus, pattern, pair):
    """Whether a fully known kit pair meets one target pattern."""
    want = read_pattern(locus, pattern)
    if want is None:
        return True
    if want[1] == UNKNOWN:
        return shown(locus, pair) == want[0]
    return order(locus, pair) == want


def fillings(locus, pair):
    """Every fully known pair a recorded pair could be. An unknown allele is
    anything at or below the shown one in dominance; (_, _) is anything."""
    series = SERIES[locus]
    a, b = pair
    if a == UNKNOWN:
        return [order(locus, p) for p in product(series, repeat=2) if series.index(p[0]) <= series.index(p[1])]
    if b == UNKNOWN:
        return [order(locus, (a, x)) for x in series[series.index(a):]]
    return [order(locus, pair)]


def locus_odds(locus, pattern, doe_pair, buck_pair):
    """(low, high) chance a kit meets the pattern at one locus, over every
    way the parents' unknown alleles could be filled."""
    chances = []
    for d, b in product(fillings(locus, doe_pair), fillings(locus, buck_pair)):
        chances.append(sum((f for g, f in cross(locus, d, b).items() if matches(locus, pattern, g)), Fraction(0)))
    return min(chances), max(chances)


def target_odds(target, doe, buck):
    """(low, high) chance a kit shows the target. Loci are independent, so the
    range is the product of each locus's range."""
    low = high = Fraction(1)
    for locus, pattern in target.items():
        lo, hi = locus_odds(locus, pattern, doe.get(locus, (UNKNOWN, UNKNOWN)), buck.get(locus, (UNKNOWN, UNKNOWN)))
        low, high = low * lo, high * hi
    return low, high


def assumed(pair):
    """The one filling used to name kit colors: an unknown allele reads as the
    shown one (the cautious guess); a blank locus reads as the wild type."""
    a, b = pair
    if a == UNKNOWN:
        return None
    return (a, a) if b == UNKNOWN else pair


WILD = {"A": ("A", "A"), "B": ("B", "B"), "C": ("C", "C"), "D": ("D", "D"), "E": ("E", "E"), "En": ("en", "en")}


def kit_genotypes(doe, buck):
    """{full genotype tuple over PLAN_LOCI: chance} for a litter, reading
    unknown alleles with assumed()."""
    per = []
    for locus in PLAN_LOCI:
        d = assumed(doe.get(locus, (UNKNOWN, UNKNOWN))) or WILD[locus]
        b = assumed(buck.get(locus, (UNKNOWN, UNKNOWN))) or WILD[locus]
        per.append(list(cross(locus, d, b).items()))
    out = {}
    for combo in product(*per):
        chance = Fraction(1)
        for _, f in combo:
            chance *= f
        key = tuple(g for g, _ in combo)
        out[key] = out.get(key, Fraction(0)) + chance
    return out


def phenotype(genotype):
    """"Broken black" from a full genotype tuple over PLAN_LOCI."""
    g = dict(zip(PLAN_LOCI, genotype))
    color = color_name(*(shown(locus, g[locus]) for locus in ["A", "B", "C", "D", "E"]))
    pattern = pattern_name(g["En"])
    if pattern == "Solid":
        return color
    word = "Charlie" if pattern.startswith("Charlie") else "Broken"
    return f"{word} {color[0].lower()}{color[1:]}"


def is_target(target, genotype):
    g = dict(zip(PLAN_LOCI, genotype))
    return all(matches(locus, pattern, g[locus]) for locus, pattern in target.items())


def outcomes(target, doe, buck):
    """[{name, chance, target}] for a litter, likeliest first, the target first among equals."""
    names = {}
    for genotype, chance in kit_genotypes(doe, buck).items():
        name = phenotype(genotype)
        row = names.setdefault(name, {"name": name, "chance": Fraction(0), "target": True})
        row["chance"] += chance
        row["target"] = row["target"] and is_target(target, genotype)
    return sorted(names.values(), key=lambda r: (-r["chance"], not r["target"], r["name"]))


def kept_genes(target, doe, buck):
    """A kept target kit's genes: {locus: pair}, exact where every target kit
    agrees and "X_" (one allele unknown) where they don't. Used as the G2 parent."""
    kits = [(g, f) for g, f in kit_genotypes(doe, buck).items() if is_target(target, g)]
    if not kits:
        return None
    out = {}
    for i, locus in enumerate(PLAN_LOCI):
        pairs = {g[i] for g, _ in kits}
        if len(pairs) == 1:
            out[locus] = next(iter(pairs))
        else:
            tops = {p[0] for p in pairs}
            out[locus] = (tops.pop(), UNKNOWN) if len(tops) == 1 else (UNKNOWN, UNKNOWN)
    return out


def kept_odds(target, doe, buck, mate):
    """Chance a kit of (a kept target kit of doe x buck) x mate shows the
    target, weighting each possible kept genotype by its share of target kits."""
    kits = [(g, f) for g, f in kit_genotypes(doe, buck).items() if is_target(target, g)]
    total = sum((f for _, f in kits), Fraction(0))
    if not total:
        return Fraction(0)
    mate_full = {locus: assumed(mate.get(locus, (UNKNOWN, UNKNOWN))) or WILD[locus] for locus in PLAN_LOCI}
    chance = Fraction(0)
    for genotype, weight in kits:
        parent = dict(zip(PLAN_LOCI, genotype))
        hit = sum((f for g, f in kit_genotypes(parent, mate_full).items() if is_target(target, g)), Fraction(0))
        chance += weight / total * hit
    return chance


# Litters ---------------------------------------------------------------------

def at_least(n, k, p):
    """Chance of at least k successes in n tries at chance p."""
    p = Fraction(p)
    return sum((comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)), Fraction(0))


def expected_text(n, p):
    """"About 2 of 7" / "About 3–4 of 7" for the expected count."""
    mean = float(n * Fraction(p))
    low, high = int(mean), int(mean) + (0 if mean == int(mean) else 1)
    if mean - low <= 0.25:
        high = low
    elif high - mean <= 0.25:
        low = high
    return f"About {low} of {n}" if low == high else f"About {low}–{high} of {n}"


# Inbreeding (Wright) ------------------------------------------------------------

class Pedigree:
    """Parents of each rabbit: {node: (sire, dam)} with None for unknown.
    Nodes are any hashable keys, so planned kits can be added as virtual ones."""

    def __init__(self, parents):
        self.parents = dict(parents)
        self._f = {}

    def paths_up(self, node, depth=MAX_GENERATIONS):
        """Every path from node up its pedigree, as tuples starting at node."""
        out = [(node,)]
        if depth == 0:
            return out
        for parent in self.parents.get(node, (None, None)):
            if parent is not None:
                out += [(node,) + path for path in self.paths_up(parent, depth - 1)]
        return out

    def inbreeding(self, node):
        """F of a rabbit, from its own sire and dam."""
        if node not in self._f:
            self._f[node] = Fraction(0)  # guards against a loop in bad data
            sire, dam = self.parents.get(node, (None, None))
            self._f[node] = self.coi(sire, dam) if sire is not None and dam is not None else Fraction(0)
        return self._f[node]

    def coi(self, sire, dam):
        """F of a kit of sire x dam (Wright's path formula with 1 + F_A)."""
        if sire is None or dam is None:
            return Fraction(0)
        up_s, up_d = self.paths_up(sire), self.paths_up(dam)
        total = Fraction(0)
        for ps in up_s:
            for pd in up_d:
                if ps[-1] != pd[-1]:
                    continue
                # The two paths may meet only at the common ancestor.
                if set(ps[:-1]) & set(pd):
                    continue
                if set(pd[:-1]) & set(ps):
                    continue
                n1, n2 = len(ps) - 1, len(pd) - 1
                total += HALF ** (n1 + n2 + 1) * (1 + self.inbreeding(ps[-1]))
        return total


def percent_text(fraction, digits=1):
    value = round(float(fraction) * 100, digits)
    return f"{value:g}%"


def range_text(low, high):
    if low == high:
        return percent_text(low, 0)
    return f"{percent_text(low, 0)[:-1]}–{percent_text(high, 0)}"
