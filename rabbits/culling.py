"""Keep-or-cull notes on a rabbit. Adding and editing use the same form on
the rabbit page; ?cull=<id> loads a note into it for editing."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .health import parse
from .models import CullNote, Rabbit


def form_context(request, rabbit):
    """The culling card's notes and form state for the rabbit page."""
    notes = list(rabbit.cull_notes.all())
    editing = None
    raw = request.GET.get("cull", "")
    if raw.isdigit():
        editing = next((note for note in notes if note.pk == int(raw)), None)
    return {"cull_notes": notes, "cull_editing": editing, "cull_decisions": CullNote.Decision.choices}


def _save(request, rabbit, note):
    back = f"/rabbits/{rabbit.pk}/#culling"
    day = parse(request.POST.get("cull_date"))
    decision = request.POST.get("cull_decision", "")
    reason = request.POST.get("cull_reason", "").strip()[:1000]
    if day is None:
        messages.error(request, "Please enter the date of the evaluation.")
    elif day > timezone.localdate():
        messages.error(request, "The evaluation's date is in the future. Please check it.")
    elif decision not in CullNote.Decision.values:
        messages.error(request, "Please choose keep, cull or undecided.")
    else:
        editing = note.pk is not None
        note.date, note.decision, note.reason = day, decision, reason
        note.save()
        messages.success(request, "Evaluation saved." if editing else "Evaluation added.")
        return redirect(back)
    if note.pk:
        return redirect(f"/rabbits/{rabbit.pk}/?cull={note.pk}#culling")
    return redirect(back)


@login_required
@require_POST
def cull_add(request, pk):
    rabbit = get_object_or_404(Rabbit, owner=request.user, pk=pk)
    return _save(request, rabbit, CullNote(rabbit=rabbit))


@login_required
@require_POST
def cull_edit(request, pk):
    note = get_object_or_404(CullNote.objects.select_related("rabbit"), rabbit__owner=request.user, pk=pk)
    return _save(request, note.rabbit, note)


@login_required
@require_POST
def cull_delete(request, pk):
    note = get_object_or_404(CullNote, rabbit__owner=request.user, pk=pk)
    note.delete()
    messages.success(request, "The evaluation was removed.")
    return redirect(f"/rabbits/{note.rabbit_id}/#culling")
