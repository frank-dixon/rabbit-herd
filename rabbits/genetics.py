"""Small, plain helpers for recorded genes and colors.

Litter color odds live in color_odds. This module only reads what keepers recorded and
spots one well-known case: a parent that is c/c (albino, such as a
ruby-eyed white) passes a c to every kit, so a non-albino kit of that
parent carries c.
"""

from .models import Gene, Relative

LOCI = [value for value in Gene.Locus.values if value != Gene.Locus.OTHER]
ALBINO_COLORS = {"ruby-eyed white", "ruby eyed white", "rew", "albino"}
PARENTS = (Relative.Relationship.DAM, Relative.Relationship.SIRE)


def normalize(genotype):
    """c/c, c c and cc all read as cc. Case is kept: C and c differ."""
    return "".join(str(genotype or "").replace("/", "").split())


def is_albino_color(color):
    return " ".join(str(color or "").lower().split()) in ALBINO_COLORS


def c_genotype(genes):
    for gene in genes:
        if gene.locus == Gene.Locus.C:
            return normalize(gene.genotype)
    return ""


def is_albino(color, genes):
    """True when the C locus is recorded as cc, or the color is albino."""
    return c_genotype(genes) == "cc" or is_albino_color(color)


def albino_parent(rabbit):
    """The first dam or sire recorded as c/c, as (relationship label, name),
    or None. Looks at the color and genes recorded on the relative row, and
    at the herd rabbit's own color and genes when the parent is in the herd."""
    rows = rabbit.relatives.filter(relationship__in=PARENTS).select_related("herd_rabbit", "outside")
    for row in rows:
        if is_albino(row.color, list(row.genes.all())):
            return row.relationship, str(row.other.name)
        herd = row.herd_rabbit
        if herd is not None and is_albino(herd.color, list(herd.genes.all())):
            return row.relationship, herd.name
    return None


def c_carrier_suggestion(rabbit):
    """The note to show on a rabbit when a parent is c/c, or "".

    Nothing shows when the rabbit already has a C gene recorded, when the
    keeper removed the note, or when the rabbit is itself albino."""
    if rabbit.c_carrier_dismissed or rabbit.genes.filter(locus=Gene.Locus.C).exists():
        return ""
    if is_albino_color(rabbit.color):
        return ""
    parent = albino_parent(rabbit)
    if parent is None:
        return ""
    relationship, name = parent
    return (
        f"Probable carrier of c (albino): {rabbit.name}'s {relationship}, {name}, is c/c, "
        "so every kit gets one c. Confirm to record C/c, or remove this note."
    )


def _has(pair, allele):
    return pair is not None and allele in pair


def _homo(pair, allele):
    return pair is not None and pair[0] == allele and pair[1] == allele


def hidden_notes(pairs):
    """Plain notes on what a genotype hides or carries, from
    {locus: (allele, allele)} as color_odds.recorded returns."""
    a, c, e, v, si, en = (pairs.get(locus) for locus in ("A", "C", "E", "V", "Si", "En"))
    notes = []
    if _homo(c, "c"):
        notes.append("c/c (ruby-eyed white) hides whatever it carries at A, B, D, E, V and Si. "
                     "Bred to a colored rabbit, those genes show in the kits.")
    elif _has(c, "c"):
        notes.append("Carries albino (c). Bred to another carrier, about 1 in 4 kits are ruby-eyed white.")
        if _has(c, "ch"):
            notes.append("ch/c Himalayan: points are often paler than on ch/ch.")
    if _homo(v, "v"):
        if not _homo(c, "c"):
            notes.append("v/v (blue-eyed white) hides whatever it carries at A, B, C, D, E and Si.")
    elif _has(v, "v"):
        notes.append("Carries Vienna (v). Bred to another carrier, about 1 in 4 kits are blue-eyed white. "
                     "V/v rabbits can show small white marks.")
    if _has(e, "e") and not _homo(e, "e"):
        notes.append("Carries red (e). Bred to another carrier, about 1 in 4 kits are red-based: "
                     "orange, fawn or tortoise.")
    if e is not None and e[0] == "Es" and _homo(a, "a"):
        notes.append("Carries steel (Es), which does not show on a self (a/a). Bred to an agouti, steel kits can appear.")
    if _has(si, "si") and not _homo(si, "si"):
        notes.append("Carries silvering (si) without showing it. Bred to another carrier, about 1 in 4 kits are silvered.")
    if _homo(en, "En"):
        notes.append("Charlie (En/En). Bred to a solid (en/en), every kit is broken.")
    return notes


def pairing_notes(doe_name, doe_pairs, buck_name, buck_pairs):
    """Notes for a pairing: each parent's hidden genes, then what the two
    together make likely."""
    notes = [f"{name}: {note}" for name, pairs in ((doe_name, doe_pairs), (buck_name, buck_pairs))
             for note in hidden_notes(pairs)]
    doe_en, buck_en = doe_pairs.get("En"), buck_pairs.get("En")
    if _has(doe_en, "En") and _has(buck_en, "En"):
        notes.append("Both parents carry broken (En): expect some charlie (En/En) kits.")
    return notes
