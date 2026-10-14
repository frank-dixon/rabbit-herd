"""Gene inference across a family: what each rabbit carries at every locus,
where each allele came from, and how sure we are.

Pure Python, no database. The caller hands in plain dicts (see infer) and
gets back, per rabbit and locus, two allele records labeled:

- known: the coat, a recorded known genotype, a parent that can only pass
  one allele, a kit that proves it, or the only allele left that fits.
- probable: more likely than not from what the parents can pass, with a %.
- guess: possible from the parents but no better than a coin toss.
- unknown: nothing to go on. Breed frequencies are never used, so a founder
  with no kits stays unknown where its coat proves nothing.

Slot 0 is the allele from the sire, slot 1 the allele from the dam.
"""

from .color_odds import SERIES, UNKNOWN, order, parse
from .gene_fill import LOCUS_NAMES, from_breed_and_color

LOCI = ["A", "B", "C", "D", "E", "En", "V", "Si"]
ROLE = ("sire", "dam")
KNOWN, PROBABLE, GUESS, UNKNOWN_LEVEL = "known", "probable", "guess", "unknown"
SURE = 0.995  # a probability this high, with no unknown share, is the only allele that fits
ALLELE_NAMES = {
    "A": "agouti", "at": "tan pattern", "a": "self",
    "B": "black", "b": "chocolate",
    "C": "full color", "cchd": "dark chinchilla", "cchm": "medium chinchilla", "cchl": "light chinchilla",
    "ch": "Himalayan", "c": "ruby-eyed white",
    "D": "dense", "d": "dilute",
    "ED": "dominant black", "Es": "steel", "E": "full extension", "ej": "harlequin", "e": "non-extension",
    "En": "broken", "en": "solid", "V": "non-Vienna", "v": "Vienna", "Si": "non-silvered", "si": "silvering",
}


# Alleles worth tracing: the hidden or notable ones a keeper breeds for or against.
NOTABLE = {"A": {"at"}, "B": {"b"}, "C": {"cchd", "cchm", "cchl", "ch", "c"}, "D": {"d"},
           "E": {"ED", "Es", "ej", "e"}, "En": {"En"}, "V": {"v"}, "Si": {"si"}}


def notable(locus, allele):
    return allele in NOTABLE.get(locus, ())


def rank(locus, allele):
    return SERIES[locus].index(allele)


def pair_text(locus, alleles):
    return " ".join(a if a else "?" for a in alleles)


class Locus:
    """What is known about one rabbit at one locus."""

    def __init__(self, locus):
        self.locus = locus
        self.entries = []  # {"a", "why", "slot" (0, 1 or None), "kind"}
        self.shown = None

    def placed(self, slot):
        return next((e for e in self.entries if e["slot"] == slot), None)

    def has(self, allele):
        return any(e["a"] == allele for e in self.entries)

    def full(self):
        return len(self.entries) == 2

    def add(self, allele, why, kind, slot=None, dup=False):
        """Record a known allele. Returns True when something changed."""
        if slot is not None:
            here = self.placed(slot)
            if here is not None:
                return False
            loose = next((e for e in self.entries if e["a"] == allele and e["slot"] is None), None)
            if loose is not None:
                loose["slot"] = slot
                if kind in ("parent", "fits"):
                    loose["why"], loose["kind"] = why, kind
                self.tidy()
                return True
            if self.full():
                return False
            self.entries.append({"a": allele, "why": why, "slot": slot, "kind": kind})
            self.tidy()
            return True
        if (self.has(allele) and not dup) or self.full():
            return False
        self.entries.append({"a": allele, "why": why, "slot": None, "kind": kind})
        self.tidy()
        return True

    def tidy(self):
        free = [e for e in self.entries if e["slot"] is None]
        if len(self.entries) == 2 and len(free) == 1:
            other = self.entries[0] if self.entries[1] is free[0] else self.entries[1]
            free[0]["slot"] = 1 - other["slot"]
        elif len(free) == 2 and free[0]["a"] == free[1]["a"]:
            free[0]["slot"], free[1]["slot"] = 0, 1
        # One slot holds something other than the coat's allele: the other slot is the coat's.
        if self.shown and not self.has(self.shown) and not self.full():
            for slot in (0, 1):
                e = self.placed(slot)
                if e and e["a"] != self.shown:
                    self.entries.append({"a": self.shown, "why": "Coat shows " + ALLELE_NAMES.get(self.shown, self.shown),
                                         "slot": 1 - slot, "kind": "coat"})
                    break


