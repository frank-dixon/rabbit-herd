"""The Family tree view of a pedigree: five generations from PedigreeEntry,
Relative and herd records, plus siblings, aunts, uncles and cousins, and
litter kits as evidence. Genes come from gene_inference, cached per rabbit
and refreshed whenever anything they were read from changes."""

import hashlib
import json

from django.core.cache import cache
from django.db.models import Q
from django.urls import reverse

from . import gene_inference
from .litter_photos import coat_placeholder_url, outside_photo_url
from .models import Gene, LitterKit, OutsideRabbit, PedigreeEntry, Rabbit, Relative
from .pedigree import build_tree

GENERATIONS = 5
MAX_SIBLINGS = 4
MAX_AUNTS = 2
MAX_COUSINS = 2
CHIP_COLORS = ["#6b4fd8", "#8a5a2b", "#0f7a5c", "#b4234b", "#b86e00", "#2f6fd6", "#5f6b7a", "#9c3fb8"]
CACHE_SECONDS = 60 * 60 * 24 * 7


def key_of(obj):
    return ("r" if isinstance(obj, Rabbit) else "o") + str(obj.pk)


def ahnentafel(position):
    number = 1
    for step in position:
        number = number * 2 + (0 if step == "s" else 1)
    return number


def parents_of(obj):
    """(sire, dam) objects for a herd rabbit from its own records."""
    if not isinstance(obj, Rabbit):
        return None, None
    from .pedigree import known_parents

    found = known_parents(obj.pk)
    return tuple(found.get(step, (None, None))[0] for step in "sd")


def kids_of(owner, obj):
    """Herd rabbits that name obj as sire or dam."""
    field = "herd_rabbit" if isinstance(obj, Rabbit) else "outside"
    ids = set(PedigreeEntry.objects.filter(position__in=["s", "d"], **{field: obj}).values_list("rabbit_id", flat=True))
    ids |= set(Relative.objects.filter(relationship__in=["sire", "dam"], **{field: obj}).values_list("rabbit_id", flat=True))
    if isinstance(obj, Rabbit):
        ids |= set(Rabbit.objects.filter(owner=owner).filter(Q(litter__pairing__doe=obj) | Q(litter__pairing__buck=obj))
                   .values_list("pk", flat=True))
    return Rabbit.objects.filter(owner=owner, pk__in=ids).order_by("birth_date", "pk")


def full_siblings(owner, sire, dam, exclude):
    if sire is None or dam is None:
        return []
    out = []
    for kid in kids_of(owner, sire):
        if kid.pk in exclude:
            continue
        s, d = parents_of(kid)
        if s is not None and d is not None and key_of(s) == key_of(sire) and key_of(d) == key_of(dam):
            out.append(kid)
    return out


def photo_url(obj, color):
    if isinstance(obj, Rabbit):
        main = next((p for p in obj.photos.all() if p.is_main), None)
        if main:
            return reverse("rabbit_photo_file", args=[main.pk]) + f"?v={main.image.name[-12:]}&w=320", False
        return coat_placeholder_url(color or obj.color), True
    if getattr(obj, "photo", None):
        return outside_photo_url(obj, 320), False
    return coat_placeholder_url(color or outside_color(obj)), True


def outside_color(obj):
    """An outside rabbit's color from details like "Black doe · Mini Rex · Fox Hollow"."""
    text = (obj.details or "").split("·")[0].strip()
    for word in (" doe", " buck"):
        if text.lower().endswith(word):
            text = text[: -len(word)]
    return text


def gene_inputs(genes):
    return {g.locus: (g.genotype, g.certainty) for g in genes if g.locus != Gene.Locus.OTHER}


