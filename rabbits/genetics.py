"""Small, plain helpers for recorded genes and colors.

Nothing here predicts litters. It only reads what keepers recorded and
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
