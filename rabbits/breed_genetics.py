"""Typical genotypes for 31 meat rabbit varieties, as plain data.

These are the usual genotypes for each variety, not proof for any one
rabbit: lines differ, and a white or pointed coat can hide almost
anything. Verify against your own rabbits before relying on them.
An allele written _ is not fixed by the variety.

Source: the rabbit-genetics-visualizer breed table, itself drawn from OSU
Extension EM 9708, Dichrome Rabbitry (V and Si loci), Fontanesi et al.
(MC1R, KIT, MLPH) and the ARBA breed standards.
"""

from typing import NamedTuple

from .color_odds import SERIES, UNKNOWN, parse


class Variety(NamedTuple):
    name: str
    category: str
    genotype: str
    eyes: str
    coat: str


VARIETIES = [
    Variety('New Zealand White', 'New Zealand', 'aa B_ cc D_ E_ enen SiSi VV',
            'Ruby', 'Pure white; cc epistatic albino masks all underlying color'),
    Variety('New Zealand Red', 'New Zealand', 'A_ B_ C_ D_ ee enen SiSi VV',
            'Dark brown', 'Rich red/chestnut from agouti + non-extension (ee)'),
    Variety('New Zealand Black', 'New Zealand', 'aa B_ C_ D_ E_ enen SiSi VV',
            'Dark brown', 'Solid black self; non-agouti with full extension'),
    Variety('New Zealand Blue', 'New Zealand', 'aa B_ C_ dd E_ enen SiSi VV',
            'Dark brown', 'Dilute black; blue-gray self'),
    Variety('Broken New Zealand (Black)', 'New Zealand', 'aa B_ C_ D_ E_ Enen SiSi VV',
            'Dark brown', 'Black patches on white; En spotting over self black base'),
    Variety('Broken New Zealand (Red)', 'New Zealand', 'A_ B_ C_ D_ ee Enen SiSi VV',
            'Dark brown', 'Red/fawn patches on white; En spotting over non-extension base'),
    Variety('Californian', 'Californian & Pointed', 'aa B_ chch D_ E_ enen SiSi VV',
            'Pink-tinged', 'White body with dark points (nose, ears, feet, tail)'),
    Variety('Broken Californian', 'Californian & Pointed', 'aa B_ chch D_ E_ Enen SiSi VV',
            'Pink-tinged', 'Himalayan-pointed patches on white; broken spotting over Californian base'),
    Variety('Himalayan', 'Californian & Pointed', 'aa B_ chch D_ E_ enen SiSi VV',
            'Pink-tinged', 'Pointed white breed; same Himalayan (ch) mechanism as Californian'),
    Variety('Silver Fox (Black)', 'Silver Fox', 'aa B_ C_ D_ E_ enen sisi VV',
            'Dark brown', 'Born black; progressive silver ticking from sisi. Es steel may be carried hidden on aa selfs.'),
    Variety('Silver Fox (Blue)', 'Silver Fox', 'aa B_ C_ dd E_ enen sisi VV',
            'Dark brown', 'Dilute black base with heavy silvering; blue-gray mature coat'),
    Variety('Silver Fox (Chocolate)', 'Silver Fox', 'aa bb C_ D_ E_ enen sisi VV',
            'Dark brown', 'Chocolate brown base with progressive silver tipping'),
    Variety('Silver Fox (Lilac)', 'Silver Fox', 'aa bb C_ dd E_ enen sisi VV',
            'Dark brown', 'Dilute chocolate base with silver ticking; lilac-gray mature coat'),
    Variety("Champagne d'Argent", "d'Argent & Silvered", 'aa B_ C_ D_ E_ enen sisi VV',
            'Dark brown', 'Born black; silvering develops from ~7–8 weeks. Heavier silver expression than Silver Fox in many lines.'),
    Variety("Crème d'Argent", "d'Argent & Silvered", 'aa B_ C_ D_ ee enen sisi VV',
            'Dark brown', 'Creamy orange/fawn base (ee) with progressive silver ticking; commercial meat body type'),
    Variety('Argente Brun', "d'Argent & Silvered", 'aa bb C_ D_ E_ enen sisi VV',
            'Dark brown', 'Chocolate-based silvered argente; related to Champagne foundation genetics'),
    Variety('Argente Bleu', "d'Argent & Silvered", 'aa B_ C_ dd E_ enen sisi VV',
            'Dark brown', 'Blue (dilute black) silvered argente'),
    Variety('Silver (Breed)', "d'Argent & Silvered", 'A_ B_ C_ D_ E_ enen sisi VV',
            'Dark brown', 'Agouti-based silvered breed; white ticking over wild-type pattern (distinct from Silver Fox self base)'),
    Variety('American Chinchilla', 'Chinchilla', 'A_ B_ cchd_ D_ E_ enen SiSi VV',
            'Dark brown', 'Agouti with dark chinchilla; pearl banding, commercial meat breed'),
    Variety('Giant Chinchilla', 'Chinchilla', 'A_ B_ cchd_ D_ E_ enen SiSi VV',
            'Dark brown', 'Large commercial chinchilla; same cchd modifier on agouti base'),
    Variety('Sable / Siamese Sable', 'Chinchilla', 'A_ B_ cchl_ D_ E_ enen SiSi VV',
            'Dark brown', 'Shaded chinchilla light; darker points, lighter body'),
    Variety('Ermine / Frosted Pearl', 'Chinchilla', 'A_ B_ cchd_ D_ ee enen SiSi VV',
            'Dark brown', 'Chinchilla dark on non-extension (ee) agouti; frosted pearl/ermine'),
    Variety('Checkered Giant (Broken)', 'Broken & Spotted', 'A_ B_ C_ D_ E_ Enen SiSi VV',
            'Dark brown', 'Large spotted meat/show type; Enen broken pattern'),
    Variety('Charlie (EnEn)', 'Broken & Spotted', 'A_ B_ C_ D_ E_ EnEn SiSi VV',
            'Dark brown', 'Nearly all white from homozygous English spotting; often subvital; welfare concern in breeding'),
    Variety('Steel / Silver-Tipped', 'Broken & Spotted', 'A_ B_ C_ D_ Es_ enen SiSi VV',
            'Dark brown', 'Steel (Es) requires agouti (A_); dark coat with silver or gold guard hair tipping'),
    Variety('Self Black', 'Base Colors', 'aa B_ C_ D_ E_ enen SiSi VV',
            'Dark brown', 'Solid black; foundation for many commercial and specialty lines'),
    Variety('Chestnut / Agouti', 'Base Colors', 'A_ B_ C_ D_ E_ enen SiSi VV',
            'Dark brown', 'Wild-type agouti banding; castor/chestnut'),
    Variety('Blue Vienna (BEW)', 'Base Colors', 'aa B_ C_ dd E_ enen SiSi vv',
            'Blue', 'Vienna blue-eyed white; vv overrides coat to white with blue eyes'),
    Variety('Chocolate Self', 'Base Colors', 'aa bb C_ D_ E_ enen SiSi VV',
            'Dark brown', 'Havana-type chocolate brown self'),
    Variety('Lilac Self', 'Base Colors', 'aa bb C_ dd E_ enen SiSi VV',
            'Dark brown', 'Dilute chocolate; lilac/gray self'),
    Variety('Palomino', 'Base Colors', 'A_ B_ cchl_ D_ ee enen SiSi VV',
            'Dark brown', 'Golden fawn from non-extension (ee) with shaded chinchilla modifier'),
]

