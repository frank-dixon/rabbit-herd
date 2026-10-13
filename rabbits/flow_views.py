"""Pages for the add-a-rabbit card flow (see rabbits/flow.py).

Every card is a normal form post, so the flow works without JavaScript:
Next checks the card and moves on, Back keeps what was typed and goes
back, and the add and remove buttons for crossbred rows and relatives
are submit buttons too. Posts redirect afterwards, so a refresh never
posts twice. The script in assets/ only adds a live total, hides a taken
dam or sire as people choose, and saves typing as it happens.
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import flow, flow_forms
from .models import Rabbit, share_number, share_text

RADIO_FIELDS = {"sex", "status", "breed_type"}


def step_url(slug, check=False, anchor=""):
    url = reverse("rabbit_flow_step", args=[slug])
    if check:
        url += "?check=1"
    if anchor:
        url += f"#{anchor}"
    return url


def question(slug, draft):
    who = flow.who(draft)
    if slug == "name":
        return "What is this rabbit's name or ear tag?"
    if slug == "sex":
        return f"Is {who} a doe or a buck?"
    if slug == "birth-date":
        return f"When was {who} born?"
    if slug == "color":
        return f"What color is {who}?"
    if slug == "status":
        return f"What is {who}'s status in your herd?"
    if slug == "breed-type":
        return f"Is {who} purebred or crossbred?"
    if slug == "breed":
        if draft["breed_type"] == Rabbit.BreedType.CROSSBRED:
            return f"Which breeds make up {who}'s mix?"
        return f"Which breed is {who}?"
    if slug == "relatives":
        return f"Do you know any of {who}'s relatives?"
    if slug == "line":
        return f"Which line is {who} from?"
    if slug == "genes":
        return f"Which genes does {who} carry?"
    return f"Please check {who}'s details"


HINTS = {
    "name": "Use whatever you go by to tell this rabbit apart.",
    "review": "If something needs changing, use Back to return to it.",
    "genes": "Optional. Filled from the breed, color and eye color where they prove a gene. _ means the second allele isn't known yet.",
    "line": "Optional. The line or strain, such as a breeder's herd name, to tell same-breed lines apart.",
}


def next_label(slug, draft):
    if slug == "review":
        return f"Save {flow.who(draft)}"
    if slug == "relatives" and not draft["relatives"]:
        return "Skip this step"
    return "Next"


def anchor_for(key, draft):
    """The element an error summary link jumps to."""
    if key == "color_choice":
        colors = flow_forms.offered_colors(flow_forms.purebred_breed(draft))
        return "id_color_choice_0" if len(colors) <= flow_forms.COLOR_TILE_LIMIT else "id_color_choice"
    if key == "__all__":
        return "id_cross" if draft["breed_type"] == Rabbit.BreedType.CROSSBRED else "id_breed_type"
    if key in RADIO_FIELDS:
        return f"id_{key}_0"
    return f"id_{key}"


def total_text(total):
    total = Decimal(total)
    if total == 100:
        return "Total: 100%. The mix adds up."
    if total < 100:
        return f"Total so far: {share_text(total)}%. Add {share_text(100 - total)}% more to reach 100%."
    return f"Total so far: {share_text(total)}%. That's {share_text(total - 100)}% over, so lower a share."


def total_tone(total):
    if total == 100:
        return "good"
    return "over" if total > 100 else "short"


def cross_total(draft):
    total = Decimal(0)
    for row in draft["cross"]:
        value = share_number(row["percent"])
        if value is not None:
            total += value
    return total


def tiles(choices, value):
    return [
        {"value": choice, "label": label, "hint": hint, "checked": choice == value}
        for choice, label, hint in choices
    ]


def color_context(draft, errors):
    """What the color card shows: tiles, a select, or a text box."""
    breed = flow_forms.purebred_breed(draft)
    colors = flow_forms.offered_colors(breed)
    context = {"color_error": errors.get("color", []), "color_choice_error": errors.get("color_choice", [])}
    if not colors:
        if breed is not None:
            help_text = (
                f"The {breed.name} comes in many recognized colors, so please describe the coat, "
                "for example broken black or chestnut agouti."
            )
        else:
            help_text = "Describe the coat, for example broken black or chestnut agouti."
        context.update({"color_mode": "text", "color_help": help_text})
        return context
    names = [color["name"] for color in colors]
    choice = flow_forms.color_choice(names, draft["color_choice"], draft["color"])
    other_hint = "For a color that isn't listed. You'll describe it below."
    if len(colors) == 1:
        note = (
            f"This is the only recognized color for the {breed.name}. "
            "If yours looks different, choose Another color."
        )
    else:
        note = (
            f"These are the recognized colors for the {breed.name}. "
            "If yours isn't listed, choose Another color."
        )
    context.update(
        {
            "color_note": note,
            "color_breed": breed.name,
            "color_other": choice == flow_forms.OTHER_COLOR,
            "other_color": flow_forms.OTHER_COLOR,
        }
    )
    if len(colors) <= flow_forms.COLOR_TILE_LIMIT:
        color_tiles = [
            {"value": color["name"], "label": color["name"], "hint": color["hint"], "checked": choice == color["name"]}
            for color in colors
        ]
        color_tiles.append(
            {"value": flow_forms.OTHER_COLOR, "label": "Another color", "hint": other_hint,
             "checked": choice == flow_forms.OTHER_COLOR}
        )
        context.update({"color_mode": "tiles", "color_tiles": color_tiles, "color_single": len(colors) == 1})
    else:
        options = [
            (color["name"], f"{color['name']} ({color['hint']})" if color["hint"] else color["name"])
            for color in colors
        ]
        options.append((flow_forms.OTHER_COLOR, "Another color"))
        context.update({"color_mode": "select", "color_options": options, "color_choice": choice})
    return context


def status_text(draft, statuses):
    """The status for the review and edit summary, with the death details."""
    text = statuses.get(draft["status"], "")
    if draft["status"] == Rabbit.Status.DECEASED:
        details = [part for part in (draft["death_date"].strip(), draft["death_cause"].strip()) if part]
        if details:
            text += " · " + ", ".join(details)
    return text


def review_rows(draft, user):
    sexes = dict(Rabbit.Sex.choices)
    statuses = dict(Rabbit.Status.choices)
    rows = [
        ("Name", draft["name"].strip() + (f" · ear tattoo {draft['tattoo'].strip()}" if draft["tattoo"].strip() else "")),
        ("Sex", sexes.get(draft["sex"], "")),
        ("Birth date", draft["birth_date"]),
        ("Color", flow.draft_color(draft)),
        ("Status", status_text(draft, statuses)),
        ("Breed", flow.draft_breed_line(draft)),
        ("Genes", flow.genes_line(draft) or "Not recorded"),
    ]
    labels = dict(flow_forms.Relative.Relationship.choices)
    relatives = []
    for row in draft["relatives"]:
        target = flow_forms.resolve_ref(user, row["ref"]) if row["ref"] else None
        if row["new_name"].strip():
            details = row["new_details"].strip()
            name = row["new_name"].strip() + (f" ({details})" if details else "")
        elif isinstance(target, Rabbit):
            name = f"{target.name} (herd)"
        elif target is not None:
            name = target.name + (f" ({target.details})" if target.details else "")
        else:
            continue
        outside_breed = "" if isinstance(target, Rabbit) else row.get("breed", "").strip()
        traits = [part for part in (outside_breed, row["color"].strip() or row["color_choice"], row["line"].strip()) if part]
        if traits:
            name += " · " + ", ".join(traits)
        relatives.append(f"{labels.get(row['relationship'], 'Relative')}: {name}")
    return rows, relatives


def tattoo_suggestion(slug, data, user, form, exclude):
    """On a new rabbit's name step, fill the ear tattoo from the keeper's
    tattoo format in Settings when none is entered yet."""
    if slug != "name" or exclude is not None or form is not None or data.get("tattoo") or user is None:
        return {}
    from .tattoo import suggest

    value = suggest(user)
    if not value:
        return {}
    return {"tattoo_value": value, "tattoo_help": "Filled in from your tattoo format in Settings. Change or clear it if needed."}


def step_context(slug, draft, user, form, exclude=None):
    errors = {key: list(messages) for key, messages in (form.errors.items() if form else [])}
    data = flow.form_data(draft)
    index = flow.SLUGS.index(slug) if slug in flow.SLUGS else 0
    count = len(flow.STEPS)
    context = {
        "slug": slug,
        "number": index + 1,
        "count": count,
        "percent": round((index + 1) / count * 100),
        "question": question(slug, draft),
        "hint": HINTS.get(slug, ""),
        "next_label": next_label(slug, draft),
        "has_back": index > 0,
        "summary": [
            {"anchor": anchor_for(key, draft), "message": message}
            for key, messages in errors.items()
            for message in messages
        ],
        "errors": errors,
        "value": data.get(slug.replace("-", "_"), ""),
        "error": errors.get(slug.replace("-", "_"), []),
        "tattoo_value": data.get("tattoo", ""),
        "tattoo_error": errors.get("tattoo", []),
        **tattoo_suggestion(slug, data, user, form, exclude),
        "today": flow_forms.today().isoformat(),
        "draft": draft,
        "form_action": step_url(slug),
        "back_label": "Back",
    }
    if slug == "sex":
        context["tiles"] = tiles(flow_forms.SEX_CHOICES, draft["sex"])
    if slug == "status":
        context["tiles"] = tiles(flow_forms.STATUS_CHOICES, draft["status"])
        context.update({
            "death_causes": flow_forms.DEATH_CAUSES,
            "death_date_error": errors.get("death_date", []),
            "death_cause_error": errors.get("death_cause", []),
            "is_deceased": draft["status"] == Rabbit.Status.DECEASED,
        })
    if slug == "breed-type":
        context["tiles"] = tiles(flow_forms.BREED_TYPE_CHOICES, draft["breed_type"])
    if slug == "color":
        context.update(color_context(draft, errors))
    if slug == "breed":
        groups = flow_forms.breed_groups()
        total = cross_total(draft)
        context.update(
            {
                "crossbred": draft["breed_type"] == Rabbit.BreedType.CROSSBRED,
                "breed_groups": groups,
                "purebred_error": errors.get("purebred", []),
                "cross_error": errors.get("__all__", []),
                "cross_rows": [
                    {
                        "number": number + 1,
                        "breed_label": f"Breed {number + 1}",
                        "sr_name": f"breed {number + 1}",
                        "remove_action": f"remove-cross-{number}",
                        "breed_name": f"cross-{number}-breed",
                        "percent_name": f"cross-{number}-percent",
                        "breed": row["breed"],
                        "percent": row["percent"],
                        "breed_error": errors.get(f"cross-{number}-breed", []),
                        "percent_error": errors.get(f"cross-{number}-percent", []),
                    }
                    for number, row in enumerate(draft["cross"])
                ],
                "can_remove_cross": len(draft["cross"]) > 2,
                "can_add_cross": len(draft["cross"]) < flow_forms.MAX_CROSS_ROWS,
                "total": total,
                "total_text": total_text(total),
                "total_tone": total_tone(total),
            }
        )
    if slug == "relatives":
        ref_groups = flow_forms.rabbit_ref_groups(user, exclude=exclude)
        breed = flow_forms.purebred_breed(draft)
        parent_colors = flow_forms.parent_color_options(breed)
        context.update(
            {
                "ref_groups": ref_groups,
                "all_relationships": flow_forms.Relative.Relationship.choices,
                "relative_rows": [
                    {
                        "number": number + 1,
                        "sr_name": f"relative {number + 1}",
                        "remove_action": f"remove-relative-{number}",
                        "relationship_name": f"relatives-{number}-relationship",
                        "ref_name": f"relatives-{number}-ref",
                        "new_name_name": f"relatives-{number}-new_name",
                        "new_details_name": f"relatives-{number}-new_details",
                        "row": row,
                        "relationships": flow_forms.relationship_choices(draft["relatives"], number),
                        "relationship_error": errors.get(f"relatives-{number}-relationship", []),
                        "ref_error": errors.get(f"relatives-{number}-ref", []),
                        "new_name_error": errors.get(f"relatives-{number}-new_name", []),
                        "new_details_error": errors.get(f"relatives-{number}-new_details", []),
                        "open_new": bool(row["new_name"] or row["new_details"]),
                        **trait_context(number, row, errors, parent_colors, breed),
                    }
                    for number, row in enumerate(draft["relatives"])
                ],
                "can_add_relative": len(draft["relatives"]) < flow_forms.MAX_RELATIVES,
            }
        )
    if slug == "genes":
        context.update(genes_context(draft, user, errors))
    if slug == "review":
        context["review_rows"], context["review_relatives"] = review_rows(draft, user)
    return context


CERTAINTY_OPTIONS = [("known", "Known"), ("probable", "Probable")]
LOCUS_LABELS = dict(flow_forms.Gene.Locus.choices)


def trait_context(number, row, errors, parent_colors, breed):
    """The 'Color and line' part and the 'Genes they carry' part of one
    relative row, with each input's name, value, and errors."""
    base = f"relatives-{number}"
    genes = [
        {
            "label": LOCUS_LABELS[locus],
            "name": f"{base}-gene_{locus}",
            "cert_name": f"{base}-cert_{locus}",
            "value": row[f"gene_{locus}"],
            "cert": row[f"cert_{locus}"] or "probable",
            "error": errors.get(f"{base}-gene_{locus}", []),
        }
        for locus in flow_forms.GENE_LOCI + ["other"]
    ]
    return {
        "color_choice_name": f"{base}-color_choice",
        "color_name": f"{base}-color",
        "line_name": f"{base}-line",
        "breed_name": f"{base}-breed",
        "breed_error": errors.get(f"{base}-breed", []),
        "parent_colors": parent_colors,
        "color_help": (
            f"Choose one of the {breed.name}'s colors, or describe it."
            if parent_colors
            else "Describe the coat, for example ruby-eyed white or broken black."
        ),
        "color_choice_error": errors.get(f"{base}-color_choice", []),
        "color_error": errors.get(f"{base}-color", []),
        "line_error": errors.get(f"{base}-line", []),
        "genes": genes,
        "certainty_options": CERTAINTY_OPTIONS,
        "open_genes": any(gene["value"] or gene["error"] for gene in genes),
    }


