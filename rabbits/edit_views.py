"""Editing a saved rabbit with the same cards and checks as adding one.

The edit page is an overview of the rabbit's answers, each with a Change
link to its card. Cards keep a draft in the session, one per rabbit, so
nothing is saved until Save changes, which checks every card again in one
transaction (rabbits/flow.py update_rabbit). Every page is a plain form
post, so it works without JavaScript. Only the owner can open any of it.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import flow
from .flow_views import row_anchor, step_context
from .models import Rabbit

# A card can only be shown once the cards it depends on pass.
NEEDS = {"breed": ["breed-type"], "color": ["breed-type", "breed"], "genes": ["breed-type", "breed"]}
LABELS = {
    "name": "Name", "sex": "Sex", "birth-date": "Birth date", "status": "Status",
    "breed-type": "Breed type", "breed": "Breed", "color": "Color", "line": "Line",
    "relatives": "Relatives", "genes": "Genes",
}


def owned(request, pk):
    return get_object_or_404(Rabbit, owner=request.user, pk=pk)


def card_url(pk, slug, check=False, anchor=""):
    url = reverse("rabbit_edit_step", args=[pk, slug])
    if check:
        url += "?check=1"
    if anchor:
        url += f"#{anchor}"
    return url


def load(request, rabbit):
    key = flow.edit_key(rabbit.pk)
    if not flow.has_draft(request.session, key):
        flow.save_draft(request.session, flow.draft_from_rabbit(rabbit), key)
    elif "gene_auto" not in request.session[key]:
        # A draft begun before the genes card: take the genes from the rabbit.
        fresh = flow.draft_from_rabbit(rabbit)
        stored = dict(request.session[key])
        stored.update({k: fresh[k] for k in flow.GENE_KEYS + ("eye_color", "gene_auto")})
        flow.save_draft(request.session, stored, key)
    return flow.load_draft(request.session, key), key


def overview_rows(draft, user, rabbit):
    from .flow_views import review_rows

    rows, relatives = review_rows(draft, user)
    values = dict(rows)
    breed_types = dict(Rabbit.BreedType.choices)
    answers = [
        ("name", values["Name"]), ("sex", values["Sex"]), ("birth-date", values["Birth date"]),
        ("relatives", None), ("status", values["Status"]), ("breed-type", breed_types.get(draft["breed_type"], "")),
        ("breed", values["Breed"]), ("color", values["Color"]), ("genes", values["Genes"]), ("line", draft["line"].strip()),
    ]
    out = []
    for slug, answer in answers:
        if slug == "relatives":
            out.append({"slug": slug, "label": LABELS[slug], "answer": "None added", "entries": relatives,
                        "url": card_url(rabbit.pk, slug)})
        else:
            out.append({"slug": slug, "label": LABELS[slug], "answer": answer, "url": card_url(rabbit.pk, slug)})
    return out


@login_required
def rabbit_edit(request, pk):
    rabbit = owned(request, pk)
    draft, key = load(request, rabbit)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "discard":
            flow.clear_draft(request.session, key)
            return redirect("rabbit_detail", pk=rabbit.pk)
        if action == "save":
            try:
                rabbit = flow.update_rabbit(draft, request.user, rabbit)
            except flow.DraftNotReady as not_ready:
                return redirect(card_url(rabbit.pk, not_ready.slug, check=True))
            flow.clear_draft(request.session, key)
            messages.success(request, f"{rabbit.name} was saved.")
            return redirect("rabbit_detail", pk=rabbit.pk)
        return redirect("rabbit_edit", pk=rabbit.pk)
    pending = draft != flow.load_draft({key: flow.draft_from_rabbit(rabbit)}, key)
    legacy = draft["legacy_breed"] if not draft["breed_type"] else ""
    return render(request, "rabbits/edit.html", {
        "rabbit": rabbit,
        "rows": overview_rows(draft, request.user, rabbit),
        "overview_url": reverse("rabbit_edit", args=[rabbit.pk]),
        "legacy_breed": legacy,
        "legacy_url": card_url(rabbit.pk, "breed-type"),
        "pending": pending,
        "wide": True,
    })


def blocked_card(draft, user):
    """The first card that no longer passes after a change (a new breed type
    can leave the breed or color card out of date), or None."""
    return flow.first_invalid_step(draft, user, steps=flow.EDIT_STEPS)


@login_required
def rabbit_edit_step(request, pk, step):
    if step not in flow.EDIT_SLUGS:
        raise Http404("No such card.")
    rabbit = owned(request, pk)
    draft, key = load(request, rabbit)
    for needed in NEEDS.get(step, []):
        if not flow.bound_form(needed, draft, request.user).is_valid():
            return redirect(card_url(rabbit.pk, needed, check=True))

    if request.method == "POST":
        flow.update_draft(draft, step, request.POST)
        action = request.POST.get("action", "next")
        if step == "genes":
            flow.fill_genes(draft, request.user)
            if action == "fill":
                flow.save_draft(request.session, draft, key)
                return redirect(card_url(rabbit.pk, step))
        if action == "save":
            flow.save_draft(request.session, draft, key)
            if request.headers.get("X-Autosave") == "1":
                return HttpResponse(status=204)
            return redirect(card_url(rabbit.pk, step))
        if flow.apply_row_action(draft, action):
            flow.save_draft(request.session, draft, key)
            return redirect(card_url(rabbit.pk, step, anchor=row_anchor(action, draft)))
        if action == "back":
            flow.save_draft(request.session, draft, key)
            return redirect("rabbit_edit", pk=rabbit.pk)
        if step == "breed-type" and flow.type_needs_round_trip(draft, request.POST):
            flow.save_draft(request.session, draft, key)
            return redirect(card_url(rabbit.pk, step, anchor="breed-section"))
        if step in ("breed", "breed-type"):
            flow.merge_mix(draft)
        form = flow.card_form(step, draft, request.user)
        if step == "relatives" and form.is_valid():
            if any(row["target"] == rabbit for row in form.cleaned_data["relatives"]):
                flow.save_draft(request.session, draft, key)
                messages.error(request, flow.SELF_RELATIVE)
                return redirect(card_url(rabbit.pk, step))
        if form.is_valid():
            if step == "relatives":
                filled = flow.prefill_breed_from_parents(draft, form.cleaned_data["relatives"])
                if filled:
                    messages.info(request, f"The breed was filled in from the parents: {filled}. You can change it on the breed cards.")
            # Done saves this card to the draft and goes back to the summary,
            # never on to another card. If the change left another card out
            # of date, the summary says which; Save also sends people there.
            flow.save_draft(request.session, draft, key)
            blocked = blocked_card(draft, request.user)
            if blocked:
                messages.error(
                    request,
                    f"Your change means the {LABELS.get(blocked, blocked)} card needs another look before you save.",
                )
            return redirect("rabbit_edit", pk=rabbit.pk)
        flow.save_draft(request.session, draft, key)
        return redirect(card_url(rabbit.pk, step, check=True))

    cleared = flow.reconcile_color(draft) if step == "color" else ""
    if step == "genes":
        flow.fill_genes(draft, request.user)
    flow.save_draft(request.session, draft, key)
    form = None
    if request.GET.get("check"):
        form = flow.card_form(step, draft, request.user)
        form.is_valid()
    context = step_context(step, draft, request.user, form, exclude=rabbit.pk)
    context.update({
        "editing": rabbit,
        "form_action": card_url(rabbit.pk, step),
        "overview_url": reverse("rabbit_edit", args=[rabbit.pk]),
        "has_back": True,
        "back_label": "Back to summary",
        "next_label": "Done",
        "hint": context["hint"] if step != "review" else "",
        "color_cleared": cleared,
        "wide": True,
    })
    return render(request, "rabbits/flow/step.html", context)


# One-card edits from the rabbit page: change one answer and save it at once,
# with every card's checks (flow.update_rabbit). Each detail row links here, so
# it works without JavaScript; rabbit-inline.mjs posts the simple ones in place.
QUICK_SLUGS = ("name", "sex", "birth-date", "status", "breed-type", "breed", "color", "genes", "line")
# Cards whose answers stand alone, and the rabbit fields each one sets.
SIMPLE = {"name": ("name", "tattoo"), "sex": ("sex",), "birth-date": ("birth_date",), "line": ("line",),
          "status": ("status", "death_date", "death_cause")}


def quick_key(pk):
    return flow.edit_key(pk) + "_quick"


def quick_url(pk, slug, keep=False, check=False, anchor=""):
    url = reverse("rabbit_quick_edit", args=[pk, slug])
    params = "&".join(p for p, on in (("keep=1", keep), ("check=1", check)) if on)
    return url + (f"?{params}" if params else "") + (f"#{anchor}" if anchor else "")


def quick_errors(form):
    return {name: [str(e) for e in errors] for name, errors in form.errors.items()}


@login_required
def rabbit_quick_edit(request, pk, step):
    if step not in QUICK_SLUGS:
        raise Http404("No such card.")
    rabbit = owned(request, pk)
    key = quick_key(pk)
    detail = reverse("rabbit_detail", args=[rabbit.pk]) + "#facts"
    keep = request.method == "POST" or request.GET.get("keep") or request.GET.get("check")
    if keep and flow.has_draft(request.session, key):
        draft = flow.load_draft(request.session, key)
    else:
        draft = flow.draft_from_rabbit(rabbit)
    inline = request.headers.get("X-Requested-With") == "fetch"

    if request.method == "POST":
        action = request.POST.get("action", "next")
        if action in ("back", "cancel"):
            flow.clear_draft(request.session, key)
            return redirect(detail)
        flow.update_draft(draft, step, request.POST)
        if action == "save":
            # The flow's autosave: keep the answer in the draft, save nothing yet.
            flow.save_draft(request.session, draft, key)
            if request.headers.get("X-Autosave") == "1":
                return HttpResponse(status=204)
            return redirect(quick_url(rabbit.pk, step, keep=True))
        if step == "genes":
            flow.fill_genes(draft, request.user)
            if action == "fill":
                flow.save_draft(request.session, draft, key)
                return redirect(quick_url(rabbit.pk, step, keep=True))
        if flow.apply_row_action(draft, action):
            flow.save_draft(request.session, draft, key)
            return redirect(quick_url(rabbit.pk, step, keep=True, anchor=row_anchor(action, draft)))
        if step == "breed-type" and flow.type_needs_round_trip(draft, request.POST):
            flow.save_draft(request.session, draft, key)
            return redirect(quick_url(rabbit.pk, step, keep=True, anchor="breed-section"))
        if step in ("breed", "breed-type"):
            flow.merge_mix(draft)
        form = flow.card_form(step, draft, request.user)
        if not form.is_valid():
            if inline:
                return JsonResponse({"errors": quick_errors(form)}, status=400)
            flow.save_draft(request.session, draft, key)
            return redirect(quick_url(rabbit.pk, step, check=True))
        if step in SIMPLE:
            # A self-contained answer: save just its fields, so an older rabbit
            # with other answers still missing can be corrected one row at a time.
            for field in SIMPLE[step]:
                setattr(rabbit, field, form.cleaned_data[field])
            rabbit.save(update_fields=list(SIMPLE[step]))
            flow.clear_draft(request.session, key)
            if inline:
                return JsonResponse({"saved": True})
            messages.success(request, f"{rabbit.name} was saved.")
            return redirect(detail)
        blocked = blocked_card(draft, request.user)
        if blocked:
            # The change leaves another card out of date (a new breed type, say):
            # carry on in the full edit, which explains what needs a look.
            flow.clear_draft(request.session, key)
            if inline:
                return JsonResponse({"errors": {"__all__": ["This change needs other answers updated. Use Edit."]}}, status=400)
            flow.save_draft(request.session, draft, flow.edit_key(rabbit.pk))
            messages.error(request, f"Your change means the {LABELS.get(blocked, blocked)} card needs another look before you save.")
            return redirect(card_url(rabbit.pk, blocked, check=True))
        try:
            rabbit = flow.update_rabbit(draft, request.user, rabbit)
        except flow.DraftNotReady as not_ready:
            flow.save_draft(request.session, draft, flow.edit_key(rabbit.pk))
            return redirect(card_url(rabbit.pk, not_ready.slug, check=True))
        flow.clear_draft(request.session, key)
        if inline:
            return JsonResponse({"saved": True})
        messages.success(request, f"{rabbit.name} was saved.")
        return redirect(detail)

    for needed in NEEDS.get(step, []):
        if not flow.bound_form(needed, draft, request.user).is_valid():
            flow.save_draft(request.session, draft, flow.edit_key(rabbit.pk))
            return redirect(card_url(rabbit.pk, needed, check=True))
    cleared = flow.reconcile_color(draft) if step == "color" else ""
    if step == "genes":
        flow.fill_genes(draft, request.user)
    flow.save_draft(request.session, draft, key)
    form = None
    if request.GET.get("check"):
        form = flow.card_form(step, draft, request.user)
        form.is_valid()
    context = step_context(step, draft, request.user, form, exclude=rabbit.pk)
    context.update({
        "editing": rabbit, "quick": True,
        "form_action": reverse("rabbit_quick_edit", args=[rabbit.pk, step]),
        "overview_url": detail,
        "has_back": True, "back_label": "Cancel", "next_label": "Save",
        "hint": context["hint"] if step != "review" else "",
        "color_cleared": cleared, "wide": True,
    })
    return render(request, "rabbits/flow/step.html", context)
