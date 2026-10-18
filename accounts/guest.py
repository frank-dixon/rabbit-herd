"""Start my own herd: guest accounts that keep their herd.

A guest is a real account row without an email or password yet
(specs/guest-mode.md). Signing up turns it into a full account in place
(SignupForm.claim), so nothing is copied and nothing is lost. Signing in to an
existing account from a guest session moves the guest's records into that
account (merge_guest_into) and retires the guest.

Guests who never added anything are deactivated after seven days unused;
staff can reactivate them in the admin. Guests with records are kept.

Demo accounts (accounts.demo) are never claimed or merged."""

import datetime
import uuid

from django.db import transaction
from django.utils import timezone

from .models import User

EMPTY_GUEST_DAYS = 7


def create_guest():
    return User.objects.create_user(
        email=f"guest-{uuid.uuid4().hex}@guest.invalid",
        password=None,
        is_guest=True,
        is_active=True,
        email_confirmed=True,
        email_confirmed_at=timezone.now(),
        guide_step="today",
        show_samples=True,
        last_seen_at=timezone.now(),
    )


class CannotMerge(Exception):
    pass


@transaction.atomic
def merge_guest_into(guest, target):
    """Move every record of guest into target and retire the guest. Sample
    records stay behind (they're not the guest's own). Safe to call twice:
    a guest already merged is left alone. Returns the number of rabbits moved."""
    from rabbits.herd_ops import move_herd
    from rabbits.samples import clear_samples

    guest = User.objects.select_for_update().get(pk=guest.pk)
    if guest.is_demo or target.is_demo:
        raise CannotMerge("A demo herd can't be saved or merged.")
    if not guest.is_guest or guest.merged_into_id or guest.pk == target.pk:
        return 0
    if target.is_guest:
        raise CannotMerge("Only a full account can take a guest herd.")
    clear_samples(guest)
    moved = move_herd(guest, target)
    guest.is_active = False
    guest.merged_into = target
    guest.deactivated_at = timezone.now()
    guest.save(update_fields=["is_active", "merged_into", "deactivated_at"])
    return moved


def idle_empty_guests(now=None):
    """Active guests unused for EMPTY_GUEST_DAYS with no records of their own."""
    from django.db.models import Q

    from rabbits.herd_ops import has_herd_data

    now = now or timezone.now()
    cutoff = now - datetime.timedelta(days=EMPTY_GUEST_DAYS)
    idle = User.objects.filter(is_guest=True, is_active=True, is_demo=False).filter(
        Q(last_seen_at__lt=cutoff) | Q(last_seen_at__isnull=True, date_joined__lt=cutoff))
    return [g for g in idle if not has_herd_data(g)]


def deactivate_empty_guests(now=None):
    """Deactivate idle empty guests (recoverable in the admin). Returns how many."""
    now = now or timezone.now()
    ids = [g.pk for g in idle_empty_guests(now)]
    return User.objects.filter(pk__in=ids).update(is_active=False, deactivated_at=now)