def collect(rabbit):
    """Every rabbit the tree draws or reads, as nodes for gene_inference, plus layout."""
    owner = rabbit.owner
    tree = build_tree(rabbit, GENERATIONS)
    objects, meta, places = {}, {}, {}

    def note(obj, color="", breed="", genes=(), row=None):
        key = key_of(obj)
        objects[key] = obj
        m = meta.setdefault(key, {"color": "", "breed": "", "genes": {}})
        m["color"] = m["color"] or color or (obj.color if isinstance(obj, Rabbit) else outside_color(obj))
        m["breed"] = m["breed"] or breed or (obj.breed if isinstance(obj, Rabbit) else "")
        if isinstance(obj, Rabbit) and "own" not in m:
            m["own"] = True
            m["genes"].update(gene_inputs(obj.genes.all()))
        if row is not None:
            for locus, value in gene_inputs(row.genes.all()).items():
                m["genes"].setdefault(locus, value)
        return key

    subject = note(rabbit)
    places[1] = subject
    rows = {(r.rabbit_id, r.relationship): r for r in Relative.objects.filter(
        relationship__in=["sire", "dam"]).filter(Q(herd_rabbit__isnull=False) | Q(outside__isnull=False))
        .filter(rabbit__owner=owner).prefetch_related("genes")}
    for position, cell in tree.items():
        child = places.get(ahnentafel(position[:-1]))
        row = rows.get((int(child[1:]), "sire" if position.endswith("s" ) else "dam")) if child and child[0] == "r" else None
        places[ahnentafel(position)] = note(cell["rabbit"], cell["color"], cell["breed"], row=row)
    parent = {}
    for number, key in places.items():
        for step, offset in (("sire", 0), ("dam", 1)):
            up = places.get(number * 2 + offset)
            if up:
                parent.setdefault(key, {})[step] = up

    laterals = {}
    seen = {o.pk for k, o in objects.items() if k[0] == "r"}

    def add_lateral(kid, kind, label, anchor):
        key = note(kid)
        s, d = parents_of(kid)
        for step, obj in (("sire", s), ("dam", d)):
            if obj is not None and key_of(obj) in objects:
                parent.setdefault(key, {})[step] = key_of(obj)
        laterals[key] = {"kind": kind, "label": label, "anchor": anchor}
        seen.add(kid.pk)
        return key

    sire, dam = (objects.get(places.get(n)) for n in (2, 3))
    for kid in full_siblings(owner, sire, dam, seen)[:MAX_SIBLINGS]:
        add_lateral(kid, "sibling", "Littermate" if kid.birth_date == rabbit.birth_date else "Full sibling", 1)
    for number, side in ((2, "Sire's"), (3, "Dam's")):
        gs, gd = (objects.get(places.get(number * 2 + o)) for o in (0, 1))
        par = objects.get(places.get(number))
        for aunt in full_siblings(owner, gs, gd, seen)[:MAX_AUNTS]:
            word = "brother" if aunt.sex == Rabbit.Sex.BUCK else "sister"
            akey = add_lateral(aunt, "aunt", f"{side} {word}" if par is None else f"{par.name}'s {word}", number)
            for cousin in kids_of(owner, aunt).exclude(pk__in=seen)[:MAX_COUSINS]:
                add_lateral(cousin, "cousin", "Cousin", akey)

    # Kits recorded on a litter but never added to the herd still prove what their parents carry.
    herd_keys = {int(k[1:]) for k in objects if k[0] == "r"}
    evidence = {}
    for slot in LitterKit.objects.filter(rabbit__isnull=True, litter__owner=owner).exclude(color="").filter(
            litter__pairing__doe_id__in=herd_keys, litter__pairing__buck_id__in=herd_keys).select_related("litter__pairing"):
        pairing = slot.litter.pairing
        key = f"k{slot.pk}"
        evidence[key] = {"name": f"Kit {slot.number} of {pairing.doe.name} × {pairing.buck.name}", "color": slot.color,
                         "sire": f"r{pairing.buck_id}", "dam": f"r{pairing.doe_id}", "breed": "", "genes": {}}

    nodes = {}
    for key, obj in objects.items():
        m = meta[key]
        nodes[key] = {"name": obj.name, "color": m["color"], "breed": m["breed"],
                      "eye": obj.eye_color if isinstance(obj, Rabbit) else "", "genes": m["genes"],
                      "sire": parent.get(key, {}).get("sire"), "dam": parent.get(key, {}).get("dam")}
    nodes.update(evidence)
    return {"subject": subject, "objects": objects, "nodes": nodes, "places": places, "laterals": laterals}


