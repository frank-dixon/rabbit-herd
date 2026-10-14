"""Rabbit history, Django-admin style. Model signals log every add, change and delete of a
rabbit and its records (weights, health, cull notes, shows, photos) as HistoryEntry rows with
display-ready text, so any edit path is covered. `quiet()` turns logging off for bulk jobs."""
import contextlib
import datetime
import threading

from django.db.models.signals import post_delete, post_save, pre_delete, pre_save

_state = threading.local()
SKIP = {"deleted_at", "id", "owner", "created_at", "updated_at", "c_carrier_dismissed", "image", "uploaded_at", "relative", "next_occurrence"}


@contextlib.contextmanager
def quiet():
    previous = getattr(_state, "off", False)
    _state.off = True
    try:
        yield
    finally:
        _state.off = previous


def off():
    return getattr(_state, "off", False)


def display(instance, field):
    """A field's value as people read it: choice labels, related names, short dates, Yes/No."""
    if field.is_relation:
        related = getattr(instance, field.name, None)
        return str(related) if related is not None else ""
    value = getattr(instance, field.attname)
    if value in (None, ""):
        return ""
    if field.choices:
        return str(dict(field.flatchoices).get(value, value))
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime.datetime):
        return "Yes" if field.name == "archived_at" else f"{value:%a, %b} {value.day}"
    if isinstance(value, datetime.date):
        return f"{value:%a, %b} {value.day}, {value.year}"
    return str(value)


def label(field):
    if field.name == "archived_at":
        return "Archived"
    text = str(field.verbose_name)
    return text[:1].upper() + text[1:]


def tracked(model):
    return [f for f in model._meta.concrete_fields if f.name not in SKIP and not f.primary_key and f.name != "rabbit"]


def diff(old, new):
    changes = []
    for field in tracked(type(new)):
        before, after = display(old, field), display(new, field)
        if before != after:
            changes.append({"field": label(field), "old": before, "new": after})
    return changes


def describe(instance):
    """Short subject text for a record: "weight 4 lb 6 oz on Tue, Oct 13"."""
    from .models import Weight, weight_text

    name = instance._meta.verbose_name
    date = getattr(instance, "date", None)
    when = f" on {date:%a, %b} {date.day}" if isinstance(date, datetime.date) else ""
    if isinstance(instance, Weight):
        return f"weight {weight_text(instance.grams, instance.unit)}{when}"
    if hasattr(instance, "kind"):
        return f"{instance.get_kind_display().lower()} note{when}"
    if hasattr(instance, "decision"):
        return f"cull note ({instance.get_decision_display().lower()}){when}"
    if hasattr(instance, "locus"):
        return f"genes ({instance.get_locus_display()})"
    if hasattr(instance, "show_name"):
        return f"show entry {instance.show_name}{when}"
    return f"{name}{when}"


def log(rabbit_id, action, subject, summary, changes=()):
    from .models import HistoryEntry

    HistoryEntry.objects.create(rabbit_id=rabbit_id, action=action, subject=subject, summary=summary[:200],
                                changes=list(changes))


def _remember(sender, instance, raw=False, **kwargs):
    if raw or off() or not instance.pk:
        instance._history_old = None
        return
    instance._history_old = sender._base_manager.filter(pk=instance.pk).first()


def _rabbit_saved(sender, instance, created, raw=False, **kwargs):
    if raw or off():
        return
    if created:
        log(instance.pk, "added", "rabbit", f"Added {instance.name}.")
        return
    old = getattr(instance, "_history_old", None)
    if old is None:
        return
    if bool(old.deleted_at) != bool(instance.deleted_at):
        log(instance.pk, "deleted" if instance.deleted_at else "changed", "rabbit",
            "Moved to Recently deleted." if instance.deleted_at else "Restored from Recently deleted.")
        return
    changes = diff(old, instance)
    if changes:
        names = ", ".join(c["field"] for c in changes)
        log(instance.pk, "changed", "rabbit", f"Changed {names}.", changes)


def _child_saved(sender, instance, created, raw=False, **kwargs):
    if raw or off() or not getattr(instance, "rabbit_id", None):
        return
    if created:
        log(instance.rabbit_id, "added", sender._meta.verbose_name, f"Added {describe(instance)}.")
        return
    old = getattr(instance, "_history_old", None)
    changes = diff(old, instance) if old is not None else []
    if changes:
        log(instance.rabbit_id, "changed", sender._meta.verbose_name,
            f"Changed {describe(instance)}: {', '.join(c['field'] for c in changes)}.", changes)


def _child_deleted(sender, instance, **kwargs):
    from .models import Rabbit

    rabbit_id = getattr(instance, "rabbit_id", None)
    if off() or not rabbit_id or rabbit_id in getattr(_state, "going", set()):
        return  # the rabbit itself is going; its history goes with it
    if not Rabbit._base_manager.filter(pk=rabbit_id).exists():
        return
    log(instance.rabbit_id, "deleted", sender._meta.verbose_name, f"Deleted {describe(instance)}.")


def _rabbit_going(sender, instance, **kwargs):
    going = getattr(_state, "going", None)
    if going is None:
        going = _state.going = set()
    going.add(instance.pk)


def _rabbit_gone(sender, instance, **kwargs):
    getattr(_state, "going", set()).discard(instance.pk)


def connect():
    from .models import CullNote, Gene, HealthNote, Rabbit, RabbitPhoto, ShowEntry, Weight

    pre_save.connect(_remember, sender=Rabbit, dispatch_uid="history-pre-rabbit")
    post_save.connect(_rabbit_saved, sender=Rabbit, dispatch_uid="history-post-rabbit")
    pre_delete.connect(_rabbit_going, sender=Rabbit, dispatch_uid="history-going-rabbit")
    post_delete.connect(_rabbit_gone, sender=Rabbit, dispatch_uid="history-gone-rabbit")
    for model in (Weight, HealthNote, CullNote, ShowEntry, RabbitPhoto, Gene):
        key = model._meta.label_lower
        pre_save.connect(_remember, sender=model, dispatch_uid=f"history-pre-{key}")
        post_save.connect(_child_saved, sender=model, dispatch_uid=f"history-post-{key}")
        post_delete.connect(_child_deleted, sender=model, dispatch_uid=f"history-del-{key}")


def rabbit_history(request, pk):
    """The rabbit's History page: newest first, each entry with its field changes."""
    from django.contrib.auth.decorators import login_required  # noqa: F401  (wrapped in urls)
    from django.shortcuts import get_object_or_404, render

    from .models import Rabbit

    rabbit = get_object_or_404(Rabbit, owner=request.user, pk=pk)
    entries = list(rabbit.history.all()[:300])
    return render(request, "rabbits/history.html", {"rabbit": rabbit, "entries": entries,
                                                     "more": rabbit.history.count() > len(entries)})
