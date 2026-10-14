import datetime

from django.conf import settings
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import color_odds, costs, culling, genetics, purebred, shows
from .forms import GenesForm, PhotoUploadForm
from .models import Contact, Gene, HealthNote, Litter, Location, Rabbit, Weight, prefs

def owned_rabbits(user):
    return Rabbit.objects.filter(owner=user)


def owned_rabbit(user, pk):
    return get_object_or_404(owned_rabbits(user), pk=pk)


LIST_VIEWS = ("grid", "list")
LIST_VIEW_SESSION_KEY = "rabbit_list_view"


def list_view_choice(request):
    """Grid or list for the rabbit list, and the grid's density. ?view= and
    ?density= set them (plain links, so no JS is needed) and the account
    remembers both."""
    user = request.user
    changed = []
    asked = request.GET.get("view")
    if asked in LIST_VIEWS and asked != user.ui_list_view:
        user.ui_list_view = asked
        changed.append("ui_list_view")
    density = request.GET.get("density")
    if density in dict(user.DENSITIES) and density != user.ui_density:
        user.ui_density = density
        changed.append("ui_density")
    if changed:
        user.save(update_fields=changed)
    if asked in LIST_VIEWS:
        request.session[LIST_VIEW_SESSION_KEY] = asked
    return user.ui_list_view if user.ui_list_view in LIST_VIEWS else "grid"


def breed_names(breeds):
    """Breed names for the filter: purebred names and every breed in a cross."""
    names = set()
    for breed in breeds:
        text = breed or ""
        if text.lower().startswith("cross:"):
            for part in text[len("cross:"):].split(","):
                part = part.strip()
                percent, _, name = part.partition(" ")
                names.add(name.strip() if percent.endswith("%") and name else part)
        elif text:
            names.add(text.strip())
    return sorted(name for name in names if name)


# Rabbits page sort choices ("" keeps the default order).
SORTS = {"oldest": "Oldest first", "youngest": "Youngest first"}


def sort_by_age(rabbits, sort):
    """Oldest or youngest first by birth date; unknown birth dates go last."""
    known = [r for r in rabbits if r.birth_date]
    known.sort(key=lambda r: (r.birth_date, r.name.lower()), reverse=sort == "youngest")
    return known + [r for r in rabbits if not r.birth_date]


def list_filters(request):
    """Search and filter choices from GET. Unknown values are dropped."""
    get = request.GET
    sexes = dict(Rabbit.Sex.choices)
    statuses = dict(Rabbit.Status.choices)
    return {
        # "deceased" was the old name of the Former tab; old links still land there.
        "tab": {"deceased": "former"}.get(get.get("tab"), get.get("tab")) if get.get("tab") in ("archived", "deceased", "former") else "active",
        "q": " ".join(get.get("q", "").split())[:120],
        "sex": get.get("sex") if get.get("sex") in sexes else "",
        "breed": get.get("breed", "").strip()[:80],
        "status": get.get("status") if get.get("status") in statuses else "",
        "pure": get.get("pure") if get.get("pure") in ("yes", "no") else "",
        "sort": get.get("sort") if get.get("sort") in SORTS else "",
        "location": get.get("location", "") if get.get("location", "").isdigit() or get.get("location") == "none" else "",
    }


def query_string(params, **changes):
    merged = {**params, **changes}
    if merged.get("tab") == "active":
        merged.pop("tab")
    return urlencode({key: value for key, value in merged.items() if value})


def list_row_columns(user, rabbits):
    """The list view's columns: latest weight and the next open date."""
    from .tasks import open_items

    ids = {r.pk for r in rabbits}
    latest = {}
    for w in Weight.objects.filter(rabbit_id__in=ids).order_by("rabbit_id", "-date", "-pk"):
        latest.setdefault(w.rabbit_id, w)
    upcoming = {}
    for item in open_items(user):
        rabbit = item.get("rabbit")
        if rabbit and rabbit.pk in ids and rabbit.pk not in upcoming:
            upcoming[rabbit.pk] = {**item, "label": item["title"].split(":")[0] if item["kind"] == "litter" else item["title"]}
    for r in rabbits:
        r.last_weight = latest.get(r.pk)
        r.next_item = upcoming.get(r.pk)
        r.age_until = r.death_date if r.status in Rabbit.FORMER else None