def _phenotype(node):
    """{locus: (allele, allele)} the breed, color and eye prove, unknown as _."""
    found = {}
    for locus, text in from_breed_and_color(node.get("breed", ""), node.get("color", ""), node.get("eye", "")).items():
        if locus in SERIES:
            pair = parse(locus, text)
            if pair:
                found[locus] = order(locus, pair)
    return found


def _new_state(nodes):
    state = {}
    for key, node in nodes.items():
        loci = {locus: Locus(locus) for locus in LOCI}
        coat = node.get("color") or ""
        for locus, pair in _phenotype(node).items():
            lo = loci[locus]
            if pair[0] != UNKNOWN:
                lo.shown = pair[0]
            for index, allele in enumerate(pair):
                if allele != UNKNOWN:
                    why = (f"Coat ({coat}) shows " + ALLELE_NAMES.get(allele, allele) if index == 0
                           else f"{coat} needs two {allele}" if allele == pair[0]
                           else f"{coat} needs {allele} with {pair[0]}")
                    lo.add(allele, why, "coat", dup=True)
        for locus, (text, certainty) in (node.get("genes") or {}).items():
            if locus not in SERIES:
                continue
            pair = parse(locus, text)
            if not pair:
                continue
            pair = order(locus, pair)
            lo = loci[locus]
            if certainty == "known":
                if pair[0] != UNKNOWN:
                    lo.shown = lo.shown or pair[0]
                for allele in pair:
                    if allele != UNKNOWN and sum(e["a"] == allele for e in lo.entries) < list(pair).count(allele):
                        lo.add(allele, f"Recorded as {pair_text(locus, pair)}", "record", dup=True)
            else:
                lo.recorded = pair  # a keeper's probable note, shown only if nothing better turns up
        state[key] = loci
    return state


def _propagate(nodes, state):
    changed = True
    rounds = 0
    while changed and rounds < 50:
        changed, rounds = False, rounds + 1
        for key, node in nodes.items():
            for slot, parent in enumerate((node.get("sire"), node.get("dam"))):
                if parent not in state:
                    continue
                pname = nodes[parent]["name"]
                for locus in LOCI:
                    kid, par = state[key][locus], state[parent][locus]
                    # A parent with two copies of one allele passes it.
                    if par.full() and par.entries[0]["a"] == par.entries[1]["a"]:
                        a = par.entries[0]["a"]
                        changed |= kid.add(a, f"{ROLE[slot].capitalize()} {pname} is {a} {a}, so passes {a}", "parent", slot)
                    # A kit's allele from this parent proves the parent carries it.
                    e = kid.placed(slot)
                    if e is not None and not par.has(e["a"]):
                        changed |= par.add(e["a"], f"Proven by kit {node['name']} ({ALLELE_NAMES.get(e['a'], e['a'])})", "kit")
                    # A loose allele this parent cannot have came from the other one.
                    if par.full():
                        for e in kid.entries:
                            if e["slot"] is None and not par.has(e["a"]) and kid.placed(1 - slot) is None:
                                e["slot"] = 1 - slot
                                kid.tidy()
                                changed = True
    return state


def _allowed(lo, allele):
    return lo.shown is None or rank(lo.locus, allele) >= rank(lo.locus, lo.shown)


def _normalize(dist):
    total = sum(dist.values())
    return {a: p / total for a, p in dist.items() if p > 0} if total > 0 else {UNKNOWN: 1.0}


