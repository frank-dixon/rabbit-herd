"""See a demo herd: a private, temporary copy of the sample herd.

Each visitor gets their own account (is_demo) holding a copy of the demo
baseline (accounts.models.DemoBaseline), with every date moved forward so it
reads as current. A demo account is fully usable but can never be saved,
signed up, merged or converted: "Start my own herd" starts a fresh guest
instead. Copies are deleted keep_hours (24) after their last use by
prune_demo_accounts, which also runs each time a new demo starts.

The copies point at the baseline's photo files rather than duplicating them,
so storage never deletes a file in the baseline owner's folders (see
rabbits.storage)."""

import datetime
import secrets

from django.contrib.auth import get_user_model, login
from django.db import transaction
from django.utils import timezone

DEMO_DOMAIN = "demo.invalid"


def baseline():
    from .models import DemoBaseline

    return DemoBaseline.objects.filter(enabled=True).select_related("owner").first()


def protected_prefixes():
    """Storage folders that hold baseline files every demo copy points at."""
    from .models import DemoBaseline

    owners = DemoBaseline.objects.values_list("owner_id", flat=True)
    return tuple(f"{folder}/{pk}/" for pk in owners for folder in ("rabbit-photos", "litter-photos")) + ("demo-baseline/",)


@transaction.atomic
def create_demo_account(today=None):
    """A new demo account holding a copy of the baseline herd, or None when no baseline is set up."""
    from rabbits.herd_ops import clone_herd

    base = baseline()
    if base is None:
        return None
    today = today or timezone.localdate()
    User = get_user_model()
    user = User.objects.create_user(
        email=f"demo-{secrets.token_hex(8)}@{DEMO_DOMAIN}",
        is_demo=True, email_confirmed=False, show_samples=False, guide_step="",
        last_seen_at=timezone.now(),
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    clone_herd(base.owner, user, shift_days=(today - base.as_of).days)
    return user


def start_demo(request):
    """Sign the browser in to a fresh demo account. Returns the account, or None without a baseline."""
    prune_demo_accounts()
    user = create_demo_account()
    if user is None:
        return None
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    base = baseline()
    request.session.set_expiry(datetime.timedelta(hours=base.keep_hours if base else 24))
    return user


def expired_demo_accounts(now=None):
    now = now or timezone.now()
    base = baseline()
    hours = base.keep_hours if base else 24
    cutoff = now - datetime.timedelta(hours=hours)
    from django.db.models import Q

    return get_user_model().objects.filter(is_demo=True).filter(
        Q(last_seen_at__lt=cutoff) | Q(last_seen_at__isnull=True, date_joined__lt=cutoff))


def _own_files(user):
    """Photo files a demo visitor uploaded themselves (not the shared baseline ones)."""
    from rabbits.models import Litter, LitterKit, OutsideRabbit, RabbitPhoto

    names = list(RabbitPhoto.objects.filter(rabbit__owner=user).values_list("image", flat=True))
    names += list(Litter.objects.filter(owner=user).exclude(photo="").values_list("photo", flat=True))
    names += list(LitterKit.objects.filter(litter__owner=user).exclude(photo="").values_list("photo", flat=True))
    names += list(OutsideRabbit.objects.filter(owner=user).exclude(photo="").exclude(photo__isnull=True).values_list("photo", flat=True))
    keep = protected_prefixes()
    return [n for n in names if n and not n.startswith(keep)]


def delete_demo_account(user):
    from django.core.files.storage import default_storage

    from rabbits.renditions import delete_renditions

    if not user.is_demo:
        raise ValueError("Only demo accounts are deleted this way.")
    files = _own_files(user)
    with transaction.atomic():
        user.delete()
        for name in files:
            transaction.on_commit(lambda n=name: (default_storage.delete(n), delete_renditions(default_storage, n)))


def prune_demo_accounts(now=None):
    """Delete demo accounts unused for keep_hours. Returns how many went."""
    count = 0
    for user in list(expired_demo_accounts(now)):
        delete_demo_account(user)
        count += 1
    return count
