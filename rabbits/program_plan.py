"""Turns a Program into what its pages show: the ranked starting pairings,
the breeders, and the two-generation plan with odds, COI and dates. All the
genetics is in rabbits.planner; this module reads the herd and words it."""

import datetime
from fractions import Fraction

from django.utils import timezone

from . import planner as P
from .color_odds import UNKNOWN
from . import routes as routes_mod
from .models import Gene, Litter, Pairing, Rabbit, Relative, prefs
from .pedigree import known_parents

FULL = {"B": "B_", "C": "C_", "D": "D_", "E": "E_"}
# Common show and fancy colors as targets: (key, label, description, {locus: pattern}).
TARGETS = [
    ("broken-black", "Broken black", "Black pattern on white, 10–50% color", {"A": "aa", **FULL, "En": "Enen"}),
    ("broken-blue", "Broken blue", "Blue pattern on white", {"A": "aa", "B": "B_", "C": "C_", "D": "dd", "E": "E_", "En": "Enen"}),
    ("broken-chocolate", "Broken chocolate", "Chocolate pattern on white", {"A": "aa", "B": "bb", "C": "C_", "D": "D_", "E": "E_", "En": "Enen"}),
    ("broken-chestnut", "Broken chestnut", "Chestnut agouti pattern on white", {"A": "A_", **FULL, "En": "Enen"}),
    ("broken-orange", "Broken orange", "Orange pattern on white", {"A": "A_", "B": "B_", "C": "C_", "D": "D_", "E": "ee", "En": "Enen"}),
    ("black", "Black", "Solid black self", {"A": "aa", **FULL, "En": "enen"}),
    ("blue", "Blue", "Solid blue self", {"A": "aa", "B": "B_", "C": "C_", "D": "dd", "E": "E_", "En": "enen"}),
    ("chocolate", "Chocolate", "Solid chocolate self", {"A": "aa", "B": "bb", "C": "C_", "D": "D_", "E": "E_", "En": "enen"}),
    ("lilac", "Lilac", "Solid lilac self", {"A": "aa", "B": "bb", "C": "C_", "D": "dd", "E": "E_", "En": "enen"}),
    ("chestnut", "Chestnut agouti", "Banded agouti, black ticking", {"A": "A_", **FULL, "En": "enen"}),
    ("opal", "Opal", "Blue agouti with fawn band", {"A": "A_", "B": "B_", "C": "C_", "D": "dd", "E": "E_", "En": "enen"}),
    ("otter", "Black otter", "Black with tan belly and eye circles", {"A": "at_", **FULL, "En": "enen"}),
    ("tort", "Tortoiseshell", "Orange body, black points", {"A": "aa", "B": "B_", "C": "C_", "D": "D_", "E": "ee", "En": "enen"}),
    ("orange", "Orange", "Bright orange, cream belly", {"A": "A_", "B": "B_", "C": "C_", "D": "D_", "E": "ee", "En": "enen"}),
    ("fawn", "Fawn", "Dilute orange", {"A": "A_", "B": "B_", "C": "C_", "D": "dd", "E": "ee", "En": "enen"}),
    ("rew", "Ruby-eyed white", "Albino, pink eyes", {"C": "cc"}),
]
TARGET_KEYS = {key: (label, text, genes) for key, label, text, genes in TARGETS}
G2_AGE_DAYS = 183  # a kept doe or buck is bred at about six months
GOAL_LAG_DAYS = 56  # kits are judged at about eight weeks
DEFAULT_LITTER = 7


def target_text(target):
    """"aa E_ Enen" for the chip, in locus order, written as the board does."""
    order = ["A", "B", "C", "D", "E", "En"]
    return " ".join(spaced(locus, target[locus]) for locus in order if locus in target and target[locus] not in FULL.values())


def spaced(locus, text):
    """"Enen" -> "En en", "aa" -> "aa" (two-letter alleles get a space)."""
    if locus == "En" and text in ("Enen", "EnEn", "enen", "En_"):
        return {"Enen": "En en", "EnEn": "En En", "enen": "en en", "En_": "En _"}[text]
    return text


