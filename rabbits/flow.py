"""The add-a-rabbit card flow: its steps, its draft, and saving.

The flow asks one question per card, in this order: name, sex, birth date,
status, breed type, breed, color, relatives (optional), and a review. Color
comes after the breed, so the color card can know which breed it is for. It
has no pedigree step; the pedigree models stay unused for now.

The draft is kept in the signed-in session, so it survives a refresh, a
Back, or closing the tab, and it never needs JavaScript. It holds exactly
what people typed, as text. Nothing is checked when it is stored: the
step forms in rabbits/flow_forms.py check the draft when people move on,
and every step is checked again, in one transaction, right before saving.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from . import flow_forms, gene_fill
from .models import Breed, BreedShare, Gene, OutsideRabbit, Rabbit, Relative, color_text, parse_share, share_text

SESSION_KEY = "rabbit_draft"
MAX_TEXT = 500
# The draft's single-value answers, named like the inputs on the cards.
TEXT_KEYS = (
    "name", "sex", "birth_date", "color_choice", "color", "status", "breed_type", "purebred",
    "line", "legacy_breed", "death_date", "death_cause", "tattoo", "self_pk",
)
GENE_KEYS = tuple(f"gene_{locus}" for locus in gene_fill.LOCI) + ("gene_other",)
TEXT_KEYS += ("eye_color",) + GENE_KEYS + ("gene_auto",)
# The edit flow keeps one draft per rabbit, under this key plus the rabbit's id.
EDIT_SESSION_KEY = "rabbit_edit_draft_{pk}"


@dataclass(frozen=True)
class Step:
    slug: str
    form_class: type | None
    fields: tuple = ()
    optional: bool = False


STEPS = [
    Step("name", flow_forms.NameForm, ("name", "tattoo")),
    Step("sex", flow_forms.SexForm, ("sex",)),
    Step("birth-date", flow_forms.BirthDateForm, ("birth_date",)),
    # Parents and relatives come right after the basics, so the breed cards
    # can start from what the parents are.
    Step("relatives", flow_forms.RelativesForm, optional=True),
    Step("status", flow_forms.StatusForm, ("status", "death_date", "death_cause")),
    Step("breed-type", flow_forms.BreedTypeForm, ("breed_type",)),
    Step("breed", flow_forms.BreedForm, ("purebred",)),
    Step("color", flow_forms.ColorForm, ("color_choice", "color")),
    # Genes come right after the color, so they can be filled from it.
    Step("genes", flow_forms.GenesForm, ("eye_color",) + GENE_KEYS + ("gene_auto",), optional=True),
    Step("review", None),
]
SLUGS = [step.slug for step in STEPS]

# Editing uses the same cards and checks, plus the rabbit's own line, and
# an overview card instead of the review card.
EDIT_STEPS = STEPS[:9] + [
    Step("line", flow_forms.LineForm, ("line",), optional=True),
]
EDIT_SLUGS = [step.slug for step in EDIT_STEPS]
STEP_BY_SLUG = {step.slug: step for step in STEPS + EDIT_STEPS}


def step_index(slug):
    return SLUGS.index(slug)


def edit_key(pk):
    return EDIT_SESSION_KEY.format(pk=int(pk))


def blank_cross_row():
    return {"breed": "", "percent": ""}


def blank_relative():
    row = {"relationship": "", "ref": "", "new_name": "", "new_details": ""}
    row.update(flow_forms.blank_traits())
    return row


def empty_draft():
    return {
        "name": "",
        "sex": "",
        "birth_date": "",
        "color_choice": "",
        "color": "",
        "status": Rabbit.Status.GROWING.value,
        "breed_type": "",
        "purebred": "",
        "cross": [blank_cross_row(), blank_cross_row()],
        "relatives": [],
        "line": "",
        "legacy_breed": "",
        "death_date": "",
        "death_cause": "",
        "tattoo": "",
        "self_pk": "",
        "eye_color": "",
        **{key: "" for key in GENE_KEYS},
        "gene_auto": "",
        "step": SLUGS[0],
    }


def clean_text(value):
    return str(value or "")[:MAX_TEXT]


def clean_rows(rows, blank, limit, minimum=0):
    """Rows from the session, with only the known keys, as bounded text."""
    keys = blank().keys()
    cleaned = []
    if isinstance(rows, list):
        for row in rows[:limit]:
            if isinstance(row, dict):
                cleaned.append({key: clean_text(row.get(key)) for key in keys})
    while len(cleaned) < minimum:
        cleaned.append(blank())
    return cleaned


def load_draft(session, key=SESSION_KEY):
    """The session's draft, filled out to the full shape."""
    draft = empty_draft()
    stored = session.get(key)
    if isinstance(stored, dict):
        for key in TEXT_KEYS:
            if key in stored:
                draft[key] = clean_text(stored[key])
        draft["cross"] = clean_rows(
            stored.get("cross"), blank_cross_row, flow_forms.MAX_CROSS_ROWS, minimum=2
        )
        draft["relatives"] = clean_rows(
            stored.get("relatives"), blank_relative, flow_forms.MAX_RELATIVES
        )
        if stored.get("step") in STEP_BY_SLUG:
            draft["step"] = stored["step"]
    return draft