PATTERNS = [
    ("solid", "Solid", "enen", "One colour all over, no white spotting."),
    ("broken", "Broken", "Enen", "Coloured patches on white, 10 to 50% colour."),
    ("charlie", "Charlie", "EnEn", "Mostly white, with a light nose and ear marking."),
]


def pattern_choices(value):
    """The Solid, Broken and Charlie picker for the En locus. A broken coat
    is En/en (Charlies are told apart by their markings), so each pattern
    names one genotype; a recorded "En_" stays on the Broken choice."""
    out = [{"key": "none", "label": "Not recorded", "value": "", "genotype": "", "help": "", "checked": not value}]
    for key, label, genotype, help_text in PATTERNS:
        if key == "broken" and value == "En_":
            genotype = value
        out.append({"key": key, "label": label, "value": genotype, "genotype": genotype,
                    "help": help_text, "checked": value == genotype})
    known = {choice["value"] for choice in out}
    if value and value not in known:
        out.append({"key": "recorded", "label": "As recorded", "value": value, "genotype": value, "help": "", "checked": True})
    return out


def genes_context(draft, user, errors):
    """The genes card: an eye color select, a dropdown per locus with the
    filled ones marked, and the suggestions for each eye color so the
    script can refill live without a round trip."""
    from . import gene_fill

    auto = flow.parse_auto(draft["gene_auto"])
    rows = []
    for locus in gene_fill.LOCI:
        value = draft[f"gene_{locus}"].strip()
        options = [(option, option) for option in gene_fill.options(locus)]
        if value and value not in gene_fill.options(locus):
            options.insert(0, (value, f"{value} (as recorded)"))
        rows.append({
            "locus": locus,
            "name": f"gene_{locus}",
            "label": f"{locus} · {gene_fill.LOCUS_NAMES[locus]}",
            "value": value,
            "options": options,
            "auto": locus in auto,
            "error": errors.get(f"gene_{locus}", []),
            "patterns": pattern_choices(value) if locus == "En" else None,
        })
    by_eye = {eye: flow.gene_suggestions(draft, user, eye=eye) for eye in [""] + [e for e, _ in gene_fill.EYE_COLORS]}
    breed = flow_forms.purebred_breed(draft)
    source = ", ".join(part for part in (breed.name if breed else "", flow.draft_color(draft)) if part)
    return {
        "gene_rows": rows,
        "eye_options": gene_fill.EYE_COLORS,
        "eye_color": draft["eye_color"],
        "eye_error": errors.get("eye_color", []),
        "gene_other": draft["gene_other"],
        "gene_other_auto": "other" in auto,
        "gene_other_error": errors.get("gene_other", []),
        "gene_auto": draft["gene_auto"],
        "gene_source": source,
        "gene_filled_any": bool(auto),
        "gene_suggestions_json": by_eye,
    }


