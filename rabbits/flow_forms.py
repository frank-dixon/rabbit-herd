"""Step forms for the add-a-rabbit card flow, with the server-side rules.

Each card in the flow asks one question. The answers live in a draft (see
rabbits/flow.py) as the raw text people typed, and every check runs here,
on the server, from that draft. The browser's checks only help people
along; these decide.

Messages follow one voice: plain and friendly full sentences that state
the rule first and then say what to do. The wording matches the approved
Prototype C, so a change here is a copy change Frank should see.
"""

import datetime
from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import Breed, Gene, OutsideRabbit, Rabbit, Relative, parse_share, share_number, share_text

MAX_CROSS_ROWS = 8
MAX_RELATIVES = 12
GENE_LOCI = [value for value in Gene.Locus.values if value != Gene.Locus.OTHER]
TRAIT_TOO_LONG = "Please keep this to 80 characters or fewer."
GENE_TOO_LONG = "Please keep each genotype to 40 characters or fewer, for example c/c."
OTHER_GENES_TOO_LONG = "Please keep other genes to 200 characters or fewer."
RELATIVE_COLOR_NOT_LISTED = "Please choose one of the listed colors, or describe the color instead."


def trait_parts():
    """The optional color, line, and gene inputs on each relative row."""
    parts = ["color_choice", "color", "line", "breed"]
    for locus in GENE_LOCI:
        parts += [f"gene_{locus}", f"cert_{locus}"]
    return parts + ["gene_other", "cert_other"]


def parent_color_options(breed):
    """The breed's colors as (value, label) for a relative's color. A white
    the standard calls ruby-eyed is stored as "Ruby-eyed white", so the
    albino check can read it."""
    options = []
    for color in offered_colors(breed):
        hint = color.get("hint", "")
        if hint.casefold() == "ruby-eyed white":
            options.append(("Ruby-eyed white", f"{color['name']} (ruby-eyed white)"))
        else:
            options.append((color["name"], color["name"]))
    return options


def parent_color_values(breed):
    return [value for value, _ in parent_color_options(breed)]


def blank_traits():
    return {part: "" for part in trait_parts()}

NAME_REQUIRED = "Each rabbit needs a name or an ear tag. Please add one."
NAME_TOO_LONG = "A name or ear tag can be up to 120 characters. Please shorten it."
SEX_REQUIRED = "Each rabbit is recorded as a doe or a buck. Please choose one."
BIRTH_DATE_REQUIRED = "A birth date is required. Please pick one from the calendar."
BIRTH_DATE_FUTURE = "The birth date can't be in the future. Please pick today or an earlier date."
COLOR_REQUIRED = "A coat color helps tell rabbits apart, so it's required. Please describe the color."
COLOR_TOO_LONG = "A color can be up to 80 characters. Please shorten it."
COLOR_CHOICE_REQUIRED = (
    "Each rabbit needs a coat color. Please choose one of the {breed} colors, "
    "or choose Another color and describe it."
)
COLOR_NOT_LISTED = (
    "That color isn't one of the recognized {breed} colors. "
    "Please choose a color from the list, or choose Another color and describe it."
)
COLOR_CLEARED = (
    "{color} isn't a recognized color for the {breed}, so it has been cleared. "
    "Please check the color below before you go on."
)
COLOR_OTHER_REQUIRED = (
    "Another color needs a short description. Please describe the coat, for example broken black."
)
STATUS_REQUIRED = "Each rabbit needs a status. Please choose one."
BREED_TYPE_REQUIRED = "Each rabbit is either purebred or crossbred. Please choose one."
BREED_TYPE_FIRST = (
    "The breed choices depend on whether the rabbit is purebred or crossbred. "
    "Please choose that first."
)
PUREBRED_REQUIRED = "A purebred rabbit needs a breed from the list. Please choose one."
CROSS_BREED_REQUIRED = "Each row in the mix needs a breed. Please choose one, or clear the share."
TATTOO_TOO_LONG = "An ear tattoo can be up to 20 characters. Please shorten it."
TATTOO_TAKEN = "{name} already has the ear tattoo {tattoo}. Each tattoo can be used once in your herd."
CROSS_BREED_REPEATED = (
    "Each breed can be listed only once in a mix. "
    "Please choose a different breed, or combine the shares."
)
CROSS_PERCENT = "Each share is a number more than 0 and less than 100, with up to two decimals (like 12.5 or 6.25). Please adjust this share."
CROSS_TWO_BREEDS = "A crossbred rabbit has at least two breeds. Please add another breed to the mix."
CROSS_TOTAL = (
    "The shares need to add up to exactly 100%, and right now they add up to {total}%. "
    "Please adjust the shares."
)
RELATIONSHIP_REQUIRED = (
    "Each relative needs a relationship. Please choose how this rabbit is related."
)
ONE_PARENT = (
    "A rabbit can have only one {role}, and Relative {first} is already listed as the {role}. "
    "Choose a different relationship here."
)
RELATIVE_REQUIRED = (
    "Each relative needs a rabbit. Choose one from the list or add an outside rabbit."
)
ONE_RABBIT_PER_PLACE = (
    "Each place holds one rabbit. Choose one from the list or add an outside rabbit, but not both."
)
OUTSIDE_NAME_REQUIRED = "An outside rabbit needs a name. Add a name, or clear the details."
OUTSIDE_NAME_TOO_LONG = "An outside rabbit's name can be up to 120 characters. Please shorten it."
OUTSIDE_DETAILS_TOO_LONG = "Details can be up to 200 characters. Please shorten them."
RABBIT_GONE = "That rabbit is no longer in your list. Please choose again."
WRONG_SEX = "The {role} has to be a {sex}. {name} is a {actual}, so pick a {sex} here."

