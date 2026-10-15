"""Shared query helpers for sample content."""


class SampleQuerySetMixin:
    """real(): never samples. for_view(user): hide samples when the setting is off."""

    def real(self):
        return self.filter(is_sample=False)

    def for_view(self, user):
        if getattr(user, "show_samples", True):
            return self
        return self.real()
