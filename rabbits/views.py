from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import genetics
from .forms import GenesForm
from .models import Gene, Rabbit

def owned_rabbits(user):
    return Rabbit.objects.filter(owner=user)


def owned_rabbit(user, pk):
    return get_object_or_404(owned_rabbits(user), pk=pk)


LIST_VIEWS = ("grid", "list")
LIST_VIEW_SESSION_KEY = "rabbit_list_view"


def list_view_choice(request):
    """Grid or list for the rabbit list. ?view= sets it and the session remembers it."""
    asked = request.GET.get("view")
    if asked in LIST_VIEWS:
        request.session[LIST_VIEW_SESSION_KEY] = asked
        return asked
    saved = request.session.get(LIST_VIEW_SESSION_KEY)
    return saved if saved in LIST_VIEWS else "grid"


@login_required
def rabbit_list(request):
    rabbits = list(owned_rabbits(request.user).filter(archived_at__isnull=True).prefetch_related("photos"))
    return render(
        request,
        "rabbits/list.html",
        {
            "rabbits": rabbits,
            "view": list_view_choice(request),
            "wide": True,
            "subtitle": f"{len(rabbits)} active rabbit{'' if len(rabbits) == 1 else 's'} in your herd",
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


@login_required
def rabbit_detail(request, pk):
    rabbit = owned_rabbit(request.user, pk)
    photos = list(rabbit.photos.all())
    main = next((photo for photo in photos if photo.is_main), None)
    return render(
        request,
        "rabbits/detail.html",
        {
            "rabbit": rabbit,
            "wide": True,
            "main_photo": main,
            "extra_photos": [photo for photo in photos if photo is not main],
            "c_carrier_note": genetics.c_carrier_suggestion(rabbit),
            "genes": rabbit.genes.all(),
            "relatives_with_genes": [
                (relative, list(relative.genes.all()))
                for relative in rabbit.relatives.select_related("herd_rabbit", "outside")
                if relative.genes.exists()
            ],
        },
    )


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
            messages.success(request, f"{rabbit.name} is now recorded as a probable carrier of c.")
        elif request.POST.get("action") == "remove":
            rabbit.c_carrier_dismissed = True
            rabbit.save(update_fields=["c_carrier_dismissed", "updated_at"])
            messages.success(request, "The note was removed.")
    return redirect("rabbit_detail", pk=rabbit.pk)


@login_required
def rabbit_genes(request, pk):
    rabbit = owned_rabbit(request.user, pk)
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
    messages.success(request, f"{rabbit.name} was archived.")
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