def has_draft(session, key):
    return isinstance(session.get(key), dict)


def save_draft(session, draft, key=SESSION_KEY):
    session[key] = draft
    session.modified = True


def clear_draft(session, key=SESSION_KEY):
    session.pop(key, None)


def form_data(draft):
    """The draft as flat form data, named like the inputs on the cards."""
    data = {key: draft[key] for key in TEXT_KEYS}
    for index, row in enumerate(draft["cross"]):
        data[f"cross-{index}-breed"] = row["breed"]
        data[f"cross-{index}-percent"] = row["percent"]
    for index, row in enumerate(draft["relatives"]):
        for part, value in row.items():
            data[f"relatives-{index}-{part}"] = value
    return data


def update_draft(draft, slug, post):
    """Copy one card's posted answers into the draft, unchecked. Only the
    fields on that card change, so a stale or crafted post cannot rewrite
    earlier answers."""
    step = STEP_BY_SLUG[slug]
    for field in step.fields:
        if field in post:
            draft[field] = clean_text(post.get(field))
    if slug == "breed":
        for index, row in enumerate(draft["cross"]):
            for part in ("breed", "percent"):
                key = f"cross-{index}-{part}"
                if key in post:
                    row[part] = clean_text(post.get(key))
    if slug == "relatives":
        for index, row in enumerate(draft["relatives"]):
            for part in row:
                key = f"relatives-{index}-{part}"
                if key in post:
                    row[part] = clean_text(post.get(key))


def apply_row_action(draft, action):
    """Add or remove a crossbred row or a relative. These are plain submit
    buttons, so they work without JavaScript. Returns True when handled."""
    kind, _, raw_index = action.rpartition("-")
    if action == "add-cross":
        if len(draft["cross"]) < flow_forms.MAX_CROSS_ROWS:
            draft["cross"].append(blank_cross_row())
        return True
    if action == "add-relative":
        if len(draft["relatives"]) < flow_forms.MAX_RELATIVES:
            draft["relatives"].append(blank_relative())
        return True
    if not raw_index.isdigit():
        return False
    index = int(raw_index)
    if kind == "remove-cross":
        if len(draft["cross"]) > 2 and index < len(draft["cross"]):
            del draft["cross"][index]
        return True
    if kind == "remove-relative":
        if index < len(draft["relatives"]):
            del draft["relatives"][index]
        return True
    return False


def merge_mix(draft):
    """Tidy a crossbred mix when people press Next.

    A mix that comes to one breed at 100% is a purebred of that breed, and
    is recorded as one. Otherwise, fold repeated breeds in a crossbred mix into one row by adding their
    shares, so "50% New Zealand" twice becomes "100% New Zealand" instead of
    an error. The first row for a breed keeps its place. Rows whose share is
    not a whole number are left alone, so the form can point at them."""
    if draft["breed_type"] != Rabbit.BreedType.CROSSBRED:
        return
    merged = []
    first = {}
    for row in draft["cross"]:
        breed, percent = row["breed"].strip(), row["percent"].strip()
        if breed and breed in first and parse_share(percent) is not None and parse_share(first[breed]["percent"]) is not None:
            target = first[breed]
            target["percent"] = share_text(parse_share(target["percent"]) + parse_share(percent))
            continue
        if breed and breed not in first:
            first[breed] = row
        merged.append(row)
    used = [row for row in merged if row["breed"].strip() or row["percent"].strip()]
    if len(used) == 1 and used[0]["percent"].strip() in ("100", "100.0", "100.00"):
        breed = used[0]["breed"].strip()
        if breed.isdigit() and Breed.objects.filter(pk=int(breed)).exists():
            # One breed at 100% is a purebred: record it that way, so the
            # color card offers that breed's colors.
            draft["breed_type"] = Rabbit.BreedType.PUREBRED.value
            draft["purebred"] = breed
            draft["cross"] = [blank_cross_row(), blank_cross_row()]
            return
    while len(merged) < 2:
        merged.append(blank_cross_row())
    draft["cross"] = merged


