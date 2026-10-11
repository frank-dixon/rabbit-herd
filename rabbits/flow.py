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

from django.db import transaction

from . import flow_forms
from .models import Breed, BreedShare, OutsideRabbit, Rabbit, Relative, color_text

SESSION_KEY = "rabbit_draft"
MAX_TEXT = 500
# The draft's single-value answers, named like the inputs on the cards.
TEXT_KEYS = ("name", "sex", "birth_date", "color_choice", "color", "status", "breed_type", "purebred")


@dataclass(frozen=True)
class Step:
    slug: str
    form_class: type | None
    fields: tuple = ()
    optional: bool = False


STEPS = [
    Step("name", flow_forms.NameForm, ("name",)),
    Step("sex", flow_forms.SexForm, ("sex",)),
    Step("birth-date", flow_forms.BirthDateForm, ("birth_date",)),
    Step("status", flow_forms.StatusForm, ("status",)),
    Step("breed-type", flow_forms.BreedTypeForm, ("breed_type",)),
    Step("breed", flow_forms.BreedForm, ("purebred",)),
    Step("color", flow_forms.ColorForm, ("color_choice", "color")),
    Step("relatives", flow_forms.RelativesForm, optional=True),
    Step("review", None),
]
SLUGS = [step.slug for step in STEPS]


def step_index(slug):
    return SLUGS.index(slug)


def blank_cross_row():
    return {"breed": "", "percent": ""}


def blank_relative():
    return {"relationship": "", "ref": "", "new_name": "", "new_details": ""}


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


def load_draft(session):
    """The session's draft, filled out to the full shape."""
    draft = empty_draft()
    stored = session.get(SESSION_KEY)
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
        if stored.get("step") in SLUGS:
            draft["step"] = stored["step"]
    return draft


def save_draft(session, draft):
    session[SESSION_KEY] = draft
    session.modified = True


def clear_draft(session):
    session.pop(SESSION_KEY, None)


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
    step = STEPS[step_index(slug)]
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


def bound_form(slug, draft, user):
    """The step's form, bound to the draft, ready to check."""
    step = STEPS[step_index(slug)]
    kwargs = {"data": form_data(draft), "user": user}
    if slug == "breed":
        kwargs["rows"] = len(draft["cross"])
    if slug == "relatives":
        kwargs["rows"] = len(draft["relatives"])
    return step.form_class(**kwargs)


def first_invalid_step(draft, user, before=None):
    """The first step whose answers do not pass, looking only at the steps
    before `before` (a slug) when it is given. None when all pass."""
    stop = step_index(before) if before else len(STEPS)
    for step in STEPS[:stop]:
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
    return "Cross: " + ", ".join(f"{percent}% {breed.name}" for breed, percent in parts)


def draft_breed_line(draft):
    """The breed line for the review card, from the draft as it stands."""
    names = dict((str(pk), name) for pk, name in Breed.objects.values_list("pk", "name"))
    if draft["breed_type"] == Rabbit.BreedType.PUREBRED:
        return names.get(draft["purebred"], "")
    if draft["breed_type"] == Rabbit.BreedType.CROSSBRED:
        rows = [
            (names[row["breed"]], int(row["percent"]))
            for row in draft["cross"]
            if row["breed"] in names and row["percent"].isdigit()
        ]
        rows.sort(key=lambda row: (-row[1], row[0]))
        return "Cross: " + ", ".join(f"{percent}% {name}" for name, percent in rows)
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


class DraftNotReady(Exception):
    def __init__(self, slug):
        super().__init__(slug)
        self.slug = slug


def save_rabbit(draft, user):
    """Check every step again and save the rabbit, its breed shares, and
    its relatives in one transaction. Raises DraftNotReady with the first
    step that fails."""
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
            sex=answers["sex"],
            birth_date=answers["birth_date"],
            color=answers["color"],
            color_is_standard=answers["color_is_standard"],
            status=answers["status"],
            breed_type=answers["breed_type"],
            purebred=purebred,
            breed=short_breed(breed_line(purebred, shares)),
        )
        BreedShare.objects.bulk_create(
            BreedShare(rabbit=rabbit, breed=breed, percent=percent) for breed, percent in shares
        )
        for row in answers["relatives"]:
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
            Relative.objects.create(
                rabbit=rabbit,
                relationship=row["relationship"],
                herd_rabbit=target if isinstance(target, Rabbit) else None,
                outside=target if isinstance(target, OutsideRabbit) else None,
            )
    return rabbit
