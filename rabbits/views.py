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

from . import derived
from . import color_odds, costs, culling, genetics, purebred, shows
from .forms import GenesForm, PhotoUploadForm
from .models import Contact, Gene, HealthNote, Litter, Location, Rabbit, Weight, prefs

def owned_rabbits(user):
    return Rabbit.objects.filter(owner=user).for_view(user)


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


# Rabbits page sort: list-view column headers and the Filter panel's Sort
# select share one ?sort= value (rabbits/sorting.py). "-age" is oldest first.
LIST_COLUMNS = [("name", "Rabbit"), ("breed", "Sex and breed"), ("age", "Age"), ("weight", "Last weight"),
                ("location", "Location"), ("next", "Next"), ("status", "Status")]
SORT_KEYS = dict(LIST_COLUMNS)
SORT_DESC_FIRST = {"weight"}
SORT_LEGACY = {"oldest": "-age", "youngest": "age"}
SORT_CHOICES = [("-age", "Oldest first"), ("age", "Youngest first"), ("name", "Name A–Z"), ("-name", "Name Z–A"),
                ("-weight", "Heaviest first"), ("weight", "Lightest first"), ("next", "Next date soonest"),
                ("breed", "Sex and breed"), ("status", "Status")]
SORT_FUNCS = {
    "name": lambda r: r.name.casefold(),
    "breed": lambda r: (r.sex, (r.short_breed or "").casefold(), r.name.casefold()),
    # Ascending age is youngest first: later birth dates first. Unknown birth dates go last.
    "age": lambda r: -r.birth_date.toordinal() if r.birth_date else None,
    "weight": lambda r: r.last_weight.grams if getattr(r, "last_weight", None) else None,
    "location": lambda r: r.location.name.casefold() if r.location_id else None,
    "next": lambda r: r.next_item["date"] if getattr(r, "next_item", None) else None,
    "status": lambda r: (str(r.status_tag), r.name.casefold()),
}


def sort_by_age(rabbits, sort):
    """Oldest or youngest first by birth date; unknown birth dates go last."""
    from . import sorting
    key, desc = sorting.parse(sort, SORT_KEYS, legacy=SORT_LEGACY)
    return sorting.apply(rabbits, SORT_FUNCS, key, desc)


def sort_token(value):
    from . import sorting
    key, desc = sorting.parse(value, SORT_KEYS, legacy=SORT_LEGACY)
    return sorting.token(key, desc) if key else ""


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
        "sort": sort_token(get.get("sort", "")),
        "location": get.get("location", "") if get.get("location", "").isdigit() or get.get("location") == "none" else "",
    }


def sort_options(current):
    options = list(SORT_CHOICES)
    if current and current not in dict(options):
        key = current.lstrip("-")
        options.append((current, f"{SORT_KEYS[key]} {'↓' if current.startswith('-') else '↑'}"))
    return options


def sort_headers(filters):
    from . import sorting
    key, desc = sorting.parse(filters["sort"], SORT_KEYS)
    params = {k: v for k, v in filters.items() if k != "sort" and v and not (k == "tab" and v == "active")}
    return {h["key"]: h for h in sorting.headers(LIST_COLUMNS, key, desc, params, SORT_DESC_FIRST)}


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
    items = open_items(user)
    for item in items:
        rabbit = item.get("rabbit")
        if rabbit and rabbit.pk in ids and rabbit.pk not in upcoming:
            upcoming[rabbit.pk] = {**item, "label": item["title"].split(":")[0] if item["kind"] == "litter" else item["title"]}
    for r in rabbits:
        r.last_weight = latest.get(r.pk)
        r.next_item = upcoming.get(r.pk)
        r.age_until = r.death_date if r.status in Rabbit.FORMER else None


def ago_text(day, today):
    days = (today - day).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days}d ago"
    if days < 63:
        return f"{days // 7} wk ago"
    return day.strftime("%b %-d") if day.year == today.year else day.strftime("%b %-d, %Y")