def bound_form(slug, draft, user):
    """The step's form, bound to the draft, ready to check."""
    step = STEP_BY_SLUG[slug]
    kwargs = {"data": form_data(draft), "user": user}
    if slug == "breed":
        kwargs["rows"] = len(draft["cross"])
    if slug == "relatives":
        kwargs["rows"] = len(draft["relatives"])
    return step.form_class(**kwargs)


def first_invalid_step(draft, user, before=None, steps=STEPS):
    """The first step whose answers do not pass, looking only at the steps
    before `before` (a slug) when it is given. None when all pass."""
    slugs = [step.slug for step in steps]
    stop = slugs.index(before) if before else len(steps)
    for step in steps[:stop]:
        if step.form_class and not bound_form(step.slug, draft, user).is_valid():
            return step.slug
    return None


def who(draft):
    return draft["name"].strip() or "this rabbit"


def breed_line(purebred, shares):
    """Readable breed text: the breed, or "Cross: 60% Rex, 40% Dutch"."""
    if purebred is not None:
        return purebred.name
    parts = sorted(shares, key=lambda share: (-share[1], share[0].name))
    return "Cross: " + ", ".join(f"{share_text(percent)}% {breed.name}" for breed, percent in parts)


def draft_breed_line(draft):
    """The breed line for the review card, from the draft as it stands."""
    names = dict((str(pk), name) for pk, name in Breed.objects.values_list("pk", "name"))
    if draft["breed_type"] == Rabbit.BreedType.PUREBRED:
        return names.get(draft["purebred"], "")
    if draft["breed_type"] == Rabbit.BreedType.CROSSBRED:
        rows = [
            (names[row["breed"]], parse_share(row["percent"]))
            for row in draft["cross"]
            if row["breed"] in names and parse_share(row["percent"]) is not None
        ]
        rows.sort(key=lambda row: (-row[1], row[0]))
        return "Cross: " + ", ".join(f"{share_text(percent)}% {name}" for name, percent in rows)
    return ""


def reconcile_color(draft):
    """Keep the color in step with the breed after a Back and a new breed.

    A listed color the new breed doesn't recognize is cleared, and the note
    to show is returned. Another color and its description always stay. When
    the new breed takes free text, a listed color moves into the text box.
    Returns "" when nothing needed clearing."""
    choice = draft["color_choice"]
    if choice in ("", flow_forms.OTHER_COLOR, flow_forms.NO_COLOR):
        return ""
    breed = flow_forms.purebred_breed(draft)
    names = [color["name"] for color in flow_forms.offered_colors(breed)]
    if not names:
        draft["color"] = choice
        draft["color_choice"] = ""
        return ""
    if choice in names:
        return ""
    draft["color_choice"] = flow_forms.NO_COLOR
    return flow_forms.COLOR_CLEARED.format(color=choice, breed=breed.name)


def draft_color(draft):
    """The color the review card shows: the chosen recognized color, or
    the description given for Another color or a free-text color, marked
    when it is not one of the breed's recognized colors."""
    form = flow_forms.ColorForm(data=form_data(draft))
    if not form.is_valid():
        return draft["color"].strip()
    return color_text(form.cleaned_data["color"], form.cleaned_data["color_is_standard"])


def short_breed(text):
    """Rabbit.breed holds up to 80 characters; a long mix is shortened."""
    return text if len(text) <= 80 else text[:79] + "…"


def save_relatives(rabbit, user, rows):
    """Save checked relatives rows, reusing a matching outside rabbit."""
    for row in rows:
        target = row["target"]
        if target is None:
            target = (
                OutsideRabbit.objects.filter(
                    owner=user,
                    name__iexact=row["new_name"],
                    details__iexact=row["new_details"],
                ).first()
                or OutsideRabbit.objects.create(
                    owner=user, name=row["new_name"], details=row["new_details"]
                )
            )
        relative = Relative.objects.create(
            rabbit=rabbit,
            relationship=row["relationship"],
            herd_rabbit=target if isinstance(target, Rabbit) else None,
            outside=target if isinstance(target, OutsideRabbit) else None,
            color=row["color"],
            line=row["line"],
            breed=row.get("breed", "") if not isinstance(target, Rabbit) else "",
        )
        Gene.objects.bulk_create(
            Gene(relative=relative, locus=locus, genotype=genotype, certainty=certainty)
            for locus, genotype, certainty in row["genes"]
        )


