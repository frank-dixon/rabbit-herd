"""Removing things for good: rabbits whose time in Recently deleted has run out (per keeper's
retention setting), with their photo files and renditions, and add-flow photo uploads that
were abandoned (flow-pending/<user>/ files older than two days). Run daily by
`manage.py purge_deleted`; the daily-summary scheduler also calls it."""
import datetime

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from .flow_photos import PENDING_DIR
from .renditions import delete_renditions

PENDING_MAX_AGE = datetime.timedelta(days=2)


def hard_delete(rabbit):
    """Delete a rabbit and everything it owns, then its photo files once the delete commits."""
    names = [p.image.name for p in rabbit.photos.all() if p.image.name]
    with transaction.atomic():
        rabbit.delete()
        for name in names:
            transaction.on_commit(lambda n=name: (default_storage.delete(n), delete_renditions(default_storage, n)))


def expired(now=None):
    from .models import HerdSettings, Rabbit

    now = now or timezone.now()
    keep = dict(HerdSettings.objects.values_list("user_id", "deleted_retention_days"))
    default = HerdSettings._meta.get_field("deleted_retention_days").default
    for rabbit in Rabbit.all_objects.filter(deleted_at__isnull=False, deleted_at__lt=now - datetime.timedelta(days=7)):
        days = keep.get(rabbit.owner_id, default)
        if rabbit.deleted_at < now - datetime.timedelta(days=days):
            yield rabbit


def purge_rabbits(now=None):
    count = 0
    for rabbit in list(expired(now)):
        hard_delete(rabbit)
        count += 1
    return count


def purge_pending(now=None, storage=default_storage):
    """Delete abandoned add-flow uploads older than two days."""
    now = now or timezone.now()
    count = 0
    try:
        users, _ = storage.listdir(PENDING_DIR)
    except (FileNotFoundError, NotImplementedError, OSError):
        return 0
    for user_dir in users:
        folder = f"{PENDING_DIR}/{user_dir}"
        try:
            _, files = storage.listdir(folder)
        except (FileNotFoundError, OSError):
            continue
        for name in files:
            path = f"{folder}/{name}"
            try:
                stamp = storage.get_modified_time(path)
            except (NotImplementedError, OSError):
                continue
            if timezone.is_naive(stamp):
                stamp = timezone.make_aware(stamp)
            if now - stamp > PENDING_MAX_AGE:
                storage.delete(path)
                count += 1
    return count


def run(now=None):
    return {"rabbits": purge_rabbits(now), "pending photos": purge_pending(now)}