def card_stats(user, rabbits, today):
    """One context line per card: does (due, nursing, last litter), bucks (last
    bred), juniors (vs the breed curve). Two queries for the whole page."""
    from . import growth_curve as G

    ids = [r.pk for r in rabbits if r.status not in Rabbit.FORMER]
    by_doe, by_buck = {}, {}
    gestation = prefs(user).gestation_days
    for lit in (Litter.objects.filter(owner=user).filter(Q(pairing__doe_id__in=ids) | Q(pairing__buck_id__in=ids))
                .select_related("pairing", "breeding_schedule").order_by("-bred_on", "-pk")):
        by_doe.setdefault(lit.pairing.doe_id, []).append(lit)
        by_buck.setdefault(lit.pairing.buck_id, lit)
    for r in rabbits:
        w = getattr(r, "last_weight", None)
        r.weight_ago = ago_text(w.date, today) if w else ""
        r.stat, r.stat_tone = "", ""
        if r.status in Rabbit.FORMER:
            continue
        if r.status == Rabbit.Status.GROWING:
            points, _ = G.curve_for(r)
            vs = G.versus(points, (w.date - r.birth_date).days, w.grams) if (w and points and r.birth_date) else None
            if vs is not None:
                pct = round(abs(vs) * 100)
                if abs(vs) <= G.ON_TRACK:
                    r.stat, r.stat_tone = "On track vs curve", "g"
                else:
                    r.stat, r.stat_tone = f"{pct}% {'ahead of' if vs > 0 else 'behind'} curve", "g" if vs > 0 else "r"
            continue
        if r.sex == "doe":
            lits = by_doe.get(r.pk, [])
            open_lit = next((l for l in lits if not l.kindled_on and not l.converted_at), None)
            if open_lit:
                days = (open_lit.bred_on + datetime.timedelta(days=(open_lit.breeding_schedule.gestation_days
                        if open_lit.breeding_schedule_id else gestation)) - today).days
                if days >= -7:
                    r.stat = f"Due in {days} day{'' if days == 1 else 's'}" if days > 0 else ("Due today" if days == 0 else f"{-days} days past due")
                    r.stat_tone = "a" if days <= 3 else ""
                    continue
            kindled = next((l for l in lits if l.kindled_on), None)
            if kindled and not kindled.weaned and not kindled.converted_at and (today - kindled.kindled_on).days <= 56:
                r.stat = f"Kits {(today - kindled.kindled_on).days} days old"
            elif kindled:
                n = kindled.born_alive or 0
                r.stat = f"Last litter {kindled.kindled_on.strftime('%b %-d')} · {n} kit{'' if n == 1 else 's'}"
        elif r.sex == "buck" and r.pk in by_buck:
            r.stat = f"Last bred {by_buck[r.pk].bred_on.strftime('%b %-d')}"


@login_required
def rabbit_list(request):
    from rabbits.samples.context import sample_ctx
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
    list_row_columns(request.user, rabbits)
    card_stats(request.user, rabbits, timezone.localdate())
    if filters["sort"]:
        rabbits = sort_by_age(rabbits, filters["sort"])
    else:
        # Default order: sold rabbits go last; sort is stable, so each group keeps its order.
        rabbits = sorted(rabbits, key=lambda rabbit: rabbit.status == Rabbit.Status.SOLD)
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
    entries = rabbits
    if filters["tab"] not in ("archived", "former"):
        # Growing-out kits of one litter fold into a stacked card (litter_stacks).
        from django.db.models import prefetch_related_objects
        from .litter_stacks import stack_litters
        linked = [r for r in rabbits if r.status == Rabbit.Status.GROWING and r.litter_id]
        prefetch_related_objects(linked, "litter__pairing__doe__photos", "litter__pairing__buck__photos")
        entries = stack_litters(rabbits)
    return render(
        request,
        "rabbits/list.html",
        {
            "rabbits": rabbits,
            "entries": entries,
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
            "sort_options": sort_options(filters["sort"]),
            "sort_headers": sort_headers(filters),
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
            **sample_ctx(request.user, "rabbits"),
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
            "delete_text": delete_text(rabbit, prefs(request.user).deleted_retention_days),
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
            "genes": derived.genes_of(rabbit),
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
            derived.materialize(rabbit)
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

    genes = derived.genes_of(rabbit)
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
    from django.urls import reverse
    from .confirm import confirm_delete

    return confirm_delete(request, f"Delete {rabbit.name}?", delete_text(rabbit, prefs(request.user).deleted_retention_days),
                          reverse("rabbit_detail", args=[rabbit.pk]))


def delete_text(rabbit, days):
    keep = "a year" if days == 365 else f"{days} days"
    return f"{rabbit.name} and its photos, weights and records move to Recently deleted. You can restore it for {keep}."


def deleted_rabbit(user, pk):
    return get_object_or_404(Rabbit.all_objects, owner=user, pk=pk, deleted_at__isnull=False)


@login_required
def rabbit_trash(request):
    """Recently deleted: restore a rabbit, or remove it for good."""
    days = prefs(request.user).deleted_retention_days
    rabbits = list(Rabbit.all_objects.filter(owner=request.user, deleted_at__isnull=False)
                   .order_by("-deleted_at").prefetch_related("photos"))
    for rabbit in rabbits:
        rabbit.purge_on = timezone.localtime(rabbit.deleted_at).date() + datetime.timedelta(days=days)
        rabbit.forever_text = forever_text(rabbit)
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
    """Remove a deleted rabbit for good (GET shows the shared confirm page)."""
    from django.urls import reverse
    from .confirm import confirm_delete
    from .purge import hard_delete

    rabbit = deleted_rabbit(request.user, pk)
    if request.method == "POST":
        name = rabbit.name
        hard_delete(rabbit)
        messages.success(request, f"{name} was removed for good.")
        return redirect("rabbit_trash")
    return confirm_delete(request, f"Delete {rabbit.name} for good?", forever_text(rabbit), reverse("rabbit_trash"))


def forever_text(rabbit):
    return f"{rabbit.name} and all its photos, weights and records are removed. This can't be undone."


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