class DraftNotReady(Exception):
    def __init__(self, slug):
        super().__init__(slug)
        self.slug = slug


def save_rabbit(draft, user):
    """Check every step again and save the rabbit, its breed shares, and
    its relatives in one transaction. Raises DraftNotReady with the first
    step that fails."""
    fill_genes(draft, user)
    with transaction.atomic():
        answers = {}
        for step in STEPS:
            if step.form_class is None:
                continue
            form = bound_form(step.slug, draft, user)
            if not form.is_valid():
                raise DraftNotReady(step.slug)
            answers.update(form.cleaned_data)
        purebred = None
        if answers["purebred"]:
            purebred = Breed.objects.get(pk=answers["purebred"])
        shares = [(Breed.objects.get(pk=pk), percent) for pk, percent in answers["shares"]]
        rabbit = Rabbit.objects.create(
            owner=user,
            name=answers["name"],
            tattoo=answers["tattoo"],
            sex=answers["sex"],
            birth_date=answers["birth_date"],
            color=answers["color"],
            color_is_standard=answers["color_is_standard"],
            eye_color=answers["eye_color"],
            status=answers["status"],
            death_date=answers["death_date"],
            death_cause=answers["death_cause"],
            breed_type=answers["breed_type"],
            purebred=purebred,
            breed=short_breed(breed_line(purebred, shares)),
        )
        BreedShare.objects.bulk_create(
            BreedShare(rabbit=rabbit, breed=breed, percent=percent) for breed, percent in shares
        )
        save_relatives(rabbit, user, answers["relatives"])
        save_genes(rabbit, answers["genes"], auto_loci(draft))
    return rabbit


# Editing a saved rabbit ---------------------------------------------------


def fold(text):
    """Text for matching breed names: no accents, case, or extra spaces."""
    import unicodedata

    plain = unicodedata.normalize("NFKD", str(text or ""))
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return " ".join(plain.casefold().replace("’", "'").split())


def match_breed(text, breeds):
    """The Breed a legacy name spells, or None. A name cut short with "…"
    matches when exactly one breed starts with what is left."""
    folded = fold(text).rstrip(".… ")
    if not folded:
        return None
    for breed in breeds:
        if fold(breed.name) == folded:
            return breed
    if str(text).rstrip().endswith(("…", "...")) or len(folded) >= 4:
        starts = [breed for breed in breeds if fold(breed.name).startswith(folded)]
        if len(starts) == 1:
            return starts[0]
    return None


def parse_legacy_breed(text):
    """Read free-text breed from before the breed list: "New Zealand" or
    "Cross: 50% Creme d'Argent, 25% Flemish Giant, 25% New Zealand".
    Returns ("purebred", breed, []) or ("crossbred", None, [(breed, pct)])
    or None when it can't be read with confidence. Duplicate breeds are
    added together, and a mix that is one breed at 100% is a purebred."""
    import re

    breeds = list(Breed.objects.all())
    text = str(text or "").strip()
    if not text:
        return None
    body = re.sub(r"^\s*(cross(bred)?|mix)\s*:\s*", "", text, flags=re.IGNORECASE)
    parts = [part.strip() for part in re.split(r"[,/+;]| and ", body) if part.strip()]
    pattern = re.compile(r"^(\d{1,3}(?:\.\d{1,2})?)\s*%\s*(.+)$|^(.+?)\s*\(?(\d{1,3}(?:\.\d{1,2})?)\s*%\)?$")
    shares = {}
    order = []
    any_percent = False
    for part in parts:
        found = pattern.match(part)
        if found:
            any_percent = True
            percent = Decimal(found.group(1) or found.group(4))
            name = found.group(2) or found.group(3)
        else:
            percent, name = None, part
        breed = match_breed(name, breeds)
        if breed is None:
            return None
        if breed.pk not in shares:
            order.append(breed)
            shares[breed.pk] = 0
        shares[breed.pk] = None if percent is None or shares[breed.pk] is None else shares[breed.pk] + percent
    if len(order) == 1 and (not any_percent or shares[order[0].pk] == 100):
        return (Rabbit.BreedType.PUREBRED.value, order[0], [])
    if not any_percent or None in shares.values() or sum(shares.values()) != 100:
        return None
    return (Rabbit.BreedType.CROSSBRED.value, None, [(breed, shares[breed.pk]) for breed in order])


