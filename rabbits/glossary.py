"""Glossary: the terms the app uses, each with the published source it rests on.

Every entry cites at least one real, checked source (a peer-reviewed paper, a
gene database entry, an extension publication or the ARBA). Nothing here is
written without one; add a source to SOURCES before adding a term that uses it.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

SOURCES = {
    "nhgri": ("National Human Genome Research Institute. Talking Glossary of Genomic and Genetic Terms.",
              "https://www.genome.gov/genetics-glossary"),
    "asip": ("Fontanesi L, Forestier L, Allain D, et al. (2010). Characterization of the rabbit agouti signaling protein "
             "(ASIP) gene: transcripts and phylogenetic analyses and identification of the causative mutation of the "
             "nonagouti black coat colour. Genomics 95(3):166–175.", "https://doi.org/10.1016/j.ygeno.2009.11.003"),
    "omia-agouti": ("OMIA 000201-9986: Coat colour, agouti in Oryctolagus cuniculus (rabbit). Online Mendelian "
                    "Inheritance in Animals.", "https://omia.org/OMIA000201/9986/"),
    "tyrp1": ("Utzeri VJ, Ribani A, Fontanesi L (2014). A premature stop codon in the TYRP1 gene is associated with "
              "brown coat colour in the European rabbit (Oryctolagus cuniculus). Animal Genetics 45(4):600–603.",
              "https://omia.org/OMIA001249/9986/"),
    "tyr": ("Aigner B, Besenfelder U, Müller M, Brem G (2000). Tyrosinase gene variants in different rabbit strains. "
            "Mammalian Genome 11:700–702.", "https://doi.org/10.1007/s003350010120"),
    "omia-albino": ("OMIA 000202-9986: Coat/skin colour, oculocutaneous albinism type I (OCA1), TYR-related in "
                    "Oryctolagus cuniculus (rabbit). Online Mendelian Inheritance in Animals.",
                    "https://omia.org/OMIA000202/9986/"),
    "tyr-variability": ("Describing variability in the tyrosinase (TYR) gene, the albino coat colour locus, in domestic "
                        "and wild European rabbits. University of Bologna research archive.",
                        "https://cris.unibo.it/handle/11585/805740"),
    "mlph": ("Fontanesi L, Scotti E, Allain D, Dall'Olio S (2014). A frameshift mutation in the melanophilin gene causes "
             "the dilute coat colour in rabbit (Oryctolagus cuniculus) breeds. Animal Genetics 45(2):248–255.",
             "https://doi.org/10.1111/age.12104"),
    "mc1r": ("Fontanesi L, Tazzoli M, Beretti F, Russo V (2006). Mutations in the melanocortin 1 receptor (MC1R) gene are "
             "associated with coat colours in the domestic rabbit (Oryctolagus cuniculus). Animal Genetics 37(5):489–493.",
             "https://doi.org/10.1111/j.1365-2052.2006.01494.x"),
    "omia-extension": ("OMIA 001199-9986: Coat colour, extension in Oryctolagus cuniculus (rabbit). Online Mendelian "
                       "Inheritance in Animals.", "https://omia.org/OMIA001199/9986/"),
    "kit": ("Fontanesi L, Vargiolu M, Scotti E, et al. (2014). The KIT gene is associated with the English spotting coat "
            "color locus and congenital megacolon in Checkered Giant rabbits (Oryctolagus cuniculus). PLoS ONE 9(4):e93750.",
            "https://doi.org/10.1371/journal.pone.0093750"),
    "omia-spotting": ("OMIA 001597-9986: Coat colour, English spotting in Oryctolagus cuniculus (rabbit). Online "
                      "Mendelian Inheritance in Animals.", "https://omia.org/OMIA001597/9986/"),
    "usu": ("Okoh J, Hadfield J (2025). Rabbit Breeding and Management: A Guide for Producers. Utah State University "
            "Extension.", "https://extension.usu.edu/small-acreage-livestock/research/rabbit-breeding-and-management-a-guide-for-producers"),
    "hawaii": ("Vogt DW. Raising Rabbits in Hawaii. Circular 499, Cooperative Extension Service, College of Tropical "
               "Agriculture and Human Resources, University of Hawaii at Manoa.",
               "https://www3.ctahr.hawaii.edu/oc/freepubs/pdf/C1-499.pdf"),
    "msu": ("Commercial Rabbit Production. Mississippi State University Extension.",
            "https://www.poultry.msstate.edu/pdf/extension/rabbit_production.pdf"),
    "arba-gc": ("American Rabbit Breeders Association. Grand Champions (how to apply).",
                "https://arba.net/wp-content/uploads/2019/11/Grand-Champion-How-To.pdf"),
}

# (section, [(term, symbol, definition, [source keys]), ...])
SECTIONS = [
    ("Genetics basics", [
        ("Allele", "", "One of the versions of a gene. A rabbit carries two alleles at each gene, one from each parent.", ["nhgri"]),
        ("Locus", "", "The place on a chromosome where a gene sits. Coat color genes are often called by their locus letter: A, B, C, D, E, En.", ["nhgri"]),
        ("Genotype", "", "The alleles a rabbit carries, written as pairs such as aa or B_. A dash or underscore means the second allele is not known.", ["nhgri"]),
        ("Phenotype", "", "What you can see or measure, such as the coat color, as opposed to the alleles behind it.", ["nhgri"]),
        ("Dominant", "", "An allele that shows its effect when only one copy is present. Dominant alleles are written with a capital letter.", ["nhgri"]),
        ("Recessive", "", "An allele that shows its effect only when both copies are that allele. Recessive alleles are written in lower case.", ["nhgri"]),
        ("Homozygous", "", "Carrying two copies of the same allele at a locus, such as aa or DD.", ["nhgri"]),
        ("Heterozygous", "", "Carrying two different alleles at a locus, such as Aa. A heterozygous rabbit can pass on either one.", ["nhgri"]),
    ]),
    ("Color loci", [
        ("Agouti", "A", "The ASIP gene. Classical studies describe three alleles: A, light-bellied agouti (the wild type); at, black and tan; and a, black non-agouti. The a allele is a one-base insertion that stops the protein, and aa rabbits are self (non-agouti).", ["asip", "omia-agouti"]),
        ("Brown", "B", "The TYRP1 gene. The recessive b allele, a premature stop codon in TYRP1, is associated with brown coat color; it was found in Havana rabbits.", ["tyrp1"]),
        ("Color series", "C", "The TYR (tyrosinase) gene, also called the albino locus. Classical studies list full color (C), dark, medium and light chinchilla, Himalayan (ch) and albino (c). Albino rabbits carry the p.T373K change; Himalayan and chinchilla alleles carry p.E294G.", ["tyr", "omia-albino", "tyr-variability"]),
        ("Dilute", "D", "The MLPH (melanophilin) gene. The recessive d allele, a one-base deletion, dilutes both black and red/yellow pigment, so black becomes blue. dd was found in all Blue Vienna and other blue, gray or ash rabbits studied.", ["mlph"]),
        ("Extension", "E", "The MC1R gene. The recessive e allele (a 30-base deletion) is carried in two copies by red, fawn and yellow rabbits. A 6-base deletion, dominant to e, may be the dominant black (ED) or steel (ES) allele. The Japanese allele ej is also at this locus.", ["mc1r", "omia-extension"]),
        ("English spotting", "En", "The KIT gene region. en/en rabbits are solid (self-colored), En/en rabbits are normally spotted (broken), and En/En rabbits have a reduced spotted pattern (charlie). In Checkered Giants, En/En was linked to congenital megacolon.", ["kit", "omia-spotting"]),
    ]),
    ("Colors and patterns", [
        ("Self", "aa", "A non-agouti coat: two copies of a at the agouti locus, without the light belly of the wild-type agouti.", ["asip"]),
        ("Tan pattern", "at", "The black and tan allele at the agouti locus.", ["asip"]),
        ("Ruby-eyed white (REW)", "cc", "An albino rabbit: two copies of the c allele at the color series, so no pigment forms. New Zealand Whites are albino.", ["tyr", "omia-albino"]),
        ("Himalayan", "ch", "The color-series allele that limits pigment to the points (nose, ears, feet, tail), as in Californians.", ["tyr", "tyr-variability"]),
        ("Chinchilla", "cchd, cchm, cchl", "The dark, medium and light chinchilla alleles of the color series, which reduce or remove red/yellow pigment (pheomelanin).", ["tyr", "tyr-variability"]),
        ("Steel", "ES", "The steel allele in the classical extension nomenclature. The MC1R 6-base deletion dominant to e may be steel (ES) or dominant black (ED).", ["mc1r"]),
        ("Solid", "en en", "No English spotting: a colored rabbit with no white pattern from the En locus.", ["kit", "omia-spotting"]),
        ("Broken", "En en", "One copy of English spotting: the normal spotted pattern, with large colored patches.", ["kit", "omia-spotting"]),
        ("Charlie", "En En", "Two copies of English spotting: a reduced spotted pattern, with much smaller colored patches than a broken.", ["kit", "omia-spotting"]),
    ]),
    ("Breeding", [
        ("Cover", "", "One mating. Several matings within a day are fine; count the gestation days from the first mating that took.", ["usu"]),
        ("Gestation", "", "The time from mating to kindling. It averages 31 days, with a range from about 29 to 33 days, and varies with breed and litter size.", ["hawaii", "usu"]),
        ("Palpate", "", "Feeling the doe's belly for developing embryos, which feel like chains of marbles, to check for pregnancy about 14 days after mating. A doe found empty can be rebred at once.", ["msu"]),
        ("Kindling", "", "Giving birth, in rabbits.", ["hawaii"]),
        ("False pregnancy", "", "A doe that seems pregnant but is not, often after a sterile mating or stimulation by other rabbits. It lasts about 17 days.", ["usu", "msu"]),
    ]),
    ("Shows", [
        ("Leg", "", "A qualifying win at an ARBA-sanctioned show, recorded on a leg slip. Legs count toward a grand champion certificate.", ["arba-gc"]),
        ("Grand champion", "", "An ARBA certificate for a registered rabbit with at least three legs: from three different shows, under at least two judges, with one a 6/8 or senior win, all for the same ear number, sex and breed.", ["arba-gc"]),
    ]),
]


def numbered():
    """Sections with each term's sources as [(number, key)], numbered in first-use order."""
    order = {}
    sections = []
    for title, terms in SECTIONS:
        rows = []
        for term, symbol, text, keys in terms:
            refs = []
            for key in dict.fromkeys(keys):
                order.setdefault(key, len(order) + 1)
                refs.append(order[key])
            slug = "".join(ch if ch.isalnum() else "-" for ch in term.lower()).strip("-")
            rows.append({"term": term, "symbol": symbol, "text": text, "refs": refs, "slug": slug})
        sections.append({"title": title, "slug": title.lower().replace(" ", "-"), "terms": rows})
    references = [{"n": n, "key": key, "text": SOURCES[key][0], "url": SOURCES[key][1]}
                  for key, n in sorted(order.items(), key=lambda item: item[1])]
    return sections, references


@login_required
def glossary(request):
    sections, references = numbered()
    return render(request, "rabbits/glossary.html", {"sections": sections, "references": references, "wide": True})