# Short hints shown under each tile, so a newcomer knows the terms.
SEX_CHOICES = [
    ("doe", "Doe", "Female"),
    ("buck", "Buck", "Male"),
]
STATUS_CHOICES = [
    ("breeding", "Breeding", "Kept for breeding."),
    ("growing", "Growing out", "A young rabbit you're raising before deciding whether to keep it."),
    ("sold", "Sold", "Sold to someone else."),
    ("culled", "Culled", "Removed from the herd."),
    ("deceased", "Deceased", "Died. You can add the date and cause."),
]
DEATH_CAUSES = ["Died kindling", "Illness", "Injury", "Culled", "Unknown"]
DEATH_DATE_INVALID = "Please pick the date of death from the calendar, or leave it blank."
DEATH_DATE_FUTURE = "The date of death can't be in the future."
DEATH_BEFORE_BIRTH = "The date of death can't be before the birth date."
DEATH_CAUSE_TOO_LONG = "Please keep the cause to 120 characters or fewer."
BREED_TYPE_CHOICES = [
    ("purebred", "Purebred", "All one breed. Parents of the same breed in different colors still make a purebred."),
    ("crossbred", "Crossbred", "A mix of two or more different breeds, each with a share in percent."),
]
PARENT_SEX = {"dam": Rabbit.Sex.DOE, "sire": Rabbit.Sex.BUCK}

# The color card's choice for a color that is not on the breed's list.
OTHER_COLOR = "__other__"
# Set when a breed change cleared the choice, so leftover text in the
# Another color box is not mistaken for a choice.
NO_COLOR = "__none__"
# Up to this many recognized colors show as tiles; more show as a select.
COLOR_TILE_LIMIT = 6


def today():
    return timezone.localdate()


def breed_groups():
    """Breed choices grouped the way the prototype shows them, with counts.
    Values are breed ids as text, so they round-trip through the draft."""
    arba, other = [], []
    for breed in Breed.objects.order_by("name"):
        (arba if breed.registry == Breed.Registry.ARBA else other).append((str(breed.pk), breed.name))
    groups = []
    if arba:
        groups.append((f"ARBA recognized ({len(arba)})", arba))
    if other:
        groups.append((f"Other recognized breeds ({len(other)})", other))
    return groups


