"""Color odds for a pairing, from the genes recorded on the doe and buck.

Each standard locus (A, B, C, D, E and En) is a Punnett square: every kit
gets one allele from each parent, each with even chance. An allele written
as _ or ? is unknown and is shown as _ in the kit's genotype.

Named colors need A, B, C, D and E recorded with both alleles on both
rabbits; otherwise only the per-gene odds are shown. The names are the
common ones; breed standards name some of these differently.
"""

from collections import defaultdict
from fractions import Fraction
from itertools import product

from .models import Gene

UNKNOWN = "_"
UNKNOWN_MARKS = {"_", "?", "-", "x", "X"}

# Alleles in order of dominance, most dominant first.
SERIES = {
    "A": ["A", "at", "a"],
    "B": ["B", "b"],
    "C": ["C", "cchd", "cchm", "cchl", "ch", "c"],
    "D": ["D", "d"],
    "E": ["ED", "Es", "E", "ej", "e"],
    "En": ["En", "en"],
    "V": ["V", "v"],
    "Si": ["Si", "si"],
}
COLOR_LOCI = ["A", "B", "C", "D", "E"]
# Crossed into color names when recorded with both alleles on both parents;
# otherwise names assume the common V and Si (no Vienna, no silvering).
EXTRA_COLOR_LOCI = ["V", "Si"]
CHINCHILLA = {"cchd", "cchm", "cchl"}


def parse(locus, genotype):
    """Two alleles from text such as "A/at", "cchd c", "Enen" or "B/_".
    Returns a tuple of two alleles (unknown ones as _), or None when the
    text cannot be read as this locus."""
    alleles = SERIES[locus]
    text = str(genotype or "").strip()
    if "/" in text:
        parts = [p.strip() for p in text.split("/")]
    elif len(text.split()) > 1:
        parts = text.split()
    else:
        parts, rest = [], text
        longest_first = sorted(alleles, key=len, reverse=True)
        while rest:
            if rest[0] in UNKNOWN_MARKS:
                parts.append(UNKNOWN)
                rest = rest[1:]
                continue
            match = next((a for a in longest_first if rest.startswith(a)), None)
            if match is None:
                return None
            parts.append(match)
            rest = rest[len(match):]
    if len(parts) == 1:
        parts.append(UNKNOWN)
    if len(parts) != 2:
        return None
    pair = []
    for part in parts:
        if part in UNKNOWN_MARKS or part == "":
            pair.append(UNKNOWN)
        elif part in alleles:
            pair.append(part)
        else:
            return None
    return tuple(pair)


def order(locus, pair):
    """Dominant allele first, unknown last: ("at", "A") reads A/at."""
    rank = {allele: i for i, allele in enumerate(SERIES[locus])}
    return tuple(sorted(pair, key=lambda a: rank.get(a, len(rank))))


def cross(locus, doe_pair, buck_pair):
    """Kit genotypes at one locus as {ordered pair: Fraction}."""
    odds = defaultdict(Fraction)
    for a, b in product(doe_pair, buck_pair):
        odds[order(locus, (a, b))] += Fraction(1, 4)
    return dict(odds)


def shown(locus, pair):
    """The allele a kit shows: the most dominant one of its pair."""
    return order(locus, pair)[0]


def shade(b, d, agouti=False):
    if agouti:
        return {("B", "D"): "chestnut", ("b", "D"): "chocolate agouti", ("B", "d"): "opal", ("b", "d"): "lynx"}[(b, d)]
    return {("B", "D"): "black", ("b", "D"): "chocolate", ("B", "d"): "blue", ("b", "d"): "lilac"}[(b, d)]


def cap(name):
    return name[0].upper() + name[1:]


# Silvered (si/si) names on a full-color coat, keyed on the shown A and E
# alleles and the base shade. Breed names are the usual examples.
SILVERED = {
    ("a", "E", "black"): "Silvered black (Champagne d'Argent or Silver Fox type)",
    ("a", "E", "blue"): "Silvered blue (Argente Bleu or blue Silver Fox type)",
    ("a", "E", "chocolate"): "Silvered chocolate (Argente Brun type)",
    ("a", "E", "lilac"): "Silvered lilac",
    ("a", "e", "black"): "Silvered cream (Crème d'Argent type)",
    ("A", "E", "black"): "Silvered chestnut (Silver breed type)",
}


def color_name(a, b, c, d, e, v="V", si="Si"):
    """A common color name from the allele each locus shows. v and si are
    the shown V and Si alleles: vv is blue-eyed white, sisi is silvered.
    cc wins over vv: an albino that is also vv still has ruby eyes."""
    if c == "c":
        return "Ruby-eyed white"
    if v == "v":
        return "Blue-eyed white"
    name = _color_name(a, b, c, d, e)
    if si == "si" and c != "ch":
        key = (a if a != "at" else "A", "e" if e == "e" else "E", shade(b, d))
        if c not in CHINCHILLA and e not in {"ej", "Es"} and key in SILVERED:
            return SILVERED[key]
        name += ", silvered"
    return name


def eye_color(c, v="V"):
    """Eye color from the shown C and V alleles."""
    if c == "c":
        return "Ruby"
    if v == "v":
        return "Blue"
    if c == "ch":
        return "Pink-tinged"
    return "Dark brown"


