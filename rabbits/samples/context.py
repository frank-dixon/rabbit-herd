"""Sample screen context for list pages: sample_screen + sample_screen_ready."""

from rabbits.samples.service import screen_has_samples


def sample_ctx(user, screen):
    return {
        "sample_screen": screen,
        "sample_screen_ready": screen_has_samples(user, screen) if user.is_authenticated else True,
    }
