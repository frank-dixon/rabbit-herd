"""Genes a rabbit's breed, coat color and eye color prove.

A coat color shows the most dominant allele at each locus, so it proves
one allele and, for a recessive color, both. Black proves aa at A (two
recessives) but only B_ at B: the second B allele could be B or b. This
module writes what is proven and leaves the rest as _, the same mark the
pairing odds read as unknown (see color_odds). Nothing here guesses from
what is common in a breed; a breed only fills genes when every rabbit of
that breed's recognized variety must carry them (Creme d'Argent, Florida
White, Californian and the like).

Genotypes are written dominant allele first with no separator, such as
"Aat", "cchdc" or "Enen", which color_odds.parse and genetics.normalize
both read.

Sources for the phenotype rules: the ARBA Standard of Perfection color
guides, and the common rabbit color genetics references (A, B, C, D, E
and En series as used by the pairing odds).
"""

import re
import unicodedata

from .color_odds import SERIES, UNKNOWN, order, parse

LOCI = ["A", "B", "C", "D", "E", "En", "V", "Si"]
OTHER = "other"
LOCUS_NAMES = {
    "A": "Agouti", "B": "Brown", "C": "Color", "D": "Dilute", "E": "Extension", "En": "Broken",
    "V": "Vienna", "Si": "Silvering",
}
EYE_COLORS = [
    ("brown", "Brown"),
    ("blue-gray", "Blue-gray"),
    ("blue", "Blue (blue-eyed white or Vienna)"),
    ("ruby", "Ruby or pink"),
    ("marbled", "Marbled or odd"),
]
# Silvering (si) and Vienna white (v) are recessive: sisi is silvered, vv
# is a blue-eyed white.
SILVERING = {"Si": "sisi"}
VIENNA = {"V": "vv"}


def options(locus):
    """Every genotype the dropdown offers at one locus, dominant first:
    for A, "AA", "Aat", "Aa", "A_", "atat", "ata", "at_", "aa"."""
    alleles = SERIES[locus]
    out = []
    for i, first in enumerate(alleles):
        for second in alleles[i:]:
            out.append(first + second)
        if i < len(alleles) - 1:
            out.append(first + UNKNOWN)
    return out


def canonical(locus, text):
    """A recorded genotype in the dropdown's spelling ("C/c" reads "Cc",
    "_/A" reads "A_"), "" for blank, or None when it can't be read."""
    text = str(text or "").strip()
    if not text:
        return ""
    pair = parse(locus, text)
    if pair is None:
        return None
    if pair == (UNKNOWN, UNKNOWN):
        return ""
    return "".join(order(locus, pair))


def fold(text):
    plain = unicodedata.normalize("NFKD", str(text or ""))
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return " ".join(plain.casefold().replace("’", "'").split())


# What a self shade proves at B and D.
SHADES = [
    (r"\blilac\b|\blavender\b|\bdove\b", {"B": "bb", "D": "dd"}),
    (r"\bchocolate\b|\bbrown\b|\bhavana\b", {"B": "bb", "D": "D_"}),
    (r"\bblue\b|\bgr[ae]yish blue\b", {"B": "B_", "D": "dd"}),
    (r"\bblack\b|\bebony\b", {"B": "B_", "D": "D_"}),
]

# Color words, most specific first. Each rule fills only loci not already
# filled by an earlier rule or by the breed.
COLOR_RULES = [
    (r"tort", {"A": "aa", "E": "ee"}),
    (r"harlequin|japanese|magpie", {"E": "ej_"}),
    (r"steel", {"E": "Es_"}),
    (r"smoke pearl", {"C": "cchl_", "D": "dd", "B": "B_", "E": "E_"}),
    (r"sable marten", {"A": "at_", "C": "cchl_", "B": "B_", "D": "D_", "E": "E_"}),
    (r"silver marten", {"A": "at_", "E": "E_"}),
    (r"marten", {"A": "at_"}),
    (r"\bsiamese\b", {"A": "aa"}),
    (r"\bseal\b", {"A": "aa", "C": "cchlcchl", "B": "B_", "D": "D_", "E": "E_"}),
    (r"sable", {"A": "aa", "C": "cchl_", "B": "B_", "D": "D_", "E": "E_"}),
    (r"squirrel", {"A": "A_", "B": "B_", "C": "cchd_", "D": "dd", "E": "E_"}),
    (r"chinchilla", {"A": "A_", "C": "cchd_", "E": "E_"}),
    (r"otter|\btan\b|black tan", {"A": "at_", "E": "E_"}),
    (r"lynx", {"A": "A_", "B": "bb", "D": "dd", "E": "E_"}),
    (r"\bopal\b", {"A": "A_", "B": "B_", "D": "dd", "E": "E_"}),
    (r"chocolate agouti|chocolate chestnut", {"A": "A_", "B": "bb", "D": "D_", "E": "E_"}),
    (r"chestnut|castor|\bgr[ae]y\b|sandy", {"A": "A_", "B": "B_", "D": "D_", "E": "E_"}),
    (r"agouti|wild", {"A": "A_", "E": "E_"}),
    (r"points?\b|pointed|himalayan|californian", {"A": "aa", "C": "ch_", "E": "E_"}),
    (r"\bcream\b|\bcreme\b", {"A": "A_", "D": "dd", "E": "ee"}),
    (r"orange|\bred\b|\bfawn\b|\bgold|\bfire\b", {"A": "A_", "E": "ee"}),
]
SELF_WORDS = r"\b(black|blue|chocolate|brown|havana|lilac|lavender|ebony)\b"
BROKEN_WORDS = r"broken|charlie|checkered|\bspot|papillon|butterfly|markings|harlequin|magpie"