def inferred(rabbit, nodes):
    """gene_inference results for these nodes, cached per rabbit until any input changes."""
    digest = hashlib.sha1(json.dumps(nodes, sort_keys=True, default=str).encode()).hexdigest()
    cache_key = f"family-genes:{rabbit.pk}"
    saved = cache.get(cache_key)
    if saved and saved.get("digest") == digest:
        return saved["results"]
    results = gene_inference.infer(nodes)
    cache.set(cache_key, {"digest": digest, "results": results}, CACHE_SECONDS)
    return results


def chips(nodes, results, drawn):
    """Gene chips worth tracing: alleles below the top of their series (and broken), held by someone drawn."""
    counts = {}
    for key in drawn:
        for locus in gene_inference.LOCI:
            for rec in results[key][locus]["pair"]:
                a = rec["allele"]
                if a and rec["level"] in (gene_inference.KNOWN, gene_inference.PROBABLE) and gene_inference.notable(locus, a):
                    counts[(locus, a)] = counts.get((locus, a), 0) + 1
    picked = sorted((k for k in counts if counts[k] >= 2), key=lambda k: (-counts[k], k))[:6]
    out = []
    for index, (locus, allele) in enumerate(picked):
        t = gene_inference.thread(nodes, results, locus, allele)
        out.append({
            "id": f"{locus}-{allele}", "locus": locus, "allele": allele,
            "label": gene_inference.ALLELE_NAMES.get(allele, allele), "color": CHIP_COLORS[index % len(CHIP_COLORS)],
            "nodes": {k: list(v) for k, v in t["nodes"].items() if k in drawn},
            "edges": [list(e) for e in t["edges"] if e[0] in drawn and e[1] in drawn],
            "sources": [k for k in t["sources"] if k in drawn],
        })
    return out


def payload(rabbit):
    data = collect(rabbit)
    nodes, objects = data["nodes"], data["objects"]
    results = inferred(rabbit, nodes)
    drawn = set(objects)
    gens = {}
    for number, key in data["places"].items():
        gens[key] = min(gens.get(key, 9), number.bit_length() - 1)
    out = {}
    for key, obj in objects.items():
        herd = isinstance(obj, Rabbit)
        src, placeholder = photo_url(obj, nodes[key]["color"])
        node = nodes[key]
        out[key] = {
            "name": obj.name, "color": node["color"], "breed": node["breed"],
            "sex": obj.get_sex_display() if herd else "", "born": obj.birth_date.isoformat() if herd else "",
            "tattoo": obj.tattoo if herd else "", "url": reverse("rabbit_pedigree", args=[obj.pk]) if herd else "",
            "detail": reverse("rabbit_detail", args=[obj.pk]) if herd else "",
            "outside": not herd, "img": src, "placeholder": placeholder,
            "sire": node["sire"], "dam": node["dam"],
            "genes": {locus: results[key][locus] for locus in gene_inference.LOCI},
            "changes": gene_inference.changes(nodes, results, key),
            "kits": sorted({k for k, n in nodes.items() if key in (n.get("sire"), n.get("dam")) and k in drawn},
                           key=lambda k: nodes[k]["name"]),
            "lateral": data["laterals"].get(key),
            "gen": gens.get(key),
        }
    return {
        "subject": data["subject"], "nodes": out,
        "places": {str(n): k for n, k in sorted(data["places"].items())},
        "chips": chips(nodes, results, drawn),
        "evidence": len(nodes) - len(drawn),
    }