@login_required
def rabbit_list(request):
    view = list_view_choice(request)
    filters = list_filters(request)
    mine = owned_rabbits(request.user)
    live = mine.filter(archived_at__isnull=True)
    # Active is the living herd; Former holds sold, culled and deceased rabbits.
    active = live.exclude(status__in=Rabbit.FORMER)
    former = live.filter(status__in=Rabbit.FORMER)
    archived = mine.filter(archived_at__isnull=False)
    rabbits = {"archived": archived, "former": former}.get(filters["tab"], active)
    if filters["q"]:
        rabbits = rabbits.filter(Q(name__icontains=filters["q"]) | Q(tattoo__iexact=filters["q"]) | Q(tattoo__icontains=filters["q"]))
    if filters["sex"]:
        rabbits = rabbits.filter(sex=filters["sex"])
    if filters["breed"]:
        rabbits = rabbits.filter(breed__icontains=filters["breed"])
    if filters["status"]:
        rabbits = rabbits.filter(status=filters["status"])
    if not settings.FEATURE_LOCATIONS:
        filters["location"] = ""
    if filters["location"] == "none":
        rabbits = rabbits.filter(location__isnull=True)
    elif filters["location"]:
        rabbits = rabbits.filter(location_id=int(filters["location"]))
    rabbits = purebred.mark(list(rabbits.select_related("location").prefetch_related("photos", *purebred.PREFETCH)))
    if filters["pure"]:
        want = filters["pure"] == "yes"
        rabbits = [rabbit for rabbit in rabbits if bool(rabbit.purebred_info) == want]
    # Sold rabbits go last; sort is stable, so each group keeps its order.
    if filters["sort"]:
        rabbits = sort_by_age(rabbits, filters["sort"])
    rabbits = sorted(rabbits, key=lambda rabbit: rabbit.status == Rabbit.Status.SOLD)
    if view == "list":
        list_row_columns(request.user, rabbits)
    # One small query gives both tab counts and the breed filter's options.
    herd = list(mine.values_list("breed", "archived_at", "status"))
    archived_count = sum(1 for _, archived_at, _ in herd if archived_at)
    former_count = sum(1 for _, archived_at, status in herd if not archived_at and status in Rabbit.FORMER)
    active_count = len(herd) - archived_count - former_count
    filtering = any(filters[key] for key in ("q", "sex", "breed", "status", "location", "pure"))
    locations = location_options(request.user) if settings.FEATURE_LOCATIONS else []
    labels = {
        "sex": dict(Rabbit.Sex.choices),
        "status": dict(Rabbit.Status.choices),
        "location": dict(locations),
        "pure": {"yes": "Purebred", "no": "Not purebred"},
    }
    chips = [
        {"key": key, "label": labels.get(key, {}).get(filters[key], filters[key]),
         "remove_qs": query_string(filters, **{key: ""})}
        for key in ("sex", "status", "breed", "location", "pure") if filters[key]
    ]
    noun = filters["tab"]
    total = {"archived": archived_count, "former": former_count}.get(filters["tab"], active_count)
    plural = "" if total == 1 else "s"
    if filtering:
        subtitle = f"{len(rabbits)} of {total} {noun} rabbit{plural}"
    elif noun == "active":
        subtitle = f"{total} active rabbit{plural} in your herd"
    else:
        subtitle = f"{total} {noun} rabbit{plural}"
    return render(
        request,
        "rabbits/list.html",
        {
            "rabbits": rabbits,
            "view": view,
            "wide": True,
            "subtitle": subtitle,
            "filters": filters,
            "filtering": filtering,
            "filter_chips": chips,
            "active_count": active_count,
            "archived_count": archived_count,
            "deleted_count": Rabbit.all_objects.filter(owner=request.user, deleted_at__isnull=False).count(),
            "former_count": former_count,
            "former_qs": query_string({}, tab="former"),
            "sex_options": Rabbit.Sex.choices,
            "sort_options": list(SORTS.items()),
            "location_options": locations,
            # Each tab offers only the statuses it can hold.
            "status_options": [(v, l) for v, l in Rabbit.Status.choices
                               if filters["tab"] == "archived" or (v in Rabbit.FORMER) == (filters["tab"] == "former")],
            "breed_options": breed_names(breed for breed, _, _ in herd),
            "view_options": [
                {"href": "?" + query_string(filters, view=key), "label": label, "icon": key, "selected": view == key}
                for key, label in (("grid", "Grid"), ("list", "List"))],
            "density_options": [
                {"href": "?" + query_string(filters, density=key), "label": label, "selected": request.user.ui_density == key}
                for key, label in request.user.DENSITIES],
            "active_qs": query_string({"view": ""}, tab="active"),
            "archived_qs": query_string({}, tab="archived"),
            "clear_qs": query_string({}, tab=filters["tab"]),
        },
    )