def purebred_breed(data):
    """The draft's purebred Breed, or None for a crossbred or no breed yet."""
    if data.get("breed_type") != Rabbit.BreedType.PUREBRED:
        return None
    pk = str(data.get("purebred") or "")
    return Breed.objects.filter(pk=int(pk)).first() if pk.isdigit() else None


def offered_colors(breed):
    """The colors the color card offers as choices for a breed, in standard
    order. Empty means the card asks for free text: a crossbred, a breed
    whose standard recognizes colors by group, or a breed with no list."""
    if breed is None or breed.any_color:
        return []
    return list(breed.colors)


def matching_color(names, text):
    """The recognized color name that typed text spells, ignoring case."""
    folded = text.strip().casefold()
    return next((name for name in names if name.casefold() == folded), None)


def color_choice(names, choice, text):
    """The color card's current choice.

    A posted choice wins. With no choice yet, typed text from before the
    breed had a list counts as that color when it matches one, or as
    Another color when it doesn't. A breed with one recognized color has
    that color pre-chosen, also after a breed change cleared the choice."""
    if choice == NO_COLOR:
        return names[0] if len(names) == 1 else ""
    if choice:
        return choice
    if text.strip():
        return matching_color(names, text) or OTHER_COLOR
    if len(names) == 1:
        return names[0]
    return ""


def relationship_choices(rows, index):
    """Relationship choices for one relatives row.

    A rabbit has one dam and one sire, so once a row takes Dam or Sire the
    other rows stop offering it. The row's own current choice always stays,
    so a draft that somehow holds two dams still shows what it holds, and
    the save-time check flags it. The browser runs the same rule live.
    """
    taken_by = {}
    for row_index, row in enumerate(rows):
        relationship = row.get("relationship", "")
        if relationship in PARENT_SEX and relationship not in taken_by:
            taken_by[relationship] = row_index
    own = rows[index].get("relationship", "") if index < len(rows) else ""
    return [
        (value, label)
        for value, label in Relative.Relationship.choices
        if taken_by.get(value, index) == index or value == own
    ]


def rabbit_ref_groups(user, exclude=None):
    """Herd rabbits ("h:<id>") and saved outside rabbits ("o:<id>")."""
    herd = [
        (f"h:{rabbit.pk}", f"{rabbit.name} · {rabbit.get_sex_display()} · {rabbit.breed}")
        for rabbit in Rabbit.objects.filter(owner=user).order_by("name", "pk")
        if rabbit.pk != exclude
    ]
    outside = [
        (f"o:{entry.pk}", entry.name + (f" · {entry.details}" if entry.details else ""))
        for entry in OutsideRabbit.objects.filter(owner=user)
    ]
    groups = []
    if herd:
        groups.append(("In your herd", herd))
    if outside:
        groups.append(("Outside rabbits you've added before", outside))
    return groups


def resolve_ref(user, ref):
    """The herd rabbit or outside rabbit a ref names, or None. Only the
    user's own rabbits resolve, so a guessed id never reaches another herd."""
    kind, _, raw_id = (ref or "").partition(":")
    if not raw_id.isdigit():
        return None
    model = {"h": Rabbit, "o": OutsideRabbit}.get(kind)
    if model is None:
        return None
    return model.objects.filter(owner=user, pk=int(raw_id)).first()


class StepForm(forms.Form):
    """Base for one card. Fields are plain text, so every rule and message
    is ours. Error keys are field names, which are also the input names."""

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def text(self, name):
        return (self.data.get(name) or "").strip()


class NameForm(StepForm):
    name = forms.CharField(required=False)
    tattoo = forms.CharField(required=False)
    self_pk = forms.CharField(required=False)

    def clean(self):
        name = self.text("name")
        if not name:
            self.add_error("name", NAME_REQUIRED)
        elif len(name) > 120:
            self.add_error("name", NAME_TOO_LONG)
        tattoo = " ".join(self.text("tattoo").split())
        if len(tattoo) > 20:
            self.add_error("tattoo", TATTOO_TOO_LONG)
        elif tattoo and self.user is not None:
            others = Rabbit.objects.filter(owner=self.user, tattoo__iexact=tattoo)
            own = self.text("self_pk")
            if own.isdigit():
                others = others.exclude(pk=int(own))
            taken = others.first()
            if taken:
                self.add_error("tattoo", TATTOO_TAKEN.format(tattoo=tattoo, name=taken.name))
        return {"name": name, "tattoo": tattoo}


