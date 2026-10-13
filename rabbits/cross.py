"""What-if cross: color odds for any two parents, picked from the herd or
from the typical breed genotypes, or typed in (doe_genes, buck_genes such
as "aa B_ Cc"). A GET form, so the URL carries the whole cross and can be
bookmarked or shared; it works without JavaScript."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import breed_genetics, color_odds, genetics
from .models import Rabbit

SIDES = ("doe", "buck")


def source_options(user):
    herd = Rabbit.objects.filter(owner=user, archived_at__isnull=True).exclude(
        status=Rabbit.Status.DECEASED).order_by("name")
    groups = [("Your herd", [(f"r{r.pk}", f"{r.name} · {r.get_sex_display()} · {r.short_breed}") for r in herd])]
    for category in breed_genetics.CATEGORIES:
        groups.append((f"Breed: {category}", [
            (f"b:{breed_genetics.slug(v.name)}", v.name) for v in breed_genetics.VARIETIES if v.category == category]))
    return [group for group in groups if group[1]]


def resolve(user, value):
    """(label, side for color_odds.predict_sides, pairs, kind) for a picked
    source, or None when it names nothing this user can see."""
    value = (value or "").strip()
    if value.startswith("r") and value[1:].isdigit():
        rabbit = Rabbit.objects.filter(owner=user, pk=int(value[1:])).prefetch_related("genes").first()
        if rabbit is None:
            return None
        return rabbit.name, color_odds.side(rabbit), color_odds.recorded(rabbit), "rabbit"
    if value.startswith("b:"):
        variety = breed_genetics.typical(value[2:])
        if variety is None:
            return None
        pairs = breed_genetics.filled(variety)
        genes = {locus: (color_odds.genotype_text(pair), False) for locus, pair in pairs.items()}
        return variety.name, (variety.name, genes), pairs, "breed"
    return None


def typed(source, text, fallback_label):
    """Apply typed genotype text on top of a picked source. Returns
    (picked or None, unread tokens)."""
    pairs, unread = breed_genetics.read(text)
    if not pairs:
        return None, unread
    label = fallback_label
    if source is not None:
        label = source[0] if breed_genetics.summary(pairs) == breed_genetics.summary(source[2]) else f"{source[0]} (edited)"
    side = (label, {locus: (color_odds.genotype_text(pair), False) for locus, pair in pairs.items()})
    return (label, side, pairs, "typed"), unread


@login_required
def cross_view(request):
    values = {side: request.GET.get(side, "") for side in SIDES}
    values.update({f"{side}_genes": " ".join(request.GET.get(f"{side}_genes", "").split())[:200] for side in SIDES})
    picked = {side: resolve(request.user, values[side]) for side in SIDES}
    errors = {side: ["Choose a rabbit or breed from the list."]
              for side in SIDES if values[side] and picked[side] is None}
    for side, label in (("doe", "First parent"), ("buck", "Second parent")):
        text = values[f"{side}_genes"]
        was = request.GET.get(f"{side}_was")
        if was is not None and was != values[side]:
            text = ""  # The pick changed since its genes were filled in; use the new pick.
        if picked[side] is not None and text == breed_genetics.summary(picked[side][2]):
            text = ""  # Unchanged from the pick: keep the pick (and its probable genes).
        if text:
            result, unread = typed(picked[side], text, label)
            if unread:
                errors[f"{side}_genes"] = [f"Can't read {', '.join(unread)}. Write each gene like aa, B_ or Cc, separated by spaces."]
            if result is not None:
                if picked[side] is not None and picked[side][3] == "breed" and result[0] == picked[side][0]:
                    result = (result[0], result[1], result[2], "breed")
                picked[side] = result
        elif picked[side] is not None:
            values[f"{side}_genes"] = breed_genetics.summary(picked[side][2])
    result = None
    if picked["doe"] and picked["buck"]:
        (doe_label, doe_side, doe_pairs, doe_kind), (buck_label, buck_side, buck_pairs, buck_kind) = picked["doe"], picked["buck"]
        if doe_label == buck_label:
            buck_label = f"{buck_label} (2)"
            buck_side = (buck_label, buck_side[1])
        result = {
            "doe_label": doe_label, "buck_label": buck_label,
            "odds": color_odds.predict_sides(doe_side, buck_side),
            "differing": color_odds.differing(doe_pairs, buck_pairs),
            "hidden_notes": genetics.pairing_notes(doe_label, doe_pairs, buck_label, buck_pairs),
            "breeds": [label for label, kind in ((doe_label, doe_kind), (buck_label, buck_kind)) if kind == "breed"],
        }
    return render(request, "rabbits/cross.html", {
        "values": values, "errors": errors, "result": result,
        "share_url": request.build_absolute_uri() if result else "", "groups": source_options(request.user), "wide": True,
    })