@login_required
def rabbit_archived(request):
    rabbits = list(owned_rabbits(request.user).filter(archived_at__isnull=False).prefetch_related("photos"))
    return render(
        request,
        "rabbits/archived.html",
        {"rabbits": rabbits, "wide": True},
    )


def location_options(user):
    options = [(str(pk), name) for pk, name in Location.objects.filter(owner=user).values_list("pk", "name")]
    return options + [("none", "No location")] if options else []


def weight_context(request, rabbit):
    from .weights import chart

    entries = list(rabbit.weights.all())
    from .models import prefs

    last_unit = prefs(request.user).weight_unit
    failed = request.session.pop("weight_form", None)
    if not failed or failed.get("rabbit") != rabbit.pk:
        failed = {"values": {}, "errors": {}}
    return {
        "weight_values": failed["values"],
        "weight_errors": failed["errors"],
        "weights": list(reversed(entries)),
        "weight_chart": chart(entries, last_unit),
        "weight_unit": last_unit,
        "weight_units": Weight.Unit.choices,
        "today": timezone.localdate().isoformat(),
    }


@login_required
def rabbit_detail(request, pk):
    rabbit = owned_rabbit(request.user, pk)
    relatives = list(
        rabbit.relatives.select_related("herd_rabbit", "outside").prefetch_related("herd_rabbit__photos")
    )
    photos = list(rabbit.photos.all())
    main = next((photo for photo in photos if photo.is_main), None)
    context = {
            "rabbit": rabbit, "retention": prefs(request.user).deleted_retention_days,
            "wide": True,
            "main_photo": main,
            "archived_litters": (Litter.objects.filter(owner=request.user, pairing__doe=rabbit, converted_at__isnull=False).count()
                                 if rabbit.sex == Rabbit.Sex.DOE else 0),
            "purebred_info": purebred.purebred(rabbit),
            "extra_photos": [photo for photo in photos if photo is not main],
            "photos": photos,
            "relatives": relatives,
            **weight_context(request, rabbit),
            "health_notes": list(rabbit.health_notes.select_related("task").prefetch_related("photos")),
            "health_kinds": HealthNote.Kind.choices,
            **culling.form_context(request, rabbit),
            **shows.form_context(request, rabbit),
            **dict(zip(("cost_items", "cost_total"), costs.linked(rabbit.expenses.all()))),
            "cost_add_url": f"/costs/new/?rabbit={rabbit.pk}",
            "today_iso": timezone.localdate().isoformat(),
            **doe_schedule_context(request, rabbit),
            "location_choices": location_options(request.user)[:-1] if settings.FEATURE_LOCATIONS else [],
            "contact_options": [(str(c.pk), str(c)) for c in Contact.objects.filter(owner=request.user)],
            "kindling_note": rabbit.kindling_note(relatives),
            "upload_form": PhotoUploadForm(),
            "c_carrier_note": genetics.c_carrier_suggestion(rabbit),
            "hidden_notes": genetics.hidden_notes(color_odds.recorded(rabbit)),
            "carrier_odds": genetics.carrier_odds(rabbit),
            "test_mates": genetics.test_mates(rabbit),
            "genes": rabbit.genes.all(),
            **smart_gene_context(rabbit),
            "relatives_with_genes": [
                (relative, list(relative.genes.all()))
                for relative in rabbit.relatives.select_related("herd_rabbit", "outside")
                if relative.genes.exists()
            ],
    }
    context["folds"] = fold_context(context, rabbit)
    return render(request, "rabbits/detail.html", context)


