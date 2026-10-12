from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import RabbitForm
from .models import Rabbit

COLUMNS = ["Name", "Sex", "Breed", "Status"]


def owned_rabbits(user):
    return Rabbit.objects.filter(owner=user)


def owned_rabbit(user, pk):
    return get_object_or_404(owned_rabbits(user), pk=pk)


def table_rows(rabbits):
    return [
        [rabbit.name, rabbit.get_sex_display(), rabbit.breed, rabbit.get_status_display()]
        for rabbit in rabbits
    ]


@login_required
def rabbit_list(request):
    rabbits = list(owned_rabbits(request.user).filter(archived_at__isnull=True).prefetch_related("photos"))
    return render(
        request,
        "rabbits/list.html",
        {"rabbits": rabbits},
    )


@login_required
def rabbit_archived(request):
    rabbits = list(owned_rabbits(request.user).filter(archived_at__isnull=False))
    return render(
        request,
        "rabbits/archived.html",
        {"rabbits": rabbits, "columns": COLUMNS, "rows": table_rows(rabbits)},
    )


@login_required
def rabbit_detail(request, pk):
    rabbit = owned_rabbit(request.user, pk)
    photos = list(rabbit.photos.all())
    main = next((photo for photo in photos if photo.is_main), None)
    return render(
        request,
        "rabbits/detail.html",
        {"rabbit": rabbit, "main_photo": main, "extra_photos": [photo for photo in photos if photo is not main]},
    )


@login_required
def rabbit_edit(request, pk):
    rabbit = owned_rabbit(request.user, pk)
    form = RabbitForm(request.POST or None, request.FILES or None, instance=rabbit)
    if request.method == "POST" and form.is_valid():
        rabbit = form.save()
        messages.success(request, f"{rabbit.name} was saved.")
        return redirect("rabbit_detail", pk=rabbit.pk)
    return render(
        request,
        "rabbits/form.html",
        {
            "form": form,
            "rabbit": rabbit,
            "heading": "Edit rabbit",
            "submit_label": "Save changes",
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