def pairs_text(genes, target):
    """The parent's genotype at the loci the target cares about: "aa En en"."""
    loci = [locus for locus in P.PLAN_LOCI if locus in target and target[locus] not in FULL.values()] or list(target)
    out = []
    for locus in loci:
        a, b = genes.get(locus, (UNKNOWN, UNKNOWN))
        out.append(f"{a} {b}" if locus == "En" or len(a) > 1 or len(b) > 1 else f"{a}{b}")
    return " ".join(out)


def nice_date(day, approx=False):
    if day is None:
        return ""
    text = f"{day:%a, %b} {day.day}"
    if day.year != timezone.localdate().year:
        text += f", {day.year}"
    return ("~" if approx else "") + text


def month_text(day):
    return f"~{day:%b %Y}"


# Breeders ---------------------------------------------------------------------

def rabbit_genes(rabbit):
    texts = {g.locus: g.genotype for g in rabbit.genes.all() if g.locus != Gene.Locus.OTHER}
    return P.read_genes(texts)


def herd_breeders(user):
    """Rabbits still in the herd; sold, culled and deceased ones are gone."""
    return list(Rabbit.objects.filter(owner=user, archived_at__isnull=True)
                .exclude(status__in=Rabbit.FORMER).prefetch_related("genes", "photos")
                .select_related("sold_to").order_by("name", "pk"))


def open_litter(doe):
    """The doe's current breeding (not yet kindled, or kindled under 8 weeks ago)."""
    recent = timezone.localdate() - datetime.timedelta(days=56)
    return (Litter.objects.filter(pairing__doe=doe).filter(kindled_on__isnull=True).order_by("-bred_on").first()
            or Litter.objects.filter(pairing__doe=doe, kindled_on__gte=recent).order_by("-bred_on").first())


def candidates(program):
    """Every breeder the program can use, as plain dicts keyed "h:<pk>" or "x:<pk>"."""
    out = []
    for r in herd_breeders(program.owner):
        sold = r.status == Rabbit.Status.SOLD
        litter = open_litter(r) if r.sex == "doe" and not sold else None
        where = "In herd" + (" · bred" if litter else "")
        if sold:
            where = f"Sold {nice_date(r.sold_on)} · ask buyer" if r.sold_on else "Sold · ask buyer"
        out.append({"key": f"h:{r.pk}", "node": ("h", r.pk), "name": r.name, "sex": r.sex, "rabbit": r,
                    "breed": r.short_breed or "Unknown", "genes": rabbit_genes(r), "where": where, "sold": sold,
                    "outside": False, "litter": litter})
    for b in program.outside.all():
        out.append({"key": f"x:{b.pk}", "node": ("x", b.pk), "name": b.name, "sex": b.sex, "rabbit": None, "breeder": b,
                    "breed": b.rabbitry or b.breed or "Outside", "genes": P.read_genes(b.genes),
                    "where": "Outside buck" if b.sex == "buck" else "Outside doe", "sold": False, "outside": True, "litter": None})
    return out


def pedigree(user):
    """Parents of every herd rabbit, for Wright's COI. Outside rabbits named as
    parents are nodes without parents of their own."""
    parents = {}
    for r in Rabbit.all_objects.filter(owner=user).only("pk"):
        found = known_parents(r.pk)
        node = lambda other: None if other is None else (("h" if isinstance(other, Rabbit) else "o"), other.pk)
        sire = found.get("s", (None, None))[0]
        dam = found.get("d", (None, None))[0]
        if sire is not None or dam is not None:
            parents[("h", r.pk)] = (node(sire), node(dam))
    return P.Pedigree(parents)


# Ranking ------------------------------------------------------------------------

def pairing_note(program, doe, buck, low, high):
    notes = []
    if buck["sold"]:
        notes.append("Sold.")
    litter = doe["litter"]
    if litter and buck["rabbit"] is not None and litter.pairing.buck_id == buck["rabbit"].pk:
        notes.append(f"Already bred {nice_date(litter.bred_on)}, due {nice_date(litter.due_on)}. Uses this litter.")
    elif litter:
        notes.append(f"{doe['name']} is already bred.")
    unknown = [locus for locus in program.target if UNKNOWN in buck["genes"].get(locus, (UNKNOWN,)) and program.target[locus] not in FULL.values()]
    unknown_doe = [locus for locus in program.target if UNKNOWN in doe["genes"].get(locus, (UNKNOWN,)) and program.target[locus] not in FULL.values()]
    if high == 0:
        notes.append(f"No {program.target_label.lower()} kits from this pair.")
    elif low != high:
        who = buck if unknown else doe
        loci = unknown or unknown_doe
        notes.append(f"{who['name']}’s {' and '.join(loci)} genes are unknown.")
    if not notes and high > 0:
        notes.append("Good odds." if high >= Fraction(1, 2) else "Some target kits.")
    return " ".join(notes)