@login_required
@require_POST
def rabbit_c_carrier(request, pk):
    """Confirm the suggested 'probable carrier of c' note, which records
    C/c as probable, or remove it so it stops showing."""
    rabbit = owned_rabbit(request.user, pk)
    if genetics.c_carrier_suggestion(rabbit):
        if request.POST.get("action") == "confirm":
            Gene.objects.create(
                rabbit=rabbit,
                locus=Gene.Locus.C,
                genotype="C/c",
                certainty=Gene.Certainty.PROBABLE,
                note="From a c/c (albino) parent.",
            )
            messages.success(request, f"{rabbit.name} is now recorded as a probable albino (c) carrier.")
        elif request.POST.get("action") == "remove":
            rabbit.c_carrier_dismissed = True
            rabbit.save(update_fields=["c_carrier_dismissed", "updated_at"])
            messages.success(request, "The note was removed.")
    return redirect("rabbit_detail", pk=rabbit.pk)


def smart_gene_context(rabbit):
    from . import gene_card

    genes = list(rabbit.genes.all())
    card = gene_card.rows(rabbit, genes)
    return {
        "gene_card": card, "gene_card_summary": gene_card.summary(card), "gene_levels": gene_card.LEVELS,
        "gene_card_any": any(row["level"] != "unknown" for row in card) or bool(genes),
        "other_genes": [gene for gene in genes if gene.locus not in {row["locus"] for row in card}],
    }


@login_required
def rabbit_genes(request, pk):
    """Old free-text genes form. Opening it now goes to the genes card
    (dropdowns and the pattern picker), the same one the add flow uses;
    posts still save so old bookmarks and forms keep working."""
    rabbit = owned_rabbit(request.user, pk)
    if request.method != "POST":
        return redirect("rabbit_edit_step", pk=rabbit.pk, step="genes")
    form = GenesForm(request.POST or None, rabbit=rabbit)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{rabbit.name}'s genes were saved.")
        return redirect("rabbit_detail", pk=rabbit.pk)
    return render(
        request,
        "rabbits/form.html",
        {
            "form": form,
            "rabbit": rabbit,
            "heading": f"Genes {rabbit.name} carries",
            "intro": "Optional. Write a genotype like C/c or En/en, and mark it known (for example from test litters) or probable. Leave a box empty to clear it.",
            "submit_label": "Save genes",
        },
    )


@login_required
@require_POST
def rabbit_archive(request, pk):
    rabbit = owned_rabbit(request.user, pk)
    if rabbit.archived_at is None:
        rabbit.archived_at = timezone.now()
        rabbit.save(update_fields=["archived_at", "updated_at"])
    messages.success(request, f"{rabbit.name} was archived.", extra_tags="undo|" + reverse("rabbit_restore", args=[rabbit.pk]))
    return redirect("rabbit_list")


@login_required
@require_POST
def rabbit_restore(request, pk):
    rabbit = owned_rabbit(request.user, pk)
    if rabbit.archived_at is not None:
        rabbit.archived_at = None
        rabbit.save(update_fields=["archived_at", "updated_at"])
    messages.success(request, f"{rabbit.name} was restored.")
    return redirect("rabbit_detail", pk=rabbit.pk)


def delete_phrase(rabbit):
    return f"delete {rabbit.name}"


def delete_phrase_matches(rabbit, typed):
    """Case-insensitive, with outer and repeated inner spaces ignored."""
    def tidy(text):
        return " ".join(str(text or "").split()).casefold()
    return tidy(typed) == tidy(delete_phrase(rabbit))


@login_required
def rabbit_delete(request, pk):
    """Move a rabbit to Recently deleted (restorable until the keeper's retention runs out).
    GET shows the confirm page, which also works without JavaScript; the rabbit page's dialog
    posts here directly."""
    rabbit = owned_rabbit(request.user, pk)
    if request.method == "POST":
        rabbit.deleted_at = timezone.now()
        rabbit.save(update_fields=["deleted_at", "updated_at"])
        messages.success(request, f"{rabbit.name} was moved to Recently deleted.")
        return redirect("rabbit_list")
    return render(request, "rabbits/delete.html", {"rabbit": rabbit, "retention": prefs(request.user).deleted_retention_days,
                                                   "wide": True})