class Odds:
    """Distributions for the alleles no evidence pins down."""

    def __init__(self, nodes, state):
        self.nodes, self.state, self.memo = nodes, state, {}

    def positions(self, key, locus):
        """Two positions, each ("known", entry) or ("dist", {allele: p}, parents considered)."""
        memo_key = (key, locus)
        if memo_key in self.memo:
            return self.memo[memo_key]
        self.memo[memo_key] = [("dist", {UNKNOWN: 1.0}), ("dist", {UNKNOWN: 1.0})]  # guards a loop
        lo = self.state[key][locus]
        node = self.nodes[key]
        parents = (node.get("sire"), node.get("dam"))
        out = [None, None]
        loose = [e for e in lo.entries if e["slot"] is None]
        for slot in (0, 1):
            e = lo.placed(slot)
            if e is not None:
                out[slot] = ("known", e)
        for slot in (0, 1):
            if out[slot] is None and loose:
                out[slot] = ("known", loose.pop(0))
        for slot in (0, 1):
            if out[slot] is not None:
                continue
            ambiguous = any(e["slot"] is None for e in lo.entries)
            sources = [0, 1] if ambiguous else [slot]
            dist = {}
            for source in sources:
                parent = parents[source]
                passed = self.passes(parent, locus) if parent in self.state else {UNKNOWN: 1.0}
                for a, p in passed.items():
                    dist[a] = dist.get(a, 0) + p / len(sources)
            other = out[1 - slot]
            need_shown = lo.shown and other is not None and other[0] == "known" and other[1]["a"] != lo.shown
            dist = {a: p for a, p in dist.items()
                    if a == UNKNOWN or (_allowed(lo, a) and (not need_shown or a == lo.shown))}
            out[slot] = ("dist", _normalize(dist), sources)
        self.memo[memo_key] = out
        return out

    def passes(self, key, locus):
        dist = {}
        for pos in self.positions(key, locus):
            options = {pos[1]["a"]: 1.0} if pos[0] == "known" else pos[1]
            for a, p in options.items():
                dist[a] = dist.get(a, 0) + p / 2
        return dist


def _describe(dist):
    shown = sorted(((p, a) for a, p in dist.items() if a != UNKNOWN), reverse=True)[:3]
    parts = [f"{a} {round(p * 100)}%" for p, a in shown]
    if dist.get(UNKNOWN):
        parts.append(f"unrecorded {round(dist[UNKNOWN] * 100)}%")
    return ", ".join(parts)


def _record(node, nodes, slot, kind, value, sources=None):
    parents = (node.get("sire"), node.get("dam"))
    if kind == "known":
        e = value
        origin = e["slot"]
        rec = {"allele": e["a"], "level": KNOWN, "pct": 100, "why": e["why"], "kind": e["kind"]}
    else:
        dist = value
        candidates = sorted(((p, a) for a, p in dist.items() if a != UNKNOWN), reverse=True)
        origin = slot if sources == [slot] else None
        who = " or ".join(f"{ROLE[s]} {nodes[parents[s]]['name']}" if parents[s] in nodes else f"an unrecorded {ROLE[s]}"
                          for s in (sources or [slot]))
        if not candidates:
            rec = {"allele": None, "level": UNKNOWN_LEVEL, "pct": None, "kind": "none",
                   "why": f"Nothing recorded on {who} and no kits prove it"}
        else:
            p, a = candidates[0]
            tie = len(candidates) > 1 and abs(candidates[1][0] - p) < 1e-9
            level = PROBABLE if p > 0.5 and not tie else GUESS
            rec = {"allele": a, "level": level, "pct": round(p * 100), "kind": "odds",
                   "why": f"From {who}: {_describe(dist)}"}
    rec["origin"] = ROLE[origin] if origin is not None else None
    rec["origin_key"] = parents[origin] if origin is not None and parents[origin] in nodes else None
    return rec


def infer(nodes):
    """nodes: {key: {"name", "sire", "dam", "breed", "color", "eye",
    "genes": {locus: (genotype text, "known"/"probable")}}}. sire and dam
    are other keys or None. Returns {key: {locus: {"shown", "pair": [rec,
    rec], "recorded"}}} where each rec has allele, level, pct, why, kind,
    origin ("sire"/"dam"/None) and origin_key."""
    state = _propagate(nodes, _new_state(nodes))
    for _ in range(4):  # promote "only fits" alleles, then let them prove more
        odds = Odds(nodes, state)
        promoted = False
        for key, node in nodes.items():
            for locus in LOCI:
                lo = state[key][locus]
                for slot, pos in enumerate(odds.positions(key, locus)):
                    if pos[0] != "dist":
                        continue
                    dist, sources = pos[1], pos[2]
                    best = max(((p, a) for a, p in dist.items() if a != UNKNOWN), default=None)
                    if best and best[0] >= SURE and UNKNOWN not in dist and sources == [slot] and lo.shown:
                        parent = (node.get("sire"), node.get("dam"))[slot]
                        why = (f"Only allele that fits: {ROLE[slot]} {nodes[parent]['name']} passes "
                               f"{pair_text(locus, [e['a'] for e in state[parent][locus].entries])}, "
                               f"and the coat rules out the rest")
                        promoted |= lo.add(best[1], why, "fits", slot)
        if not promoted:
            break
        state = _propagate(nodes, state)
    odds = Odds(nodes, state)
    result = {}
    for key, node in nodes.items():
        result[key] = {}
        for locus in LOCI:
            lo = state[key][locus]
            pair = [_record(node, nodes, slot, *pos) if pos[0] == "known"
                    else _record(node, nodes, slot, "dist", pos[1], pos[2])
                    for slot, pos in enumerate(odds.positions(key, locus))]
            result[key][locus] = {"shown": lo.shown, "pair": pair, "name": LOCUS_NAMES.get(locus, locus),
                                  "recorded": "".join(getattr(lo, "recorded", ()) or ())}
    return result