class SexForm(StepForm):
    sex = forms.CharField(required=False)

    def clean(self):
        sex = self.text("sex")
        if sex not in Rabbit.Sex.values:
            self.add_error("sex", SEX_REQUIRED)
        return {"sex": sex}


class BirthDateForm(StepForm):
    birth_date = forms.CharField(required=False)

    def clean(self):
        raw = self.text("birth_date")
        try:
            birth_date = datetime.date.fromisoformat(raw) if len(raw) == 10 else None
        except ValueError:
            birth_date = None
        if birth_date is None:
            self.add_error("birth_date", BIRTH_DATE_REQUIRED)
        elif birth_date > today():
            self.add_error("birth_date", BIRTH_DATE_FUTURE)
        return {"birth_date": birth_date}


LINE_TOO_LONG = "A line can be up to 80 characters. Please shorten it."


class LineForm(StepForm):
    """The rabbit's own line or strain, such as a breeder's herd name. Optional."""

    line = forms.CharField(required=False)

    def clean(self):
        line = self.text("line")
        if len(line) > 80:
            self.add_error("line", LINE_TOO_LONG)
        return {"line": line}


class ColorForm(StepForm):
    """A breed with a color list: choose one of its colors, or Another color
    with a description. Crossbreds and any-color breeds: describe it."""

    color_choice = forms.CharField(required=False)
    color = forms.CharField(required=False)

    def clean(self):
        text = self.text("color")
        breed = purebred_breed(self.data)
        names = [color["name"] for color in offered_colors(breed)]
        if not names:
            return self.free_text(text, COLOR_REQUIRED)
        choice = color_choice(names, self.text("color_choice"), text)
        if choice in names:
            return {"color": choice, "color_is_standard": True}
        if choice == OTHER_COLOR:
            cleaned = self.free_text(text, COLOR_OTHER_REQUIRED)
            # Typing a listed color under Another color still counts as that color.
            matched = matching_color(names, cleaned["color"])
            return {"color": matched or cleaned["color"], "color_is_standard": matched is not None}
        message = COLOR_NOT_LISTED if choice else COLOR_CHOICE_REQUIRED
        self.add_error("color_choice", message.format(breed=breed.name))
        return {"color": "", "color_is_standard": None}

    def free_text(self, text, required_message):
        """Free text is not checked against a list, so its standing is unknown."""
        if not text:
            self.add_error("color", required_message)
        elif len(text) > 80:
            self.add_error("color", COLOR_TOO_LONG)
        return {"color": text, "color_is_standard": None}


class StatusForm(StepForm):
    """Status, plus an optional date and cause of death for Deceased.
    Any other status clears the date and cause."""

    status = forms.CharField(required=False)
    death_date = forms.CharField(required=False)
    death_cause = forms.CharField(required=False)

    def clean(self):
        status = self.text("status")
        if status not in Rabbit.Status.values:
            self.add_error("status", STATUS_REQUIRED)
        if status != Rabbit.Status.DECEASED:
            return {"status": status, "death_date": None, "death_cause": ""}
        raw = self.text("death_date")
        death_date = None
        if raw:
            try:
                death_date = datetime.date.fromisoformat(raw)
            except ValueError:
                self.add_error("death_date", DEATH_DATE_INVALID)
        if death_date:
            try:
                born = datetime.date.fromisoformat(self.text("birth_date"))
            except ValueError:
                born = None
            if death_date > today():
                self.add_error("death_date", DEATH_DATE_FUTURE)
            elif born and death_date < born:
                self.add_error("death_date", DEATH_BEFORE_BIRTH)
        cause = self.text("death_cause")
        if len(cause) > 120:
            self.add_error("death_cause", DEATH_CAUSE_TOO_LONG)
        return {"status": status, "death_date": death_date, "death_cause": cause}