# Breeds whose recognized varieties fix some genes. "*" applies to every
# color of the breed; a color name applies only to that variety. The
# breed's entries win over what the color words alone would fill.
BREEDS = {
    "creme d'argent": {"*": {"A": "aa", "B": "B_", "C": "C_", "D": "D_", "E": "ee", "En": "enen", **SILVERING}},
    "champagne d'argent": {"*": {"A": "aa", "B": "B_", "C": "C_", "D": "D_", "E": "E_", "En": "enen", **SILVERING}},
    "argente noir": {"*": {"A": "aa", "B": "B_", "C": "C_", "D": "D_", "E": "E_", "En": "enen", **SILVERING}},
    "argente bleu": {"*": {"A": "aa", "B": "B_", "C": "C_", "D": "dd", "E": "E_", "En": "enen", **SILVERING}},
    "argente brun": {"*": {"A": "aa", "B": "bb", "C": "C_", "D": "D_", "E": "E_", "En": "enen", **SILVERING}},
    "florida white": {"*": {"C": "cc"}},
    "blanc de bouscat": {"*": {"C": "cc"}},
    "blanc de termonde": {"*": {"C": "cc"}},
    "hulstlander": {"*": dict(VIENNA)},
    "californian": {"*": {"A": "aa", "B": "B_", "C": "ch_", "D": "D_", "E": "E_", "En": "enen"}},
    "mini californian": {"*": {"A": "aa", "B": "B_", "C": "ch_", "D": "D_", "E": "E_", "En": "enen"}},
    "himalayan": {"*": {"A": "aa", "C": "ch_", "E": "E_", "En": "enen"}},
    "american chinchilla": {"*": {"A": "A_", "B": "B_", "C": "cchd_", "D": "D_", "E": "E_", "En": "enen"}},
    "standard chinchilla": {"*": {"A": "A_", "B": "B_", "C": "cchd_", "D": "D_", "E": "E_", "En": "enen"}},
    "giant chinchilla": {"*": {"A": "A_", "B": "B_", "C": "cchd_", "D": "D_", "E": "E_", "En": "enen"}},
    "chinchilla giganta": {"*": {"A": "A_", "B": "B_", "C": "cchd_", "D": "D_", "E": "E_", "En": "enen"}},
    "squirrel": {"*": {"A": "A_", "B": "B_", "C": "cchd_", "D": "dd", "E": "E_", "En": "enen"}},
    "american sable": {"*": {"A": "aa", "B": "B_", "C": "cchl_", "D": "D_", "E": "E_", "En": "enen"}},
    "siamese sable": {"*": {"A": "aa", "B": "B_", "C": "cchl_", "D": "D_", "E": "E_", "En": "enen"}},
    "lilac": {"*": {"A": "aa", "B": "bb", "C": "C_", "D": "dd", "E": "E_", "En": "enen"}},
    "thrianta": {"*": {"A": "A_", "B": "B_", "C": "C_", "D": "D_", "E": "ee", "En": "enen"}},
    "tan": {"*": {"A": "at_", "C": "C_", "E": "E_", "En": "enen"}},
    "silver marten": {"*": {"A": "at_", "E": "E_", "En": "enen"}, "sable": {"C": "cchl_"}},
    "checkered giant": {"*": {"A": "aa", "C": "C_", "E": "E_", "En": "En_"}},
    "english spot": {"*": {"En": "En_"}},
    "dwarf papillon": {"*": {"A": "aa", "C": "C_", "E": "E_", "En": "En_"}},
    "rhinelander": {"*": {"E": "ej_", "En": "En_"}},
    "silver": {"*": dict(SILVERING), "brown": {"A": "A_", "B": "B_", "D": "D_", "E": "E_"}, "fawn": {"A": "A_", "E": "ee"}},
    "meissner lop": {"*": dict(SILVERING), "brown": {"A": "A_", "B": "B_", "D": "D_", "E": "E_"}, "fawn": {"A": "A_", "E": "ee"}},
    "palomino": {"lynx": {"A": "A_", "B": "bb", "C": "C_", "D": "dd", "E": "E_"}, "golden": {"A": "A_", "E": "ee"}},
    "wheaten lynx": {"*": {"A": "A_", "B": "bb", "D": "dd", "En": "enen"}},
    "flemish giant": {"white": {"C": "cc"}},
    "belgian hare": {"*": {"En": "enen"}},
    "vienna": {"blue-eyed white": dict(VIENNA)},
    "beveren": {"white": dict(VIENNA)},
}
# The whites that are ruby-eyed albinos, whatever the breed.
REW = r"ruby[- ]eyed white|red[- ]eyed white|pink[- ]eyed white|\brew\b|albino"
BEW = r"blue[- ]eyed white|\bbew\b"
# A white that still shows color somewhere is not an albino.
MARKED_WHITE = r"point|marking|band|spot|butterfly|tip|with "


