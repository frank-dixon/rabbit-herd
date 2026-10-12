"""Turn an outside relative into a herd rabbit ("Add to my herd").

The new rabbit takes the outside rabbit's name and the relative's sex
(from dam or sire), breed, color, line and genes. Every link to that
outside rabbit, on any of the keeper's rabbits and pedigrees, moves to the
new herd rabbit, and the outside entry is removed, so nothing is listed
twice. Then the edit cards open so the keeper can set the status.
"""

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import flow, flow_forms
from .models import Gene, PedigreeEntry, Rabbit, Relative

BIRTH_DATE_REQUIRED = "Please add a birth date, or your best guess. You can change it later."


def owned_outside_relative(user, pk):
    return get_object_or_404(
        Relative.objects.select_related("rabbit", "outside"), pk=pk, rabbit__owner=user, outside__isnull=False
    )


def adopt(user, relative, sex, birth_date):
    outside = relative.outside
    breed_text = relative.breed.strip()
    parsed = flow.parse_legacy_breed(breed_text) if breed_text else None
    fields = {"breed": breed_text or "Unknown"}
    if parsed and parsed[0] == Rabbit.BreedType.PUREBRED:
        fields.update(breed_type=Rabbit.BreedType.PUREBRED, purebred=parsed[1], breed=parsed[1].name)
    with transaction.atomic():
        rabbit = Rabbit.objects.create(
            owner=user, name=outside.name, sex=sex, birth_date=birth_date,
            color=relative.color or "Unknown", line=relative.line, **fields,
        )
        links = list(Relative.objects.filter(outside=outside, rabbit__owner=user).prefetch_related("genes"))
        seen = set()
        for link in [relative] + [link for link in links if link.pk != relative.pk]:
            for gene in Gene.objects.filter(relative_id=link.pk):
                if gene.locus in seen:
                    gene.delete()
                    continue
                seen.add(gene.locus)
                gene.relative = None
                gene.rabbit = rabbit
                gene.save(update_fields=["relative", "rabbit"])
        Relative.objects.filter(pk__in=[link.pk for link in links]).update(outside=None, herd_rabbit=rabbit, breed="")
        PedigreeEntry.objects.filter(outside=outside, rabbit__owner=user).update(outside=None, herd_rabbit=rabbit)
        if not Relative.objects.filter(outside=outside).exists() and not PedigreeEntry.objects.filter(outside=outside).exists():
            outside.delete()
    return rabbit


@login_required
def relative_add_to_herd(request, pk):
    """GET: a short confirm form (sex and birth date are required for a
    herd rabbit). POST: create the rabbit, relink, and open its edit cards."""
    relative = owned_outside_relative(request.user, pk)
    sex = flow_forms.PARENT_SEX.get(relative.relationship, "")
    birth_date = ""
    errors = {}
    if request.method == "POST":
        sex = request.POST.get("sex", "")
        birth_date = request.POST.get("birth_date", "").strip()
        if sex not in Rabbit.Sex.values:
            errors["sex"] = flow_forms.SEX_REQUIRED
        try:
            born = datetime.date.fromisoformat(birth_date)
            if born > flow_forms.today():
                errors["birth_date"] = flow_forms.BIRTH_DATE_FUTURE
        except ValueError:
            errors["birth_date"] = BIRTH_DATE_REQUIRED
        if not errors:
            rabbit = adopt(request.user, relative, sex, born)
            messages.success(request, f"{rabbit.name} is now in your herd. Set the status and anything else here.")
            return redirect(reverse("rabbit_edit_step", args=[rabbit.pk, "status"]))
    return render(
        request,
        "rabbits/add_to_herd.html",
        {
            "relative": relative, "sex": sex, "birth_date": birth_date, "errors": errors,
            "sex_options": Rabbit.Sex.choices, "today": flow_forms.today().isoformat(), "wide": True,
        },
        status=400 if errors else 200,
    )