def ranked_pairings(program, breeders, ped):
    does = [b for b in breeders if b["sex"] == "doe" and not b["sold"] and not b["outside"]]
    bucks = [b for b in breeders if b["sex"] == "buck"]
    rows = []
    for doe in does:
        for buck in bucks:
            low, high = P.target_odds(program.target, doe["genes"], buck["genes"])
            coi = ped.coi(buck["node"], doe["node"])
            bred_here = bool(doe["litter"] and buck["rabbit"] is not None and doe["litter"].pairing.buck_id == buck["rabbit"].pk)
            rows.append({"doe": doe, "buck": buck, "low": low, "high": high, "odds": P.range_text(low, high),
                         "coi": coi, "coi_text": P.percent_text(coi), "over": coi * 100 > program.max_coi,
                         "bred_here": bred_here, "note": pairing_note(program, doe, buck, low, high),
                         "value": f"{doe['key']}|{buck['key']}"})
    rows.sort(key=lambda r: (r["over"], -r["high"], -r["low"], r["coi"], r["doe"]["name"], r["buck"]["name"]))
    return rows


# The plan -------------------------------------------------------------------

def find(breeders, key):
    return next((b for b in breeders if b["key"] == key), None)


def sire_key(program, generation=1):
    if generation == 1:
        return f"h:{program.sire_id}" if program.sire_id else (f"x:{program.sire_outside_id}" if program.sire_outside_id else "")
    return f"h:{program.g2_sire_id}" if program.g2_sire_id else (f"x:{program.g2_outside_id}" if program.g2_outside_id else "")


def g2_options(program, dam, sire, breeders, ped):
    """Mates for a kept G1 kit, best first: odds, then COI."""
    kit_node = ("g1", program.pk)
    ped.parents[kit_node] = (sire["node"], dam["node"])
    want = "buck" if program.keep_sex != "buck" else "doe"
    rows = []
    for mate in breeders:
        if mate["sex"] != want:
            continue
        odds = P.kept_odds(program.target, dam["genes"], sire["genes"], mate["genes"])
        coi = ped.coi(mate["node"], kit_node) if want == "buck" else ped.coi(kit_node, mate["node"])
        relation = "father × daughter" if mate["key"] == sire["key"] else ("mother × son" if mate["key"] == dam["key"] else "")
        rows.append({"mate": mate, "odds": odds, "coi": coi, "over": coi * 100 > program.max_coi, "relation": relation})
    rows.sort(key=lambda r: mate_rank(program, r))
    return rows


def mate_rank(program, row):
    """Sort key for G2 mates: within the COI limit first, then any chance of
    the target at all; for a broken target a
    known solid (en en) mate before any that could throw charlies; then target
    odds, inbreeding and name."""
    charlie_risk = program.target.get("En") == "Enen" and row["mate"]["genes"].get("En") != ("en", "en")
    return (row["over"], row["odds"] == 0, charlie_risk, -row["odds"], row["coi"], row["mate"]["name"])


def grouped(rows, keep=4):
    """Outcome rows trimmed for reading: the target, charlies as one row, the
    most likely others, and everything else as "Other colors"."""
    target = [r for r in rows if r["target"]]
    charlie = [r for r in rows if not r["target"] and r["name"].startswith("Charlie")]
    rest = sorted((r for r in rows if not r["target"] and r not in charlie), key=lambda r: -r["chance"])
    out = target + rest[:keep]
    if rest[keep:]:
        out.append({"name": "Other colors", "target": False, "chance": sum(r["chance"] for r in rest[keep:])})
    if charlie:
        out.append({"name": "Charlies", "target": False, "chance": sum(r["chance"] for r in charlie)})
    return out