def deleted_rabbit(user, pk):
    return get_object_or_404(Rabbit.all_objects, owner=user, pk=pk, deleted_at__isnull=False)


@login_required
def rabbit_trash(request):
    """Recently deleted: restore a rabbit, or remove it for good (typed confirm)."""
    days = prefs(request.user).deleted_retention_days
    rabbits = list(Rabbit.all_objects.filter(owner=request.user, deleted_at__isnull=False)
                   .order_by("-deleted_at").prefetch_related("photos"))
    for rabbit in rabbits:
        rabbit.purge_on = timezone.localtime(rabbit.deleted_at).date() + datetime.timedelta(days=days)
    return render(request, "rabbits/trash.html", {"rabbits": rabbits, "retention": days})


@login_required
@require_POST
def rabbit_undelete(request, pk):
    rabbit = deleted_rabbit(request.user, pk)
    if rabbit.tattoo and Rabbit.objects.filter(owner=request.user, tattoo__iexact=rabbit.tattoo).exists():
        messages.error(request, f"Another rabbit now has ear tattoo {rabbit.tattoo}. Change one of them, then restore {rabbit.name}.")
        return redirect("rabbit_trash")
    rabbit.deleted_at = None
    rabbit.save(update_fields=["deleted_at", "updated_at"])
    messages.success(request, f"{rabbit.name} was restored.")
    return redirect("rabbit_detail", pk=rabbit.pk)


@login_required
def rabbit_delete_forever(request, pk):
    """Remove a deleted rabbit for good once its owner types "delete <name>"."""
    from .purge import hard_delete

    rabbit = deleted_rabbit(request.user, pk)
    error, typed = "", ""
    if request.method == "POST":
        typed = request.POST.get("confirm", "")
        if delete_phrase_matches(rabbit, typed):
            name = rabbit.name
            hard_delete(rabbit)
            messages.success(request, f"{name} was removed for good.")
            return redirect("rabbit_trash")
        error = f"Type “{delete_phrase(rabbit)}” exactly to remove {rabbit.name} for good."
    response = render(request, "rabbits/delete_forever.html",
                      {"rabbit": rabbit, "phrase": delete_phrase(rabbit), "typed": typed, "error": error, "wide": True})
    if error:
        response.status_code = 400
    return response


def legs_text(legs, grand):
    if legs >= grand:
        return f" · {legs} legs, enough for grand champion"
    return f" · {legs} of {grand} legs"


def fold_context(ctx, rabbit):
    """Collapsed when empty, open when there is something to see: a header summary and open flag per section."""
    def plural(n, word):
        return f"{n} {word}{'' if n == 1 else 's'}"
    shows, legs = ctx.get("show_entries") or [], ctx.get("show_legs") or 0
    notes, culls = ctx.get("health_notes") or [], ctx.get("cull_notes") or []
    editing = ctx.get("show_editing") or ctx.get("cull_editing")
    latest_cull = culls[0] if culls else None
    return {
        "shows": {"open": bool(shows) or bool(ctx.get("show_editing")),
                  "summary": (plural(len(shows), "result") + (legs_text(legs, ctx.get("legs_for_grand") or 3) if legs else "")) if shows else "None yet"},
        "health": {"open": bool(notes), "summary": plural(len(notes), "note") if notes else "None yet", "add_open": False},
        "culling": {"open": bool(culls) or bool(ctx.get("cull_editing")),
                    "summary": f"{latest_cull.get_decision_display()} · {latest_cull.date:%b} {latest_cull.date.day}" if latest_cull else "Not evaluated"},
        "location": {"open": bool(rabbit.location_id), "summary": str(rabbit.location) if rabbit.location_id else "Not set"},
        "source": {"open": bool(rabbit.source_id), "summary": rabbit.source.name if rabbit.source_id else "Not recorded"},
        "_editing": bool(editing),
    }


def doe_schedule_context(request, rabbit):
    if rabbit.sex != Rabbit.Sex.DOE:
        return {}
    from . import schedules
    from .models import prefs

    return {"schedule_options": schedules.options(request.user), "schedule_value": schedules.value_for(rabbit.breeding_schedule),
            "schedule_current": rabbit.breeding_schedule or prefs(request.user)}