class BreedTypeForm(StepForm):
    breed_type = forms.CharField(required=False)

    def clean(self):
        breed_type = self.text("breed_type")
        if breed_type not in Rabbit.BreedType.values:
            self.add_error("breed_type", BREED_TYPE_REQUIRED)
        return {"breed_type": breed_type}


class BreedForm(StepForm):
    """Purebred: one breed from the catalog. Crossbred: two or more rows of
    breed and share, with the shares totalling exactly 100."""

    breed_type = forms.CharField(required=False)
    purebred = forms.CharField(required=False)

    def __init__(self, *args, rows=2, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = rows
        for index in range(rows):
            self.fields[f"cross-{index}-breed"] = forms.CharField(required=False)
            self.fields[f"cross-{index}-percent"] = forms.CharField(required=False)

    def clean(self):
        breed_type = self.text("breed_type")
        breeds = {str(pk): pk for pk in Breed.objects.values_list("pk", flat=True)}
        if breed_type == Rabbit.BreedType.PUREBRED:
            purebred = self.text("purebred")
            if purebred not in breeds:
                self.add_error("purebred", PUREBRED_REQUIRED)
                return {}
            return {"breed_type": breed_type, "purebred": breeds[purebred], "shares": []}
        if breed_type != Rabbit.BreedType.CROSSBRED:
            self.add_error(None, BREED_TYPE_FIRST)
            return {}
        seen = set()
        shares = []
        total = Decimal(0)
        for index in range(self.rows):
            breed = self.text(f"cross-{index}-breed")
            percent = self.text(f"cross-{index}-percent")
            if not breed and not percent:
                continue
            if breed not in breeds:
                self.add_error(f"cross-{index}-breed", CROSS_BREED_REQUIRED)
            elif breed in seen:
                self.add_error(f"cross-{index}-breed", CROSS_BREED_REPEATED)
            seen.add(breed)
            value = parse_share(percent)
            if value is None:
                self.add_error(f"cross-{index}-percent", CROSS_PERCENT)
            if share_number(percent) is not None:
                total += share_number(percent)
            if breed in breeds and value:
                shares.append((breeds[breed], value))
        if self.used_rows() < 2:
            self.add_error(None, CROSS_TWO_BREEDS)
        elif total != 100:
            self.add_error(None, CROSS_TOTAL.format(total=share_text(total)))
        return {"breed_type": breed_type, "purebred": None, "shares": shares}

    def used_rows(self):
        return sum(
            1
            for index in range(self.rows)
            if self.text(f"cross-{index}-breed") or self.text(f"cross-{index}-percent")
        )


class RelativesForm(StepForm):
    """Known relatives: each row is a relationship plus a herd rabbit, a
    saved outside rabbit, or a new outside rabbit by name and details."""

    def __init__(self, *args, rows=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = rows
        for index in range(rows):
            for part in ("relationship", "ref", "new_name", "new_details", *trait_parts()):
                self.fields[f"relatives-{index}-{part}"] = forms.CharField(required=False)

    def clean(self):
        parent_seen = {}
        relatives = []
        for index in range(self.rows):
            base = f"relatives-{index}"
            relationship = self.text(f"{base}-relationship")
            ref = self.text(f"{base}-ref")
            new_name = self.text(f"{base}-new_name")
            new_details = self.text(f"{base}-new_details")
            if relationship not in Relative.Relationship.values:
                self.add_error(f"{base}-relationship", RELATIONSHIP_REQUIRED)
                relationship = ""
            elif relationship in PARENT_SEX:
                if relationship in parent_seen:
                    self.add_error(
                        f"{base}-relationship",
                        ONE_PARENT.format(role=relationship, first=parent_seen[relationship]),
                    )
                else:
                    parent_seen[relationship] = index + 1
            if not ref and not new_name:
                self.add_error(f"{base}-ref", RELATIVE_REQUIRED)
                continue
            if ref and new_name:
                self.add_error(f"{base}-new_name", ONE_RABBIT_PER_PLACE)
                continue
            if new_details and not new_name:
                self.add_error(f"{base}-new_name", OUTSIDE_NAME_REQUIRED)
                continue
            if len(new_name) > 120:
                self.add_error(f"{base}-new_name", OUTSIDE_NAME_TOO_LONG)
                continue
            if len(new_details) > 200:
                self.add_error(f"{base}-new_details", OUTSIDE_DETAILS_TOO_LONG)
                continue
            target = None
            if ref:
                target = resolve_ref(self.user, ref)
                if target is None:
                    self.add_error(f"{base}-ref", RABBIT_GONE)
                    continue
                needed = PARENT_SEX.get(relationship)
                if needed and isinstance(target, Rabbit) and target.sex != needed:
                    self.add_error(
                        f"{base}-ref",
                        WRONG_SEX.format(
                            role=relationship, sex=needed, name=target.name, actual=target.sex
                        ),
                    )
                    continue
            relatives.append(
                {
                    "relationship": relationship,
                    "target": target,
                    "new_name": new_name,
                    "new_details": new_details,
                    **self.traits(base),
                }
            )
        return {"relatives": relatives}

    def traits(self, base):
        """The row's optional color, line, and genes. The color is the
        description when one is typed, else the color chosen from the
        breed's list. A genotype without a certainty counts as probable."""
        names = parent_color_values(purebred_breed(self.data))
        choice = self.text(f"{base}-color_choice")
        color = self.text(f"{base}-color")
        if not color and choice:
            if choice in names:
                color = choice
            else:
                self.add_error(f"{base}-color_choice", RELATIVE_COLOR_NOT_LISTED)
        for part in ("color", "line", "breed"):
            value = color if part == "color" else self.text(f"{base}-{part}")
            if len(value) > 80:
                self.add_error(f"{base}-{part}", TRAIT_TOO_LONG)
        genes = []
        for locus in GENE_LOCI + ["other"]:
            genotype = self.text(f"{base}-gene_{locus}")
            if not genotype:
                continue
            limit = 200 if locus == "other" else 40
            if len(genotype) > limit:
                self.add_error(
                    f"{base}-gene_{locus}", OTHER_GENES_TOO_LONG if locus == "other" else GENE_TOO_LONG
                )
                continue
            certainty = self.text(f"{base}-cert_{locus}")
            if certainty not in Gene.Certainty.values:
                certainty = Gene.Certainty.PROBABLE
            genes.append((locus, genotype, certainty))
        return {
            "color": color,
            "line": self.text(f"{base}-line"),
            "breed": self.text(f"{base}-breed"),
            "genes": genes,
        }


GENE_UNREADABLE = "Please choose a genotype from the list, or leave it as Not recorded."
EYE_COLOR_UNKNOWN = "Please choose an eye color from the list, or leave it blank."


class GenesForm(StepForm):
    """The rabbit's own genes, one dropdown per locus, plus eye color and
    free-text other genes. Every field is optional. A genotype recorded
    before the dropdowns, in a spelling the list can't read, is kept as
    written so editing never loses it."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["eye_color", "gene_other", "gene_auto"] + [f"gene_{locus}" for locus in GENE_LOCI]:
            self.fields[name] = forms.CharField(required=False)

    def clean(self):
        from . import gene_fill

        out = {"eye_color": self.text("eye_color")}
        if out["eye_color"] and out["eye_color"] not in dict(gene_fill.EYE_COLORS):
            self.add_error("eye_color", EYE_COLOR_UNKNOWN)
        genes = {}
        for locus in GENE_LOCI:
            raw = self.text(f"gene_{locus}")
            value = gene_fill.canonical(locus, raw)
            if value is None:
                if len(raw) > 40:
                    self.add_error(f"gene_{locus}", GENE_UNREADABLE)
                value = raw
            genes[locus] = value
        other = self.text("gene_other")
        if len(other) > 200:
            self.add_error("gene_other", OTHER_GENES_TOO_LONG)
        genes["other"] = other
        out["genes"] = genes
        return out
