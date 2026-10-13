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


def _pairs_from_genes(genes):
    from .color_odds import SERIES, UNKNOWN, order, parse

    out = {}
    for gene in genes:
        if gene.locus in SERIES:
            pair = parse(gene.locus, gene.genotype)
            if pair is not None and UNKNOWN not in pair:
                out[gene.locus] = order(gene.locus, pair)
    return out


def parent_pairs(rabbit):
    """{"dam"/"sire": (name, {locus: pair})} with fully known pairs only,
    from the relative row's genes, or the herd rabbit's when it is in the herd."""
    out = {}
    rows = rabbit.relatives.filter(relationship__in=PARENTS).select_related("herd_rabbit", "outside")
    for row in rows:
        pairs = _pairs_from_genes(row.genes.all())
        name = str(row.other.name)
        if row.herd_rabbit is not None:
            pairs = {**pairs, **_pairs_from_genes(row.herd_rabbit.genes.all())}
            name = row.herd_rabbit.name
        out[row.relationship] = (name, pairs)
    return out


def _fraction_text(chance):
    return f"{chance.numerator}/{chance.denominator}" if chance.denominator != 1 else "certain"


def carrier_odds(rabbit):
    """For loci not fully known on the rabbit but known on both parents:
    the chance it carries each hidden allele, given the allele it shows
    when that is recorded (C_ shows C). Returns a list of plain lines."""
    from fractions import Fraction

    from .color_odds import SERIES, UNKNOWN, cross, genotype_text, order, parse, shown

    parents = parent_pairs(rabbit)
    if "dam" not in parents or "sire" not in parents:
        return []
    (dam_name, dam), (sire_name, sire) = parents["dam"], parents["sire"]
    own = {gene.locus: parse(gene.locus, gene.genotype) for gene in rabbit.genes.all() if gene.locus in SERIES}
    lines = []
    for locus in SERIES:
        mine = own.get(locus)
        if mine is not None and UNKNOWN not in mine:
            continue
        if locus not in dam or locus not in sire:
            continue
        odds = cross(locus, dam[locus], sire[locus])
        showing = next((allele for allele in (mine or ()) if allele != UNKNOWN), None)
        if showing is not None:
            odds = {g: f for g, f in odds.items() if shown(locus, g) == showing and showing in g}
        total = sum(odds.values(), Fraction(0))
        if not total:
            continue
        hidden = sorted({allele for g in odds for allele in g[1:]} - {showing}, key=SERIES[locus].index)
        for allele in hidden:
            chance = sum((f for g, f in odds.items() if allele in g and shown(locus, g) != allele), Fraction(0)) / total
            if 0 < chance < 1:
                lines.append(f"{locus}: {_fraction_text(chance)} chance of carrying {allele}, from "
                             f"{dam_name} {genotype_text(dam[locus])} × {sire_name} {genotype_text(sire[locus])}.")
    return lines


def test_mates(rabbit):
    """For each gene recorded with an unknown second allele, or only as
    probable, the herd rabbits of the other sex that are known to be
    homozygous for that locus's bottom recessive. A test litter from one
    shows whether the rabbit carries it. Returns [{locus, allele, shown,
    mates: [names], note}]."""
    from .color_odds import SERIES, UNKNOWN, genotype_text, parse
    from .models import Rabbit

    other_sex = {Rabbit.Sex.DOE: Rabbit.Sex.BUCK, Rabbit.Sex.BUCK: Rabbit.Sex.DOE}.get(rabbit.sex)
    if other_sex is None:
        return []
    herd = list(Rabbit.objects.filter(owner=rabbit.owner, sex=other_sex, archived_at__isnull=True)
                .exclude(status__in=[Rabbit.Status.DECEASED, Rabbit.Status.SOLD, Rabbit.Status.CULLED])
                .prefetch_related("genes").order_by("name"))
    out = []
    for gene in rabbit.genes.all():
        if gene.locus not in SERIES:
            continue
        pair = parse(gene.locus, gene.genotype)
        if pair is None:
            continue
        recessive = SERIES[gene.locus][-1]
        showing = next((allele for allele in pair if allele != UNKNOWN), None)
        probable = gene.certainty == Gene.Certainty.PROBABLE
        if showing in (None, recessive) or (recessive in pair and not probable):
            continue
        if UNKNOWN not in pair and not probable:
            continue
        mates = [mate.name for mate in herd if any(
            g.locus == gene.locus and g.certainty == Gene.Certainty.KNOWN
            and parse(g.locus, g.genotype) == (recessive, recessive) for g in mate.genes.all())]
        test = genotype_text((recessive, recessive))
        if mates:
            note = (f"Pair with {' or '.join(mates[:3])} ({test}). Any {test} kit shows {rabbit.name} carries "
                    f"{recessive}; 6 or more kits without one make it unlikely (under 2%).")
        else:
            note = f"No {test} {other_sex.label.lower()} recorded in the herd; one would test this."
        out.append({"locus": gene.locus, "allele": recessive, "shown": genotype_text(pair), "mates": mates, "note": note})
    return out
