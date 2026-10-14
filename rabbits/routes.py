"""Shortest breeding routes to a color goal, and which goals the known
rabbits can reach at all. Pure functions on plain data.

Loci are inherited independently, so every chance here is a product of
per-locus chances; that keeps a full herd scan fast. Unknown alleles read as
planner.assumed() reads them (the shown allele again; a blank locus as wild
type), the same reading the program page's outcomes use.

A breeder is {"key", "name", "sex", "genes", "state"}, state one of
"ready" (in the herd), "access" (sold or kept elsewhere: needs the owner's
help) or "evidence" (deceased: its genes inform, it cannot breed).
"""

from fractions import Fraction
from itertools import product

from .color_odds import SERIES, UNKNOWN, cross, order, shown
from .planner import PLAN_LOCI, WILD, assumed, matches

STATE_RANK = {"ready": 0, "access": 1, "evidence": 2}


def full(genes, locus):
    return assumed(genes.get(locus, (UNKNOWN, UNKNOWN))) or WILD[locus]


def hit(locus, pattern, a, b):
    """Chance one kit of pairs a x b meets the pattern at this locus."""
    return sum((f for g, f in cross(locus, a, b).items() if matches(locus, pattern, g)), Fraction(0))


def one_gen(target, a, b):
    """Chance a kit of a x b shows the target."""
    p = Fraction(1)
    for locus, pattern in target.items():
        p *= hit(locus, pattern, full(a, locus), full(b, locus))
    return p


def two_gen(target, a, b, c=None):
    """Chance a G2 kit shows the target when a G1 kit of a x b (one picked at
    random: before any are seen) is bred to c, or to a sibling when c is None."""
    p = Fraction(1)
    for locus, pattern in target.items():
        g1 = cross(locus, full(a, locus), full(b, locus))
        if c is None:
            p *= sum((f1 * f2 * hit(locus, pattern, k1, k2) for (k1, f1), (k2, f2) in product(g1.items(), repeat=2)), Fraction(0))
        else:
            p *= sum((f * hit(locus, pattern, k, full(c, locus)) for k, f in g1.items()), Fraction(0))
    return p


def state_of(rabbits):
    """A route is only as available as its least available rabbit."""
    return max((r["state"] for r in rabbits), key=STATE_RANK.get, default="ready")


def routes(target, breeders, ok=None):
    """Every one- and two-generation route among the breeders, as
    {generations, pairings, rabbits, odds, state, steps}. Two-generation routes
    are only tried for parents with no one-generation route of their own.
    ok(doe, buck, mate=None) can veto a pairing (the program's COI limit):
    mate=None asks about doe x buck, otherwise about a G1 kit of theirs x mate
    ("kit" for a sibling)."""
    ok = ok or (lambda d, s, mate=None: True)
    does = [b for b in breeders if b["sex"] == "doe"]
    bucks = [b for b in breeders if b["sex"] == "buck"]
    out = []
    for d, s in product(does, bucks):
        if not ok(d, s):
            continue
        p = one_gen(target, d["genes"], s["genes"])
        if p:
            out.append({"generations": 1, "pairings": 1, "rabbits": [d, s], "odds": p, "state": state_of([d, s]),
                        "steps": [(d, s)]})
            continue
        best = None
        for c in breeders:
            if not ok(d, s, c):
                continue
            q = two_gen(target, d["genes"], s["genes"], c["genes"])
            used = [d, s] + ([c] if c not in (d, s) else [])
            if q and (best is None or (STATE_RANK[state_of(used)], -q) < (STATE_RANK[best["state"]], -best["odds"])):
                best = {"generations": 2, "pairings": 2, "rabbits": used, "odds": q, "state": state_of(used),
                        "steps": [(d, s), ("kit", c)]}
        q = two_gen(target, d["genes"], s["genes"]) if ok(d, s, "kit") else 0
        if q and (best is None or (STATE_RANK[state_of([d, s])], -q) < (STATE_RANK[best["state"]], -best["odds"])):
            best = {"generations": 2, "pairings": 2, "rabbits": [d, s], "odds": q, "state": state_of([d, s]),
                    "steps": [(d, s), ("kit", "kit")]}
        if best:
            out.append(best)
    out.sort(key=rank)
    return out


def rank(route):
    """Fewest generations, then fewest rabbits, then availability, then odds."""
    return (route["generations"], len(route["rabbits"]), STATE_RANK[route["state"]], -route["odds"])


def shortest(target, breeders, ok=None):
    """The minimum route using only rabbits that can breed now, else the
    minimum overall (so the page can say what access would unlock)."""
    found = routes(target, breeders, ok)
    ready = [r for r in found if r["state"] == "ready"]
    return (ready[0] if ready else None), (found[0] if found else None)


# Outside rabbits ---------------------------------------------------------------

def outside_pair(locus, pattern, partner):
    """The pair an outside rabbit should have at one locus to reach the
    pattern fastest with this partner: (pair, generations). Prefers a pair
    that works in one generation, then the commonest-looking (most dominant;
    for the En pattern, solid before broken, never a charlie)."""
    series = SERIES[locus]
    pairs = sorted({order(locus, p) for p in product(series, repeat=2)},
                   key=lambda p: (series.index(p[0]), series.index(p[1])))
    if locus == "En":
        pairs.sort(key=lambda p: p.count("En"))  # solid, then broken; never shop for a charlie
    mine = full(partner, locus)
    one = [(hit(locus, pattern, mine, p), p) for p in pairs]
    best = max(one, key=lambda t: t[0])
    if best[0]:
        # Among pairs as good as any, the most dominant: easiest to find.
        return next(p for f, p in one if f == best[0]), 1
    # Two generations: partner x outside, then a kit back to the outside rabbit.
    two = [(sum((f * hit(locus, pattern, k, p) for k, f in cross(locus, mine, p).items()), Fraction(0)), p) for p in pairs]
    best = max(two, key=lambda t: t[0])
    return (next(p for f, p in two if f == best[0]), 2) if best[0] else (None, 0)


def shopping(target, partner):
    """What an outside mate for this partner should be: {genes, generations,
    odds} or None if no outside rabbit can help."""
    genes, gens = {}, 1
    for locus, pattern in target.items():
        pair, g = outside_pair(locus, pattern, partner["genes"])
        if pair is None:
            return None
        genes[locus], gens = pair, max(gens, g)
    odds = one_gen(target, partner["genes"], genes) if gens == 1 else two_gen(target, partner["genes"], genes, genes)
    return {"genes": genes, "generations": gens, "odds": odds}


def describe(genes):
    """"Shows chocolate (b b) · carries dilute d" style words for a buying spec."""
    words = []
    for locus in PLAN_LOCI:
        pair = genes.get(locus)
        if not pair or UNKNOWN in pair:
            continue
        top, other = pair
        words.append(f"{locus} {top} {other}" if top != other else f"{locus} {top} {top}")
    return words


def carries(genes):
    """Recessive alleles the outside rabbit must carry hidden: [(locus, allele)]."""
    return [(locus, pair[1]) for locus, pair in genes.items() if pair[0] != pair[1] and shown(locus, pair) != pair[1]]