def from_breed_and_color(breed, color, eye=""):
    """{locus: genotype} for what the breed, color and eye color prove.
    Loci that are not proven are left out."""
    b, c, eye = fold(breed), fold(color), fold(eye)
    genes = {}

    def add(found):
        for locus, value in found.items():
            genes.setdefault(locus, value)

    entry = BREEDS.get(b, {})
    for key, found in entry.items():
        if key != "*" and key in c:
            add(found)
    add(entry.get("*", {}))

    white = bool(re.search(r"\bwhite\b", c)) and not re.search(MARKED_WHITE, c)
    if re.search(REW, c) or (eye == "ruby" and (white or (not c and genes.get("C") in (None, "cc")))):
        # An albino hides every other color gene, so only C is proven.
        genes["C"] = "cc"
        return {"C": "cc"}
    if re.search(BEW, c) or (eye == "blue" and white):
        # A Vienna white hides every other color gene, so only V is proven.
        return dict(VIENNA)
    if not c:
        return genes

    recognized = False
    for pattern, found in COLOR_RULES:
        if re.search(pattern, c):
            add(found)
            recognized = True
    for pattern, found in SHADES:
        if re.search(pattern, c):
            add(found)
            recognized = True
            break
    if re.search(SELF_WORDS, c) and not re.search(r"chinchilla|agouti|chestnut|marten|otter|tan\b|steel|lynx|squirrel", c):
        add({"A": "aa", "E": "E_"})
    if re.search(BROKEN_WORDS, c):
        add({"En": "EnEn" if "charlie" in c else "En_"})
    elif recognized and not white:
        add({"En": "enen"})
    if recognized and not white:
        # A named color with no chinchilla, sable or point rule shows full
        # color, so it carries at least one C.
        add({"C": "C_", "V": "V_"})
    return genes


def eye_from_genes(genes):
    """The eye color a set of genes proves, or "" when they don't settle it.
    Albinos (cc) and Himalayan points (ch) have ruby eyes, Vienna whites (vv)
    blue, dilutes (dd) blue-gray, and full-color non-dilutes brown."""
    c, d, v = (str(genes.get(k) or "").strip() for k in ("C", "D", "V"))
    if c == "cc":
        return "ruby"
    if v == "vv":
        return "blue"
    if c.startswith("ch") and not c.startswith("cch"):
        return "ruby"
    if not c or c.startswith("_"):
        return ""
    if d == "dd":
        return "blue-gray"
    if d.startswith("D"):
        return "brown"
    return ""


def narrow_with_parents(genes, parents):
    """Narrow a one-unknown genotype such as A_ with a parent recorded as
    homozygous: a kit that shows A and has an aa parent is Aa. `parents` is
    a list of {locus: genotype text}. Returns a new dict."""
    out = dict(genes)
    for locus in LOCI:
        value = out.get(locus)
        if not value:
            continue
        pair = parse(locus, value)
        if pair is None or pair[1] != UNKNOWN or pair[0] == UNKNOWN:
            continue
        shown = pair[0]
        rank = SERIES[locus].index(shown)
        for parent in parents:
            p = parse(locus, parent.get(locus, "")) if parent.get(locus) else None
            if p is None or UNKNOWN in p or p[0] != p[1]:
                continue
            given = p[0]
            if SERIES[locus].index(given) > rank:
                out[locus] = shown + given
                break
    return out
