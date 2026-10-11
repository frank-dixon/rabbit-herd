"""Pages for the add-a-rabbit card flow (see rabbits/flow.py).

Every card is a normal form post, so the flow works without JavaScript:
Next checks the card and moves on, Back keeps what was typed and goes
back, and the add and remove buttons for crossbred rows and relatives
are submit buttons too. Posts redirect afterwards, so a refresh never
posts twice. The script in assets/ only adds a live total, hides a taken
dam or sire as people choose, and saves typing as it happens.
"""

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import flow, flow_forms
from .models import Rabbit

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
    return f"Please check {who}'s details"


HINTS = {
    "name": "Use whatever you go by to tell this rabbit apart.",
    "review": "If something needs changing, use Back to return to it.",
}


def next_label(slug, draft):
    if slug == "review":
        return f"Save {flow.who(draft)}"
    if slug == "relatives" and not draft["relatives"]:
        return "Skip this step"
    return "Next"


def anchor_for(key, draft):
    """The element an error summary link jumps to."""
    if key == "__all__":
        return "id_cross" if draft["breed_type"] == Rabbit.BreedType.CROSSBRED else "id_breed_type"
    if key in RADIO_FIELDS:
        return f"id_{key}_0"
    return f"id_{key}"


def total_text(total):
    if total == 100:
        return "Total: 100%. The mix adds up."
    if total < 100:
        return f"Total so far: {total}%. Add {100 - total}% more to reach 100%."
    return f"Total so far: {total}%. That's {total - 100}% over, so lower a share."


def total_tone(total):
    if total == 100:
        return "good"
    return "over" if total > 100 else "short"


def cross_total(draft):
    total = 0
    for row in draft["cross"]:
        value = row["percent"].strip()
        if value.lstrip("-").isdigit():
            total += int(value)
    return total


def tiles(choices, value):
    return [
        {"value": choice, "label": label, "hint": hint, "checked": choice == value}
        for choice, label, hint in choices
    ]


def review_rows(draft, user):
    sexes = dict(Rabbit.Sex.choices)
    statuses = dict(Rabbit.Status.choices)
    rows = [
        ("Name", draft["name"].strip()),
        ("Sex", sexes.get(draft["sex"], "")),
        ("Birth date", draft["birth_date"]),
        ("Color", draft["color"].strip()),
        ("Status", statuses.get(draft["status"], "")),
        ("Breed", flow.draft_breed_line(draft)),
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
        relatives.append(f"{labels.get(row['relationship'], 'Relative')}: {name}")
    return rows, relatives


def step_context(slug, draft, user, form):
    errors = {key: list(messages) for key, messages in (form.errors.items() if form else [])}
    data = flow.form_data(draft)
    index = flow.step_index(slug)
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
        "today": flow_forms.today().isoformat(),
        "draft": draft,
    }
    if slug == "sex":
        context["tiles"] = tiles(flow_forms.SEX_CHOICES, draft["sex"])
    if slug == "status":
        context["tiles"] = tiles(flow_forms.STATUS_CHOICES, draft["status"])
    if slug == "breed-type":
        context["tiles"] = tiles(flow_forms.BREED_TYPE_CHOICES, draft["breed_type"])
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
        ref_groups = flow_forms.rabbit_ref_groups(user)
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
                    }
                    for number, row in enumerate(draft["relatives"])
                ],
                "can_add_relative": len(draft["relatives"]) < flow_forms.MAX_RELATIVES,
            }
        )
    if slug == "review":
        context["review_rows"], context["review_relatives"] = review_rows(draft, user)
    return context


def row_anchor(action, draft):
    """Where to land after adding or removing a row."""
    if action == "add-cross":
        return f"id_cross-{len(draft['cross']) - 1}-breed"
    if action == "add-relative":
        return f"id_relatives-{len(draft['relatives']) - 1}-relationship"
    return "id_cross" if "cross" in action else "add-relative"


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
        form = flow.bound_form(step, draft, request.user)
        if form.is_valid():
            draft["step"] = flow.SLUGS[index + 1]
            flow.save_draft(request.session, draft)
            return redirect(step_url(draft["step"]))
        # Show the problems on a plain page, so a refresh never posts again.
        draft["step"] = step
        flow.save_draft(request.session, draft)
        return redirect(step_url(step, check=True))

    draft["step"] = step
    flow.save_draft(request.session, draft)
    form = None
    if request.GET.get("check") and flow.STEPS[flow.step_index(step)].form_class:
        form = flow.bound_form(step, draft, request.user)
        form.is_valid()
    return render(request, "rabbits/flow/step.html", step_context(step, draft, request.user, form))


@login_required
@require_POST
def rabbit_flow_restart(request):
    flow.clear_draft(request.session)
    return redirect(step_url(flow.SLUGS[0]))


@login_required
def rabbit_flow_done(request, pk):
    rabbit = get_object_or_404(Rabbit, owner=request.user, pk=pk)
    return render(request, "rabbits/flow/done.html", {"rabbit": rabbit})