def _color_name(a, b, c, d, e):
    base = shade(b, d)
    if c == "ch":
        return f"Himalayan ({base} points)"
    chin = c in CHINCHILLA
    shading = {"cchd": "", "cchm": " (medium shade)", "cchl": " (light shade)"}.get(c, "")
    if e == "ED":
        return cap(f"{base} self (dominant black)" + (", chinchilla-shaded" if chin else ""))
    if e == "e":
        if chin and a != "a":
            return "Frosted pearl" if base == "black" else cap(f"{base} frosted pearl")
        if c == "cchl" and a == "a":
            return "Sable point" if base == "black" else cap(f"{base} sable point")
        if a == "a":
            name = f"{base} tortoise"
        else:
            name = {"black": "orange", "chocolate": "chocolate orange", "blue": "fawn", "lilac": "cream"}[base]
            if a == "at":
                name += " with tan pattern"
        return cap(name + (", chinchilla-shaded" if chin else ""))
    if e == "ej":
        return cap(f"{base} harlequin" + (", chinchilla-shaded" if chin else ""))
    if e == "Es" and a != "a":
        # Steel needs agouti or tan; on a self (aa) it does not show.
        return cap(f"{base} steel" + (", chinchilla-shaded" if chin else ""))
    if a == "A":
        if chin:
            name = {"black": "chinchilla", "blue": "squirrel"}.get(base, f"{base} chinchilla")
            return cap(name + shading)
        return cap(shade(b, d, agouti=True))
    if a == "at":
        return cap(f"{base} {'silver marten' if chin else 'otter'}")
    if c == "cchl":
        return {"black": "Sable", "blue": "Smoke pearl"}.get(base, cap(f"{base} sable"))
    if chin:
        return cap(f"{base}, chinchilla-shaded")
    return cap(base)


def pattern_name(pair):
    count = list(pair).count("En")
    if UNKNOWN in pair and count < 2:
        return "Broken or solid" if count == 0 else "Broken or charlie"
    return {0: "Solid", 1: "Broken", 2: "Charlie (mostly white)"}[count]


def percent(fraction):
    value = round(float(fraction) * 100, 1)
    return f"{value:g}%"


def genotype_text(pair):
    return "/".join(pair)


def _genes(rabbit):
    return {gene.locus: gene for gene in rabbit.genes.all() if gene.locus != Gene.Locus.OTHER}


def predict(doe, buck):
    """Everything the pairing page shows. Keys:
    loci: per-locus rows with kit genotype odds, or the reason none show;
    colors: [(name, percent)] most likely first (color_rows adds each
    color's eye color), or [] with colors_missing
    naming what to record; assumed: V and/or Si when the names take them as
    V_ and Si_ because they are not recorded on both parents; pattern: broken odds when En is recorded on both; probable: names of rabbits whose genes used are
    only probable; unreadable: (rabbit name, locus, text) that did not parse."""
    parents = [("doe", doe, _genes(doe)), ("buck", buck, _genes(buck))]
    loci, crosses, unreadable, probable = [], {}, [], set()
    for locus in SERIES:
        pairs, missing = [], []
        for _, rabbit, genes in parents:
            gene = genes.get(locus)
            pair = parse(locus, gene.genotype) if gene else None
            if gene and pair is None:
                unreadable.append((rabbit.name, locus, gene.genotype))
            if pair is None:
                missing.append(rabbit.name)
            else:
                pairs.append(pair)
                if gene.certainty == Gene.Certainty.PROBABLE:
                    probable.add(rabbit.name)
        row = {"locus": locus, "label": Gene.Locus(locus).label, "missing": missing}
        if not missing:
            odds = cross(locus, *pairs)
            crosses[locus] = odds
            row["parents"] = [genotype_text(order(locus, p)) for p in pairs]
            row["kits"] = [(genotype_text(g), percent(f))
                           for g, f in sorted(odds.items(), key=lambda item: (-item[1], item[0]))]
        loci.append(row)

    def complete(locus):
        odds = crosses.get(locus)
        return odds is not None and not any(UNKNOWN in g for g in odds)

    colors, color_rows, colors_missing = [], [], [locus for locus in COLOR_LOCI if not complete(locus)]
    extra = [locus for locus in EXTRA_COLOR_LOCI if complete(locus)]
    assumed = [locus for locus in EXTRA_COLOR_LOCI if locus not in extra]
    if not colors_missing:
        used = COLOR_LOCI + extra
        names, eyes = defaultdict(Fraction), {}
        for combo in product(*(crosses[locus].items() for locus in used)):
            chance = Fraction(1)
            for _, fraction in combo:
                chance *= fraction
            alleles = {locus: shown(locus, g) for locus, (g, _) in zip(used, combo)}
            name = color_name(*(alleles[locus] for locus in COLOR_LOCI),
                              v=alleles.get("V", "V"), si=alleles.get("Si", "Si"))
            names[name] += chance
            eyes[name] = eye_color(alleles["C"], alleles.get("V", "V"))
        ranked = sorted(names.items(), key=lambda item: (-item[1], item[0]))
        colors = [(name, percent(f)) for name, f in ranked]
        color_rows = [{"name": name, "chance": percent(f), "eyes": eyes[name]} for name, f in ranked]

    # Broken is independent of color, so it is its own short list.
    pattern = []
    if "En" in crosses:
        names = defaultdict(Fraction)
        for genotype, chance in crosses["En"].items():
            names[pattern_name(genotype)] += chance
        pattern = [(name, percent(f)) for name, f in sorted(names.items(), key=lambda item: (-item[1], item[0]))]
    return {"loci": loci, "colors": colors, "color_rows": color_rows, "colors_missing": colors_missing,
            "assumed": assumed if colors else [], "pattern": pattern,
            "probable": sorted(probable), "unreadable": unreadable}