def relative_row(relative):
    """A saved Relative as a draft row for the relatives card."""
    row = blank_relative()
    row["relationship"] = relative.relationship
    if relative.herd_rabbit_id:
        row["ref"] = f"h:{relative.herd_rabbit_id}"
    elif relative.outside_id:
        row["ref"] = f"o:{relative.outside_id}"
    row["color"] = relative.color
    row["line"] = relative.line
    row["breed"] = relative.breed
    for gene in relative.genes.all():
        key = "other" if gene.locus == Gene.Locus.OTHER else gene.locus
        if f"gene_{key}" in row:
            row[f"gene_{key}"] = gene.genotype
            row[f"cert_{key}"] = gene.certainty
    return {key: clean_text(value) for key, value in row.items()}


def draft_from_rabbit(rabbit):
    """A draft filled in from a saved rabbit, ready for the edit cards.

    The breed comes from the saved breed fields when they are set. A rabbit
    from before the breed list only has free text, which is read with
    parse_legacy_breed; when that fails the breed is left for the keeper to
    pick, and the text is kept in legacy_breed so the cards can show it."""
    draft = empty_draft()
    draft.update(
        {
            "name": rabbit.name,
            "sex": rabbit.sex,
            "birth_date": rabbit.birth_date.isoformat() if rabbit.birth_date else "",
            "color": rabbit.color,
            "status": rabbit.status,
            "line": rabbit.line,
            "death_date": rabbit.death_date.isoformat() if rabbit.death_date else "",
            "death_cause": rabbit.death_cause,
            "tattoo": rabbit.tattoo,
            "self_pk": str(rabbit.pk),
            "eye_color": rabbit.eye_color,
            "step": EDIT_SLUGS[0],
        }
    )
    for gene in rabbit.genes.all():
        key = "gene_other" if gene.locus == Gene.Locus.OTHER else f"gene_{gene.locus}"
        if key in draft:
            value = gene.genotype if gene.locus == Gene.Locus.OTHER else gene_fill.canonical(gene.locus, gene.genotype)
            draft[key] = clean_text(gene.genotype if value is None else value)
    shares = [(share.breed, share.percent) for share in rabbit.breed_shares.select_related("breed")]
    if rabbit.breed_type == Rabbit.BreedType.PUREBRED and rabbit.purebred_id:
        parsed = (Rabbit.BreedType.PUREBRED.value, rabbit.purebred, [])
    elif rabbit.breed_type == Rabbit.BreedType.CROSSBRED and shares:
        parsed = (Rabbit.BreedType.CROSSBRED.value, None, shares)
    else:
        parsed = parse_legacy_breed(rabbit.breed)
    if parsed is None:
        draft["legacy_breed"] = clean_text(rabbit.breed)
    else:
        breed_type, purebred, parts = parsed
        draft["breed_type"] = breed_type
        if purebred is not None:
            draft["purebred"] = str(purebred.pk)
        if parts:
            draft["cross"] = [{"breed": str(breed.pk), "percent": share_text(pct)} for breed, pct in parts]
            while len(draft["cross"]) < 2:
                draft["cross"].append(blank_cross_row())
    relatives = rabbit.relatives.select_related("herd_rabbit", "outside").prefetch_related("genes")
    draft["relatives"] = [relative_row(relative) for relative in relatives][: flow_forms.MAX_RELATIVES]
    # Show a listed color as chosen, as the color card would.
    names = [color["name"] for color in flow_forms.offered_colors(flow_forms.purebred_breed(draft))]
    match = flow_forms.matching_color(names, rabbit.color) if names else None
    if match:
        draft["color_choice"], draft["color"] = match, ""
    for row in draft["relatives"]:
        values = flow_forms.parent_color_values(flow_forms.purebred_breed(draft))
        found = flow_forms.matching_color(values, row["color"]) if values else None
        if found:
            row["color_choice"], row["color"] = found, ""
    return draft


SELF_RELATIVE = "A rabbit can't be its own relative. Please choose a different rabbit."