def bars(rows):
    """Outcome rows with a CSS shade: the target in accent, the rest paler, charlies in red."""
    rows = grouped(rows)
    shades = ["s1", "s2", "s3", "s4", "s5"]
    out, i = [], 0
    for row in rows:
        if row["target"]:
            shade = "target"
        elif row["name"].startswith("Charlie"):
            shade = "charlie"
        else:
            shade = shades[min(i, len(shades) - 1)]
            i += 1
        out.append({**row, "shade": shade, "pct": P.percent_text(row["chance"], 0), "width": float(row["chance"]) * 100})
    return out


def litter_size(user):
    sizes = [l.born_alive for l in Litter.objects.filter(owner=user, born_alive__isnull=False).only("born_alive")[:30] if l.born_alive]
    return round(sum(sizes) / len(sizes)) if len(sizes) >= 3 else DEFAULT_LITTER


def build(program):
    """Everything the program page shows, or {"missing": ...} before setup is done."""
    breeders = candidates(program)
    ped = pedigree(program.owner)
    dam = find(breeders, f"h:{program.dam_id}") if program.dam_id else None
    sire = find(breeders, sire_key(program))
    picked = {b["key"] for b in (dam, sire) if b}
    plan = {"breeders": breeders, "picked": picked, "target_text": target_text(program.target)}
    if not (dam and sire):
        plan["missing"] = True
        return plan
    g1_rows = bars(P.outcomes(program.target, dam["genes"], sire["genes"]))
    low, high = P.target_odds(program.target, dam["genes"], sire["genes"])
    g1_coi = ped.coi(sire["node"], dam["node"])
    litter = dam["litter"] if dam["litter"] and sire["rabbit"] is not None and dam["litter"].pairing.buck_id == sire["rabbit"].pk else None
    today = timezone.localdate()
    gestation = prefs(program.owner).gestation_days
    g1_due = litter.due_on if litter else today + datetime.timedelta(days=gestation)
    g1_born = litter.kindled_on if litter and litter.kindled_on else g1_due
    options = g2_options(program, dam, sire, breeders, ped)
    chosen_key = sire_key(program, 2)
    g2 = next((o for o in options if o["mate"]["key"] == chosen_key), None) or (options[0] if options else None)
    alt = next((o for o in options if g2 and o["mate"]["key"] != g2["mate"]["key"]), None)
    n = litter_size(program.owner)
    kept = P.kept_genes(program.target, dam["genes"], sire["genes"])
    keep_word = {"doe": "does", "buck": "bucks"}.get(program.keep_sex, "kits")
    kit_word = {"doe": "doe", "buck": "buck"}.get(program.keep_sex, "kit")
    plan.update({
        "dam": dam, "sire": sire, "litter": litter, "n": n, "keep_word": keep_word, "kit_word": kit_word,
        "g1": {"rows": g1_rows, "odds": P.range_text(low, high), "low": low, "high": high, "coi": P.percent_text(g1_coi),
               "genes": f"{pairs_text(dam['genes'], program.target)} × {pairs_text(sire['genes'], program.target)}",
               "bred": nice_date(litter.bred_on) if litter else "", "due": nice_date(g1_due, approx=not litter),
               "status": "In progress" if litter else "Planned", "expected": P.expected_text(n, high),
               "kept_text": pairs_text(kept, program.target) if kept else ""},
        "options": options, "alt": alt,
    })
    if g2:
        mate = g2["mate"]
        g2_date = g1_born + datetime.timedelta(days=G2_AGE_DAYS)
        g2_due = g2_date + datetime.timedelta(days=gestation)
        kit = {locus: pair for locus, pair in (kept or {}).items()}
        g2_rows = bars(P.outcomes(program.target, kit, mate["genes"])) if program.keep_sex != "buck" else bars(P.outcomes(program.target, mate["genes"], kit))
        p = g2["odds"]
        sex_share = Fraction(1, 2) if program.keep_sex in ("doe", "buck") else Fraction(1)
        plan["g2"] = {
            "mate": mate, "odds": P.percent_text(p, 0), "chance": p, "coi": P.percent_text(g2["coi"]), "over": g2["over"],
            "rows": g2_rows, "date": nice_date(g2_date, approx=True), "due": nice_date(g2_due, approx=True),
            "genes": f"{pairs_text(kit, program.target)} × {pairs_text(mate['genes'], program.target)}",
            "pair_label": f"G1 {kit_word} × {mate['name']}", "expected": P.expected_text(n, p),
            "note": g2_note(program, g2, high), "start": g2_date,
            "hits": P.percent_text(P.at_least(n, program.keep_count, p), 0),
            "kept": P.percent_text(P.at_least(n, program.keep_count, p * sex_share), 0),
            "goal_date": month_text(g2_due + datetime.timedelta(days=GOAL_LAG_DAYS)),
        }
        if alt:
            plan["alt_row"] = {"label": f"G1 {kit_word} × {alt['mate']['name']}", "odds": P.percent_text(alt["odds"], 0),
                               "coi": P.percent_text(alt["coi"]) + (f" ({alt['relation']})" if alt["relation"] else ""),
                               "genes": f"{pairs_text(kit, program.target)} × {pairs_text(alt['mate']['genes'], program.target)}",
                               "expected": P.expected_text(n, alt["odds"]), "advice": "Not recommended" if alt["over"] else "Alternative",
                               "mate": alt["mate"]}
    plan["charlie_tip"] = program.target.get("En") == "Enen"
    if plan.get("g2"):
        charlies = next((r for r in plan["g2"]["rows"] if r["name"] == "Charlies"), None)
        plan["g2"]["charlies"] = charlies["pct"] if charlies else ""
    seen = {}
    for row in g1_rows + plan.get("g2", {}).get("rows", []):
        seen.setdefault(row["name"], row)
    plan["legend"] = list(seen.values())
    plan["progress"] = progress(program, dam, sire, plan.get("g2"))
    return plan


