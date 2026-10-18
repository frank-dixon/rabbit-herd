"""Sample screen context for list pages: sample_screen + sample_screen_ready.

"Add samples" shows in page headers only while the keeper has no real rabbits
yet (an empty herd); a populated herd adds samples from Settings. Whether this
screen's samples were added is only looked up when the button can show."""

from rabbits.samples.service import screen_has_samples


def has_real_rabbits(user):
    from rabbits import derived
    from rabbits.models import Rabbit

    return derived.memo(("has_real_rabbits", user.pk),
                        lambda: Rabbit.all_objects.filter(owner=user, is_sample=False, deleted_at__isnull=True).exists())


def sample_ctx(user, screen):
    if not user.is_authenticated or not getattr(user, "show_samples", False) or has_real_rabbits(user):
        return {"sample_screen": None, "sample_screen_ready": True}
    return {
        "sample_screen": screen,
        "sample_screen_ready": screen_has_samples(user, screen),
    }