def row_anchor(action, draft):
    """Where to land after adding or removing a row."""
    if action == "add-cross":
        return f"id_cross-{len(draft['cross']) - 1}-breed"
    if action == "add-relative":
        return f"id_relatives-{len(draft['relatives']) - 1}-relationship"
    return "id_cross" if "cross" in action else "add-relative"


@login_required
@require_GET
def rabbit_flow_resume(request):
    """The "Add a rabbit" entry point: open the card the draft was last on,
    or the first card when there is no draft."""
    draft = flow.load_draft(request.session)
    return redirect(step_url(draft["step"]))


@login_required
def rabbit_flow_step(request, step):
    if step not in flow.SLUGS:
        raise Http404("No such question.")
    draft = flow.load_draft(request.session)
    blocked = flow.first_invalid_step(draft, request.user, before=step)
    if blocked:
        # Earlier answers are missing or no longer pass. Go there first.
        return redirect(step_url(blocked, check=True))

    if request.method == "POST":
        flow.update_draft(draft, step, request.POST)
        action = request.POST.get("action", "next")
        index = flow.step_index(step)
        if step == "genes":
            flow.fill_genes(draft, request.user)
            if action == "fill":
                flow.save_draft(request.session, draft)
                return redirect(step_url(step))
        if action == "save":
            flow.save_draft(request.session, draft)
            if request.headers.get("X-Autosave") == "1":
                return HttpResponse(status=204)
            return redirect(step_url(step))
        if flow.apply_row_action(draft, action):
            flow.save_draft(request.session, draft)
            return redirect(step_url(step, anchor=row_anchor(action, draft)))
        if action == "back" and index > 0:
            draft["step"] = flow.SLUGS[index - 1]
            flow.save_draft(request.session, draft)
            return redirect(step_url(draft["step"]))
        if step == "review":
            try:
                rabbit = flow.save_rabbit(draft, request.user)
            except flow.DraftNotReady as not_ready:
                draft["step"] = not_ready.slug
                flow.save_draft(request.session, draft)
                return redirect(step_url(not_ready.slug, check=True))
            flow.clear_draft(request.session)
            return redirect("rabbit_flow_done", pk=rabbit.pk)
        if step == "breed":
            flow.merge_mix(draft)
        form = flow.bound_form(step, draft, request.user)
        if form.is_valid():
            if step == "relatives":
                filled = flow.prefill_breed_from_parents(draft, form.cleaned_data["relatives"])
                if filled:
                    messages.info(request, f"The breed was filled in from the parents: {filled}. You can change it on the breed cards.")
            draft["step"] = flow.SLUGS[index + 1]
            flow.save_draft(request.session, draft)
            return redirect(step_url(draft["step"]))
        # Show the problems on a plain page, so a refresh never posts again.
        draft["step"] = step
        flow.save_draft(request.session, draft)
        return redirect(step_url(step, check=True))

    draft["step"] = step
    cleared = flow.reconcile_color(draft) if step == "color" else ""
    if step == "genes":
        flow.fill_genes(draft, request.user)
    flow.save_draft(request.session, draft)
    form = None
    if request.GET.get("check") and flow.STEPS[flow.step_index(step)].form_class:
        form = flow.bound_form(step, draft, request.user)
        form.is_valid()
    context = step_context(step, draft, request.user, form)
    context["color_cleared"] = cleared
    context["wide"] = True
    return render(request, "rabbits/flow/step.html", context)


@login_required
@require_POST
def rabbit_flow_restart(request):
    flow.clear_draft(request.session)
    return redirect(step_url(flow.SLUGS[0]))


@login_required
def rabbit_flow_done(request, pk):
    rabbit = get_object_or_404(Rabbit, owner=request.user, pk=pk)
    return render(request, "rabbits/flow/done.html", {"rabbit": rabbit, "wide": True})
