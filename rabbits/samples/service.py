"""Create and clear sample content for one account.

Sample rabbits are Maple (doe) and Cedar (buck). Dates are offsets from today.
Adding is idempotent by sample_key. Clearing never deletes a real row.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from rabbits.models import (
    Contact, Expense, HealthNote, Litter, LitterKit, Location, OutsideRabbit,
    Pairing, PedigreeEntry, Program, Rabbit, RabbitPhoto, Relative, ShowEntry,
    Task, WaitlistEntry, Weight,
)
from rabbits.samples.registry import SAMPLE_CHILD_MODELS, SAMPLE_OWNER_MODELS

# Bundled sample photos (Frank's own; no credit required). Copied into the
# user's photo storage on first add so the photo pipeline works unchanged.
PHOTO_DIR = Path(__file__).resolve().parent / "photos"

SCREENS = {
    "rabbits": ("rabbits.doe", "rabbits.buck", "locations.hutch", "contacts.breeder"),
    "pairings": ("pairings.main",),
    "litters": ("litters.kindled", "litters.expecting", "litters.kits"),
    "today": ("tasks.weigh", "tasks.nest"),
    "tasks": ("tasks.weigh", "tasks.nest", "tasks.done"),
    "weights": ("weights.litter", "weights.buck"),
    "health": ("health.checkup", "health.treatment"),
    "photos": ("photos.doe", "photos.buck", "photos.kit"),
    "contacts": ("contacts.breeder", "waitlist.buyer"),
    "family": ("pedigree.cedar", "outside.ancestors"),
    "costs": ("costs.feed",),
    "shows": ("shows.entry",),
}

# Parents a screen also needs so its samples make sense.
NEEDS = {
    "pairings": ("rabbits",),
    "litters": ("rabbits", "pairings"),
    "today": ("rabbits", "pairings", "litters"),
    "tasks": ("rabbits", "pairings", "litters"),
    "weights": ("rabbits", "pairings", "litters"),
    "health": ("rabbits",),
    "photos": ("rabbits", "pairings", "litters"),
    "family": ("rabbits", "pairings", "litters"),
    "contacts": (),
    "costs": (),
    "shows": ("rabbits",),
    "rabbits": (),
}


def sample_count(user):
    n = 0
    from rabbits import models as M
    for name in SAMPLE_OWNER_MODELS + SAMPLE_CHILD_MODELS:
        model = getattr(M, name)
        if any(f.name == "owner" for f in model._meta.fields):
            n += model.objects.filter(owner=user, is_sample=True).count()
        elif name in {"Weight", "HealthNote", "RabbitPhoto", "ShowEntry", "PedigreeEntry", "Relative"}:
            n += model.objects.filter(rabbit__owner=user, is_sample=True).count()
        elif name == "LitterKit":
            n += model.objects.filter(litter__owner=user, is_sample=True).count()
    return n


def screen_has_samples(user, screen):
    keys = SCREENS.get(screen, ())
    if not keys:
        return False
    # Any one key present means this screen's samples were added.
    return Rabbit.objects.filter(owner=user, is_sample=True, sample_key__in=keys).exists() or \
        Pairing.objects.filter(owner=user, is_sample=True, sample_key__in=keys).exists() or \
        Litter.objects.filter(owner=user, is_sample=True, sample_key__in=keys).exists() or \
        Task.objects.filter(owner=user, is_sample=True, sample_key__in=keys).exists() or \
        Contact.objects.filter(owner=user, is_sample=True, sample_key__in=keys).exists() or \
        WaitlistEntry.objects.filter(owner=user, is_sample=True, sample_key__in=keys).exists() or \
        HealthNote.objects.filter(rabbit__owner=user, is_sample=True, sample_key__in=keys).exists() or \
        Weight.objects.filter(rabbit__owner=user, is_sample=True, sample_key__in=keys).exists() or \
        Expense.objects.filter(owner=user, is_sample=True, sample_key__in=keys).exists() or \
        ShowEntry.objects.filter(rabbit__owner=user, is_sample=True, sample_key__in=keys).exists() or \
        OutsideRabbit.objects.filter(owner=user, is_sample=True, sample_key__in=keys).exists()


def _has(user, key):
    for model in (Rabbit, Location, Contact, Pairing, Litter, Task, Expense, WaitlistEntry, OutsideRabbit):
        if model.objects.filter(owner=user, sample_key=key).exists():
            return True
    for model in (Weight, HealthNote, RabbitPhoto, ShowEntry, PedigreeEntry):
        if model.objects.filter(rabbit__owner=user, sample_key=key).exists():
            return True
    if LitterKit.objects.filter(litter__owner=user, sample_key=key).exists():
        return True
    return False


@transaction.atomic
def add_samples(user, screen, today=None):
    """Add the sample set for one screen (and its parents). Idempotent by sample_key."""
    today = today or timezone.localdate()
    for parent in NEEDS.get(screen, ()):
        add_samples(user, parent, today=today)
    if screen == "rabbits":
        _rabbits(user, today)
    elif screen == "pairings":
        _pairings(user)
    elif screen == "litters":
        _litters(user, today)
    elif screen in {"today", "tasks"}:
        _tasks(user, today, done=screen == "tasks")
    elif screen == "weights":
        _weights(user, today)
    elif screen == "health":
        _health(user, today)
    elif screen == "photos":
        _photos(user)
    elif screen == "contacts":
        _contacts(user)
    elif screen == "family":
        _family(user)
    elif screen == "costs":
        _costs(user, today)
    elif screen == "shows":
        _shows(user, today)
    return sample_count(user)


def _rabbits(user, today):
    loc, _ = Location.objects.get_or_create(
        owner=user, sample_key="locations.hutch",
        defaults={"name": "Hutch A", "is_sample": True})
    breeder, _ = Contact.objects.get_or_create(
        owner=user, sample_key="contacts.breeder",
        defaults={"name": "Pine Hill Rabbitry", "is_breeder": True, "is_sample": True, "notes": "Where Cedar came from."})
    if not _has(user, "rabbits.doe"):
        Rabbit.objects.create(
            owner=user, name="Maple", sex=Rabbit.Sex.DOE, breed="New Zealand", color="Broken chestnut",
            birth_date=today - timedelta(days=500), status=Rabbit.Status.BREEDING, tattoo="S-MAP",
            location=loc, is_sample=True, sample_key="rabbits.doe")
    if not _has(user, "rabbits.buck"):
        Rabbit.objects.create(
            owner=user, name="Cedar", sex=Rabbit.Sex.BUCK, breed="New Zealand", color="Black",
            birth_date=today - timedelta(days=730), status=Rabbit.Status.BREEDING, tattoo="S-CED",
            location=loc, source=breeder, is_sample=True, sample_key="rabbits.buck")


def _doe(user):
    return Rabbit.objects.get(owner=user, sample_key="rabbits.doe")


def _buck(user):
    return Rabbit.objects.get(owner=user, sample_key="rabbits.buck")


def _pairings(user):
    if _has(user, "pairings.main"):
        return
    Pairing.objects.create(owner=user, doe=_doe(user), buck=_buck(user), is_sample=True, sample_key="pairings.main")


def _pair(user):
    return Pairing.objects.get(owner=user, sample_key="pairings.main")


def _litters(user, today):
    pair = _pair(user)
    if not _has(user, "litters.kindled"):
        lit = Litter.objects.create(
            owner=user, pairing=pair, bred_on=today - timedelta(days=45),
            kindled_on=today - timedelta(days=14), born_alive=6, died_after=0,
            is_sample=True, sample_key="litters.kindled")
        for i in range(1, 7):
            LitterKit.objects.create(
                litter=lit, number=i, sex=Rabbit.Sex.DOE if i % 2 else Rabbit.Sex.BUCK,
                color="Broken chestnut" if i <= 2 else "Black",
                is_sample=True, sample_key="litters.kits")
    if not _has(user, "litters.expecting"):
        Litter.objects.create(
            owner=user, pairing=pair, bred_on=today - timedelta(days=22),
            is_sample=True, sample_key="litters.expecting")


def _tasks(user, today, done=False):
    lit = Litter.objects.filter(owner=user, sample_key="litters.kindled").first()
    if not _has(user, "tasks.weigh"):
        Task.objects.create(
            owner=user, title="Weigh Maple's litter", due_on=today, rabbit=_doe(user),
            is_sample=True, sample_key="tasks.weigh")
    if not _has(user, "tasks.nest"):
        Task.objects.create(
            owner=user, title="Put the nest box in for Maple", due_on=today + timedelta(days=1),
            rabbit=_doe(user), is_sample=True, sample_key="tasks.nest")
    if done and not _has(user, "tasks.done"):
        Task.objects.create(
            owner=user, title="Check Maple's nest", due_on=today - timedelta(days=3),
            rabbit=_doe(user), done_at=timezone.now() - timedelta(days=2),
            is_sample=True, sample_key="tasks.done")


def _weights(user, today):
    doe = _doe(user)
    buck = _buck(user)
    if not Weight.objects.filter(rabbit=doe, sample_key="weights.litter").exists():
        for age, g in ((0, 400), (7, 900), (14, 1800)):
            Weight.objects.create(
                rabbit=doe, date=today - timedelta(days=14 - age), grams=g,
                is_sample=True, sample_key="weights.litter")
    if not Weight.objects.filter(rabbit=buck, sample_key="weights.buck").exists():
        Weight.objects.create(rabbit=buck, date=today - timedelta(days=30), grams=4500, is_sample=True, sample_key="weights.buck")
        Weight.objects.create(rabbit=buck, date=today - timedelta(days=7), grams=4600, is_sample=True, sample_key="weights.buck")


def _health(user, today):
    doe = _doe(user)
    if not _has_child(HealthNote, doe, "health.checkup"):
        HealthNote.objects.create(
            rabbit=doe, date=today - timedelta(days=10), kind=HealthNote.Kind.CHECKUP,
            notes="Bright eyes, good flesh. Sample checkup.", is_sample=True, sample_key="health.checkup")
    if not _has_child(HealthNote, doe, "health.treatment"):
        HealthNote.objects.create(
            rabbit=doe, date=today - timedelta(days=3), kind=HealthNote.Kind.TREATMENT,
            notes="Sample topical treatment.", follow_up_on=today + timedelta(days=4),
            is_sample=True, sample_key="health.treatment")


def _has_child(model, rabbit, key):
    return model.objects.filter(rabbit=rabbit, sample_key=key).exists()


def _photos(user):
    """Attach bundled photos when files exist; otherwise skip quietly."""
    doe, buck = _doe(user), _buck(user)
    for rabbit, key, fname in (
        (doe, "photos.doe", "maple.jpg"),
        (buck, "photos.buck", "cedar.jpg"),
    ):
        if _has_child(RabbitPhoto, rabbit, key):
            continue
        path = PHOTO_DIR / fname
        if not path.exists():
            continue
        from django.core.files import File
        photo = RabbitPhoto(rabbit=rabbit, is_main=True, is_sample=True, sample_key=key,
                            notes="Sample photo.")
        with path.open("rb") as fh:
            photo.image.save(fname, File(fh), save=True)


def _contacts(user):
    Contact.objects.get_or_create(
        owner=user, sample_key="contacts.breeder",
        defaults={"name": "Pine Hill Rabbitry", "is_breeder": True, "is_sample": True, "notes": "Where Cedar came from."})
    if not _has(user, "waitlist.buyer"):
        from django.utils import timezone as tz
        WaitlistEntry.objects.create(
            owner=user, buyer="Alex Rivera", requested_on=tz.localdate(),
            breed="New Zealand", sex="doe", color="Broken chestnut",
            is_sample=True, sample_key="waitlist.buyer")


def _family(user):
    buck = _buck(user)
    if OutsideRabbit.objects.filter(owner=user, sample_key="outside.ancestors").exists():
        return
    dam = OutsideRabbit.objects.create(
        owner=user, name="Willow", details="Black NZ · Pine Hill", is_sample=True, sample_key="outside.ancestors")
    sire = OutsideRabbit.objects.create(
        owner=user, name="Basalt", details="Black NZ · Pine Hill", is_sample=True, sample_key="outside.sire")
    PedigreeEntry.objects.create(
        rabbit=buck, position="d", outside=dam, is_sample=True, sample_key="pedigree.cedar")
    PedigreeEntry.objects.create(
        rabbit=buck, position="s", outside=sire, is_sample=True, sample_key="pedigree.cedar")


def _costs(user, today):
    if not _has(user, "costs.feed"):
        Expense.objects.create(
            owner=user, date=today - timedelta(days=5), amount="42.00", category="feed",
            description="Sample feed bag", is_sample=True, sample_key="costs.feed")


def _shows(user, today):
    if ShowEntry.objects.filter(rabbit__owner=user, sample_key="shows.entry").exists():
        return
    ShowEntry.objects.create(
        rabbit=_buck(user), show_name="County Fair", date=today - timedelta(days=60),
        placing=2, is_sample=True, sample_key="shows.entry")


@transaction.atomic
def clear_samples(user):
    """Detach real references to samples, then delete every sample row. Real rows stay."""
    # 1. Detach real rabbits from sample location / contact.
    Rabbit.objects.filter(owner=user, is_sample=False, location__is_sample=True).update(location=None)
    Rabbit.objects.filter(owner=user, is_sample=False, source__is_sample=True).update(source=None)
    # 1b. Pedigree entries on real rabbits that point at sample herd rabbits or outside samples:
    # copy name into the outside/details path by clearing the herd link and ensuring an outside row,
    # or simply null the links — keep the entry with a note via outside.
    for entry in PedigreeEntry.objects.filter(rabbit__owner=user, rabbit__is_sample=False).select_related("herd_rabbit", "outside"):
        sample_ref = (entry.herd_rabbit and entry.herd_rabbit.is_sample) or (entry.outside and entry.outside.is_sample)
        if not sample_ref:
            continue
        name = entry.herd_rabbit.name if entry.herd_rabbit and entry.herd_rabbit.is_sample else (entry.outside.name if entry.outside else "")
        details = ""
        if entry.herd_rabbit and entry.herd_rabbit.is_sample:
            details = f"{entry.herd_rabbit.color} · {entry.herd_rabbit.breed}".strip(" ·")
            if entry.herd_rabbit.tattoo:
                details = f"{details} · {entry.herd_rabbit.tattoo}".strip(" ·")
        elif entry.outside and entry.outside.is_sample:
            details = entry.outside.details
        outside = OutsideRabbit.objects.create(
            owner=user, name=name or "Ancestor", details=details or "Former sample ancestor")
        entry.herd_rabbit = None
        entry.outside = outside
        entry.save(update_fields=["herd_rabbit", "outside"])
    for rel in Relative.objects.filter(rabbit__owner=user, rabbit__is_sample=False).select_related("herd_rabbit", "outside"):
        if (rel.herd_rabbit and rel.herd_rabbit.is_sample) or (rel.outside and rel.outside.is_sample):
            rel.delete()  # relative link to a sample; the real rabbit stays
    # 2. Delete samples (children cascade from parents where FKs cascade).
    count = sample_count(user)
    # Delete children first where needed, then owners.
    for model in (Weight, HealthNote, RabbitPhoto, ShowEntry, PedigreeEntry, Relative, LitterKit):
        if model is LitterKit:
            model.objects.filter(litter__owner=user, is_sample=True).delete()
        else:
            model.objects.filter(rabbit__owner=user, is_sample=True).delete()
    for model in (Task, Litter, Pairing, Expense, WaitlistEntry, Program, Rabbit, Contact, Location, OutsideRabbit):
        model.objects.filter(owner=user, is_sample=True).delete()
    # 3. Setting: hide samples and stop the guide (Frank's default).
    user.show_samples = False
    user.guide_step = "done"
    user.save(update_fields=["show_samples", "guide_step"])
    return count