def status(result, locus, allele):
    """How one rabbit holds an allele: ("expressed"|"carrier"|None, level, pct)."""
    info = result[locus]
    hits = [r for r in info["pair"] if r["allele"] == allele and r["level"] in (KNOWN, PROBABLE)]
    if not hits:
        return None, None, None
    level = KNOWN if any(r["level"] == KNOWN for r in hits) else PROBABLE
    pct = max(r["pct"] or 0 for r in hits)
    expressed = info["shown"] == allele or (len(hits) == 2 and all(r["level"] == KNOWN for r in hits))
    return ("expressed" if expressed else "carrier"), level, pct


def thread(nodes, results, locus, allele):
    """The path one allele takes through the family: {"nodes": {key: (status,
    level, pct)}, "edges": [(parent, kit, level)], "sources": [key]}."""
    held = {}
    for key in nodes:
        s, level, pct = status(results[key], locus, allele)
        if s:
            held[key] = (s, level, pct)
    edges = []
    for key, node in nodes.items():
        if key not in held:
            continue
        for slot, parent in enumerate((node.get("sire"), node.get("dam"))):
            if parent not in held:
                continue
            rec = results[key][locus]["pair"][slot]
            hit = [r for r in results[key][locus]["pair"] if r["allele"] == allele and r["origin"] == ROLE[slot]]
            if hit:
                level = KNOWN if hit[0]["level"] == KNOWN and held[parent][1] == KNOWN else PROBABLE
                edges.append((parent, key, level))
            elif rec["origin"] is None and rec["allele"] == allele:
                edges.append((parent, key, PROBABLE))
    fed = {kit for _, kit, _ in edges}
    sources = [key for key in held if key not in fed]
    return {"nodes": held, "edges": edges, "sources": sources}


def changes(nodes, results, key):
    """'What changed at this generation': new looks, carriers proven by kits,
    and hidden alleles inherited. Each item: {kind, text, level, pct, why}."""
    node, mine = nodes[key], results[key]
    parents = [p for p in (node.get("sire"), node.get("dam")) if p in results]
    out = []
    for locus in LOCI:
        info = mine[locus]
        shown = info["shown"]
        if shown and parents and len(parents) == 2 and all(results[p][locus]["shown"] and results[p][locus]["shown"] != shown for p in parents):
            out.append({"kind": "new", "level": KNOWN, "pct": 100,
                        "text": f"New look: {ALLELE_NAMES.get(shown, shown)} appeared",
                        "why": "Neither parent shows it, so both passed a hidden " + shown})
        for rec in info["pair"]:
            if rec["kind"] == "kit":
                out.append({"kind": "proven", "level": KNOWN, "pct": 100,
                            "text": f"Carrier of {ALLELE_NAMES.get(rec['allele'], rec['allele'])} ({rec['allele']}) proven",
                            "why": rec["why"]})
        for rec in info["pair"]:
            a = rec["allele"]
            if a and rec["origin"] and a != shown and notable(locus, a) and rec["level"] in (KNOWN, PROBABLE) and rec["kind"] != "kit":
                who = nodes.get(rec["origin_key"], {}).get("name", "")
                out.append({"kind": "inherited", "level": rec["level"], "pct": rec["pct"],
                            "text": f"Inherited {ALLELE_NAMES.get(a, a)} ({a}) from {rec['origin']} {who}".strip(),
                            "why": rec["why"]})
    return out