def g2_note(program, g2, g1_high):
    mate = g2["mate"]
    parts = []
    pattern = {"Enen": "Broken", "EnEn": "Charlie", "enen": "Solid"}.get("".join(mate["genes"].get("En", ("_", "_"))), "")
    lead = " ".join(w for w in (pattern, "outside" if mate["outside"] else "herd", "buck" if mate["sex"] == "buck" else "doe") if w)
    lead = lead[0].upper() + lead[1:]
    if g1_high and g2["odds"] >= 2 * g1_high:
        parts.append("double the target odds")
    elif g1_high and g2["odds"] > g1_high:
        parts.append("better target odds")
    if program.target.get("En") == "Enen" and mate["genes"].get("En") == ("en", "en"):
        parts.append("no charlies")
    parts.append(f"COI {P.percent_text(g2['coi'])}")
    return f"{lead}: {', '.join(parts)}."


def progress(program, dam, sire, g2):
    """Kept target kits from G2 so far: herd rabbits of the keep sex whose dam
    or sire is a G1 kit of this pairing and whose other parent is the G2 mate."""
    if not (dam["rabbit"] and sire["rabbit"]):
        g1_kits = []
    else:
        dam_kids = set(Relative.objects.filter(relationship="dam", herd_rabbit=dam["rabbit"]).values_list("rabbit_id", flat=True))
        sire_kids = set(Relative.objects.filter(relationship="sire", herd_rabbit=sire["rabbit"]).values_list("rabbit_id", flat=True))
        g1_kits = list(dam_kids & sire_kids)
    kept = 0
    if g1_kits and g2 and g2["mate"]["rabbit"] is not None:
        kids = Rabbit.objects.filter(relatives__relationship__in=["dam", "sire"], relatives__herd_rabbit_id__in=g1_kits) \
            .filter(relatives__herd_rabbit=g2["mate"]["rabbit"]).exclude(status__in=[Rabbit.Status.DECEASED, Rabbit.Status.SOLD]).distinct()
        if program.keep_sex in ("doe", "buck"):
            kids = kids.filter(sex=program.keep_sex)
        label = program.target_label.lower()
        kept = sum(1 for k in kids.prefetch_related("genes") if (k.color or "").strip().lower() == label
                   or all(P.matches(locus, pattern, pair) for locus, pattern in program.target.items()
                          for pair in [rabbit_genes(k)[locus]] if UNKNOWN not in pair))
    return {"kept": min(kept, program.keep_count), "of": program.keep_count, "pct": min(100, round(100 * kept / max(program.keep_count, 1))),
            "generation": 2 if g1_kits else 1, "g1_kits": len(g1_kits)}