def update_rabbit(draft, user, rabbit):
    """Check every edit card again and save the changes to the rabbit, its
    breed shares, and its relatives in one transaction. Raises DraftNotReady
    with the first card that fails."""
    fill_genes(draft, user)
    with transaction.atomic():
        rabbit = Rabbit.objects.select_for_update().get(pk=rabbit.pk, owner=user)
        answers = {}
        for step in EDIT_STEPS:
            form = bound_form(step.slug, draft, user)
            if not form.is_valid():
                raise DraftNotReady(step.slug)
            answers.update(form.cleaned_data)
        if any(row["target"] == rabbit for row in answers["relatives"]):
            raise DraftNotReady("relatives")
        purebred = Breed.objects.get(pk=answers["purebred"]) if answers["purebred"] else None
        shares = [(Breed.objects.get(pk=pk), percent) for pk, percent in answers["shares"]]
        for field in ("name", "tattoo", "sex", "birth_date", "color", "color_is_standard", "status", "death_date", "death_cause", "breed_type", "line", "eye_color"):
            setattr(rabbit, field, answers[field])
        rabbit.purebred = purebred
        rabbit.breed = short_breed(breed_line(purebred, shares))
        rabbit.save()
        rabbit.breed_shares.all().delete()
        BreedShare.objects.bulk_create(
            BreedShare(rabbit=rabbit, breed=breed, percent=percent) for breed, percent in shares
        )
        rabbit.relatives.all().delete()
        save_relatives(rabbit, user, answers["relatives"])
        save_genes(rabbit, answers["genes"], auto_loci(draft))
    return rabbit


def parent_mix(row):
    """A parent's breed as {breed pk: Decimal share}, or None if unknown."""
    target = row.get("target")
    if isinstance(target, Rabbit):
        if target.breed_type == Rabbit.BreedType.PUREBRED and target.purebred_id:
            return {target.purebred_id: Decimal(100)}
        shares = {share.breed_id: Decimal(share.percent) for share in target.breed_shares.all()}
        if shares:
            return shares
        text = target.breed
    else:
        text = row.get("breed", "")
    parsed = parse_legacy_breed(text)
    if parsed is None:
        return None
    kind, breed, parts = parsed
    if kind == Rabbit.BreedType.PUREBRED:
        return {breed.pk: Decimal(100)}
    return {part.pk: Decimal(pct) for part, pct in parts}


def prefill_breed_from_parents(draft, rows):
    """When the breed isn't answered yet and both the dam's and the sire's
    breeds are known, start the breed cards from them: the same breed on
    both sides is a purebred, otherwise each parent gives half its mix.
    Returns the breed line it filled in, or "" when it left things alone."""
    if draft["breed_type"]:
        return ""
    parents = {row["relationship"]: row for row in rows if row["relationship"] in ("dam", "sire")}
    if set(parents) != {"dam", "sire"}:
        return ""
    mixes = [parent_mix(parents["dam"]), parent_mix(parents["sire"])]
    if None in mixes:
        return ""
    combined = {}
    for mix in mixes:
        for pk, pct in mix.items():
            combined[pk] = combined.get(pk, Decimal(0)) + pct / 2
    if any(pct != pct.quantize(Decimal("0.01")) for pct in combined.values()):
        return ""
    if len(combined) == 1:
        draft["breed_type"] = Rabbit.BreedType.PUREBRED.value
        draft["purebred"] = str(next(iter(combined)))
    else:
        draft["breed_type"] = Rabbit.BreedType.CROSSBRED.value
        order = sorted(combined, key=lambda pk: -combined[pk])
        draft["cross"] = [{"breed": str(pk), "percent": share_text(combined[pk])} for pk in order]
    return draft_breed_line(draft)


# Genes filled from the breed and color ----------------------------------
#
# The genes card fills empty loci with what the breed, color and eye color
# prove (rabbits/gene_fill.py). The draft's gene_auto remembers each value
# it filled, as "A=aa;D=dd". A locus whose value still equals what was
# filled is still automatic, so a new color or eye color refreshes it. A
# locus people changed, or that held a value before, is theirs and is
# never touched. The script keeps gene_auto in step as it fills live.

AUTO_LOCI = gene_fill.LOCI + [gene_fill.OTHER]


def parse_auto(text):
    out = {}
    for part in str(text or "").split(";"):
        locus, sep, value = part.partition("=")
        if sep and locus in AUTO_LOCI:
            out[locus] = value
    return out