CATEGORIES = list(dict.fromkeys(variety.category for variety in VARIETIES))


def slug(name):
    keep = "".join(ch if ch.isalnum() else "-" for ch in name.lower().replace("è", "e").replace("'", ""))
    return "-".join(part for part in keep.split("-") if part)


BY_SLUG = {slug(variety.name): variety for variety in VARIETIES}


def genes(summary):
    """{locus: (allele, allele)} from a summary such as "aa B_ cc D_".
    Unknown alleles stay _; tokens that match no locus are skipped."""
    return read(summary)[0]


def read(summary):
    """(genes, unread tokens) from typed text such as "aa B_ cc D_" or
    "a/a B/b": each token is one locus, written either way."""
    out, unread = {}, []
    for token in str(summary or "").replace(",", " ").split():
        for locus in SERIES:
            if locus in out:
                continue
            pair = parse(locus, token)
            if pair is not None and pair != (UNKNOWN, UNKNOWN):
                out[locus] = pair
                break
        else:
            unread.append(token)
    return out, unread


def summary(pairs):
    """The short typed form of {locus: pair}: "aa B_ cc"."""
    return " ".join("".join(pairs[locus]) for locus in SERIES if locus in pairs)


def typical(name_or_slug):
    """The Variety for a variety name or slug, matched loosely, or None."""
    key = slug(str(name_or_slug or ""))
    return BY_SLUG.get(key)


def filled(variety):
    """The variety's genes with each _ read as a second copy of the shown
    allele (B_ as BB). Used where a full genotype is needed, such as a
    breed on the what-if cross page; the page says it assumes this."""
    out = {}
    for locus, pair in genes(variety.genotype).items():
        first = next(allele for allele in pair if allele != UNKNOWN)
        out[locus] = tuple(first if allele == UNKNOWN else allele for allele in pair)
    return out