# Routes and reachable goals --------------------------------------------------

STATE_WORDS = {"ready": "In herd", "access": "Needs access", "evidence": "Deceased: genetic evidence only"}
ALLELE_WORDS = {"b": "chocolate", "d": "dilute", "a": "self", "at": "tan pattern", "e": "non-extension (orange/fawn)",
                "ej": "Japanese harlequin", "c": "ruby-eyed white", "ch": "Himalayan", "cchd": "dark chinchilla",
                "cchm": "sable", "cchl": "sable point", "en": "solid"}


def known_breeders(user, program=None):
    """Every rabbit with genes on record, for route finding: herd rabbits
    (sold and culled need access; deceased are evidence only), outside
    relatives named in pedigrees, and the program's outside breeders."""
    out = []
    for r in Rabbit.all_objects.filter(owner=user).prefetch_related("genes"):
        genes = rabbit_genes(r)
        if all(set(p) == {UNKNOWN} for p in genes.values()):
            continue
        state = "evidence" if r.status == Rabbit.Status.DECEASED else ("access" if r.status in Rabbit.FORMER or r.archived_at else "ready")
        out.append({"key": f"h:{r.pk}", "name": r.name, "sex": r.sex, "genes": genes, "state": state, "rabbit": r, "node": ("h", r.pk)})
    seen = set()
    for rel in Relative.objects.filter(rabbit__owner=user, outside__isnull=False, relationship__in=["dam", "sire"]) \
            .select_related("outside").prefetch_related("genes"):
        texts = {g.locus: g.genotype for g in rel.genes.all() if g.locus != Gene.Locus.OTHER}
        if not texts or rel.outside_id in seen:
            continue
        seen.add(rel.outside_id)
        out.append({"key": f"o:{rel.outside_id}", "name": rel.outside.name, "sex": "doe" if rel.relationship == "dam" else "buck",
                    "genes": P.read_genes(texts), "state": "access", "rabbit": None, "node": ("o", rel.outside_id)})
    if program is not None:
        for b in program.outside.all():
            out.append({"key": f"x:{b.pk}", "name": b.name, "sex": b.sex, "genes": P.read_genes(b.genes), "state": "access", "rabbit": None, "node": ("x", b.pk)})
    return out


def route_view(route, target):
    """A route as words for the page."""
    if route is None:
        return None
    steps = []
    for a, b in route["steps"]:
        if a == "kit":
            steps.append("Breed a G1 kit to " + ("a G1 sibling" if b == "kit" else b["name"]))
        else:
            steps.append(f"{a['name']} × {b['name']}")
    return {"generations": route["generations"], "steps": steps, "odds": P.percent_text(route["odds"], 0),
            "state": route["state"], "state_text": STATE_WORDS[route["state"]],
            "rabbits": [{"name": r["name"], "state": r["state"], "state_text": STATE_WORDS[r["state"]]} for r in route["rabbits"]]}


def spec_view(target, spec):
    """An outside rabbit to look for, in plain words."""
    looks = phenotype_of(spec["genes"])
    carries = [f"carries {ALLELE_WORDS.get(allele, allele)} ({allele})" for _, allele in routes_mod.carries(spec["genes"])]
    return {"looks": looks, "carries": carries, "genes": pairs_text(spec["genes"], target), "generations": spec["generations"],
            "odds": P.percent_text(spec["odds"], 0)}


def phenotype_of(genes):
    full = tuple(genes.get(locus) or P.WILD[locus] for locus in P.PLAN_LOCI)
    return P.phenotype(full)


def coi_veto(program, ped):
    """ok() for routes: no pairing over the program's COI limit, the same rule
    the plan's own pairings follow."""
    limit = Fraction(program.max_coi) / 100

    def ok(d, s, mate=None):
        if mate is None:
            return ped.coi(s["node"], d["node"]) <= limit
        kit = ("route-kit", d["node"], s["node"])
        ped.parents[kit] = (s["node"], d["node"])
        if mate == "kit":
            sib = ("route-sib", d["node"], s["node"])
            ped.parents[sib] = (s["node"], d["node"])
            return ped.coi(kit, sib) <= limit
        return ped.coi(mate["node"], kit) <= limit if mate["sex"] == "buck" else ped.coi(kit, mate["node"]) <= limit
    return ok