def auto_text(auto):
    return ";".join(f"{locus}={auto[locus]}" for locus in AUTO_LOCI if locus in auto)


def auto_loci(draft):
    return set(parse_auto(draft["gene_auto"]))


def gene_key(locus):
    return f"gene_{locus}"


def draft_color_text(draft):
    """The color as the rules read it: the color, plus its hint from the
    breed's list when the hint names the eyes (New Zealand "White" is
    listed as ruby-eyed white). Other hints describe shading and would
    only confuse the rules."""
    color = draft_color(draft)
    breed = flow_forms.purebred_breed(draft)
    for listed in flow_forms.offered_colors(breed):
        hint = listed.get("hint", "").casefold()
        if listed["name"] == draft["color_choice"] and ("eyed white" in hint or "ruby eyes" in hint):
            color = f"{color} {listed['hint']}"
    return color


def parent_genes(draft, user):
    """The dam's and sire's genes as recorded on the relatives card, or on
    the herd rabbit when the card leaves them blank."""
    out = []
    for row in draft["relatives"]:
        if row["relationship"] not in ("dam", "sire"):
            continue
        genes = {locus: row.get(gene_key(locus), "") for locus in gene_fill.LOCI if row.get(gene_key(locus))}
        target = flow_forms.resolve_ref(user, row["ref"]) if row["ref"].startswith("h:") else None
        if isinstance(target, Rabbit):
            for gene in target.genes.all():
                genes.setdefault(gene.locus, gene.genotype)
        out.append(genes)
    return out


def gene_suggestions(draft, user, eye=None):
    """{locus: genotype} the breed, color and eye color prove, narrowed by
    the parents. `eye` overrides the draft's eye color."""
    breed = flow_forms.purebred_breed(draft)
    found = gene_fill.from_breed_and_color(
        breed.name if breed else "", draft_color_text(draft), draft["eye_color"] if eye is None else eye
    )
    return gene_fill.narrow_with_parents(found, parent_genes(draft, user))


def fill_genes(draft, user, suggestions=None):
    """Fill empty or still-automatic loci from the suggestions. Returns the
    set of loci that hold a filled value afterwards."""
    if suggestions is None:
        suggestions = gene_suggestions(draft, user)
    before = parse_auto(draft["gene_auto"])
    auto = {}
    for locus in AUTO_LOCI:
        key = gene_key(locus)
        current = draft[key].strip()
        still_auto = locus in before and current == before[locus]
        if current and not still_auto:
            continue
        if suggestions.get(locus):
            draft[key] = suggestions[locus]
            auto[locus] = suggestions[locus]
        elif still_auto:
            draft[key] = ""
    draft["gene_auto"] = auto_text(auto)
    return set(auto)


def save_genes(rabbit, genes, auto):
    """Write the genes card to the rabbit. A blank clears that locus. A
    filled value proven by the color is saved as known; anything else
    keeps its certainty, or starts as probable."""
    for locus in gene_fill.LOCI + [Gene.Locus.OTHER]:
        value = genes.get(locus, "").strip()
        existing = rabbit.genes.filter(locus=locus).first()
        if not value:
            if existing:
                existing.delete()
            continue
        if existing and locus in auto:
            # A filled value never replaces a gene already on the rabbit,
            # such as one recorded on the genes page after this draft began.
            continue
        if existing:
            same = existing.genotype == value or (
                locus != Gene.Locus.OTHER and gene_fill.canonical(locus, existing.genotype) == value
            )
            if not same:
                existing.genotype = value
                if locus in auto:
                    existing.certainty = Gene.Certainty.KNOWN
                existing.save()
            continue
        certainty = Gene.Certainty.KNOWN if locus in auto and locus != Gene.Locus.OTHER else Gene.Certainty.PROBABLE
        Gene.objects.create(rabbit=rabbit, locus=locus, genotype=value, certainty=certainty)


def genes_line(draft):
    """The genes for the review card and the edit summary: "aa B_ C_ D_ E_
    enen · brown eyes", or "" when nothing is recorded."""
    parts = [draft[gene_key(locus)].strip() for locus in gene_fill.LOCI if draft[gene_key(locus)].strip()]
    eye = dict(gene_fill.EYE_COLORS).get(draft["eye_color"], "")
    text = " ".join(parts)
    if eye:
        text = f"{text} · {eye.split(' (')[0].lower()} eyes" if text else f"{eye.split(' (')[0]} eyes"
    return text
