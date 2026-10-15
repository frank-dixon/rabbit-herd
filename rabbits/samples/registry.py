"""Every owner-scoped model is either sample-bearing or exempt. A test fails when a new one isn't listed."""

from django.apps import apps


SAMPLE_OWNER_MODELS = (
    "Rabbit", "Location", "Contact", "OutsideRabbit", "Pairing", "Litter", "Task",
    "Expense", "WaitlistEntry", "Program",
)

SAMPLE_CHILD_MODELS = (
    "Weight", "HealthNote", "RabbitPhoto", "LitterKit", "PedigreeEntry", "Relative", "ShowEntry",
)

EXEMPT_OWNER_MODELS = (
    "BreedingSchedule", "SyncOp",
)


def sample_models():
    from rabbits import models as M
    return [getattr(M, n) for n in SAMPLE_OWNER_MODELS + SAMPLE_CHILD_MODELS]


def owner_model_names():
    names = []
    for model in apps.get_models():
        if model._meta.app_label not in {"rabbits", "accounts"}:
            continue
        if any(f.name == "owner" for f in model._meta.fields):
            names.append(model.__name__)
    return sorted(names)