def shortest_view(program, breeders=None, plan=None):
    """The program's minimum path (within its COI limit), how it compares with
    the plan's chosen starting pair, and outside-rabbit specs when the herd
    alone can't do better."""
    breeders = breeders if breeders is not None else known_breeders(program.owner, program)
    ready, overall = routes_mod.shortest(program.target, breeders, coi_veto(program, pedigree(program.owner)))
    view = {"ready": route_view(ready, program.target), "overall": route_view(overall, program.target), "shopping": []}
    if plan and plan.get("dam") and ready:
        mine = (plan["dam"]["key"], plan["sire"]["key"])
        first = ready["steps"][0]
        plan_gens = 1 if plan["g1"]["high"] else 2
        if (first[0]["key"], first[1]["key"]) != mine:
            plan_odds = routes_mod.one_gen(program.target, plan["dam"]["genes"], plan["sire"]["genes"]) if plan_gens == 1 else None
            switchable = all(r["state"] == "ready" or r["key"].startswith("x:") for r in first)
            view["differs"] = {"plan_pair": f"{plan['dam']['name']} × {plan['sire']['name']}", "plan_gens": plan_gens,
                               "faster": ready["generations"] < plan_gens,
                               "plan_odds": P.percent_text(plan_odds, 0) if plan_odds is not None else "",
                               "pairing": f"{first[0]['key']}|{first[1]['key']}" if switchable else "",
                               "charlies": P.percent_text(routes_mod.one_gen({"En": "EnEn"}, first[0]["genes"], first[1]["genes"]), 0)
                               if program.target.get("En") == "Enen" and routes_mod.one_gen({"En": "EnEn"}, first[0]["genes"], first[1]["genes"]) else ""}
        else:
            view["same"] = True
    if ready is None or ready["generations"] > 1:
        partners = [b for b in breeders if b["state"] == "ready"]
        specs = []
        for h in partners:
            spec = routes_mod.shopping(program.target, h)
            if spec and (ready is None or spec["generations"] < ready["generations"]):
                specs.append((spec["generations"], -spec["odds"], h["name"], h, spec))
        specs.sort(key=lambda t: t[:3])
        view["shopping"] = [{"partner": h["name"], "partner_sex": h["sex"], "want": "buck" if h["sex"] == "doe" else "doe",
                             **spec_view(program.target, spec)} for *_, h, spec in specs[:4]]
    return view


def goal_options(user):
    """Every preset target, sorted into the four tiers (routes.tier) and,
    within each, by fewest generations then best odds; each with a tier badge
    and one short line on how."""
    breeders = known_breeders(user)
    out = []
    for key, label, text, target in TARGETS:
        t = routes_mod.tier(target, breeders)
        gens = f"{t['generations']} generation{'s' if t['generations'] != 1 else ''}"
        if t["tier"] in (1, 2):
            first = t["route"]["steps"][0]
            how = f"{gens} · {first[0]['name']} × {first[1]['name']}"
        elif t["tier"] == 3:
            spec, partner = t["spec"], t["partner"]
            want = "buck" if partner["sex"] == "doe" else "doe"
            carries = [ALLELE_WORDS.get(a, a) for _, a in routes_mod.carries(spec["genes"])]
            how = f"Buy a {phenotype_of(spec['genes']).lower()} {want}" + (f" carrying {', '.join(carries)}" if carries else "") + f" for {partner['name']}"
        else:
            how = f"Buy a {label.lower()} pair"
        out.append({"key": key, "label": label, "text": text, "genes": target_text(target), "tier": t["tier"],
                    "badge": routes_mod.TIERS[t["tier"]], "how": how, "sort": routes_mod.tier_key(t),
                    "odds": P.percent_text(t["odds"], 0) if t["tier"] < 4 else ""})
    out.sort(key=lambda o: (o["sort"], o["label"]))
    return out
