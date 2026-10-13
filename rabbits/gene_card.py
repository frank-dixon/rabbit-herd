"""The smart genes card on a rabbit's page: one row per locus with how sure
we are. Known and Probable come from what was recorded; Possible is what the
breed, color and eye color point to but nobody has recorded; Unknown is
everything else, so the gaps are visible instead of silent."""

from . import gene_fill

LEVELS = [
    ("known", "Known", "Proven, for example by test litters or a ruby-eyed white coat."),
    ("probable", "Probable", "Recorded as likely, from the parents or the seller."),
    ("possible", "Possible", "Suggested by the breed and color. Not recorded yet."),
    ("unknown", "Unknown", "Nothing recorded or implied."),
]
LEVEL_LABELS = {key: label for key, label, _ in LEVELS}


def rows(rabbit, genes=None):
    """[{locus, name, genotype, level, label, note}] for every standard locus."""
    genes = list(rabbit.genes.all()) if genes is None else list(genes)
    recorded = {gene.locus: gene for gene in genes}
    implied = gene_fill.from_breed_and_color(rabbit.breed or "", rabbit.color or "", rabbit.eye_color or "")
    out = []
    for locus in gene_fill.LOCI:
        gene = recorded.get(locus)
        if gene:
            level, genotype, note = gene.certainty, gene.genotype, gene.note
        elif implied.get(locus):
            level, genotype, note = "possible", implied[locus], "From breed and color"
        else:
            level, genotype, note = "unknown", "", ""
        out.append({
            "locus": locus, "name": gene_fill.LOCUS_NAMES[locus], "genotype": genotype,
            "level": level, "label": LEVEL_LABELS.get(level, level.title()), "note": note,
        })
    return out


def summary(card_rows):
    """"2 known · 1 probable · 3 possible · 2 unknown", skipping zeros."""
    counts = {}
    for row in card_rows:
        counts[row["level"]] = counts.get(row["level"], 0) + 1
    return " · ".join(f"{counts[key]} {label.lower()}" for key, label, _ in LEVELS if counts.get(key))
