import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


def rabbit_photo_path(instance, filename):
    """Store a photo under the owner, with a generated name."""
    extension = Path(filename).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        extension = ""
    return f"rabbits/{instance.owner_id}/{uuid.uuid4().hex}{extension}"


class Rabbit(models.Model):
    """One rabbit owned by one account. Archiving keeps the row."""

    class Sex(models.TextChoices):
        DOE = "doe", "Doe"
        BUCK = "buck", "Buck"

    class Status(models.TextChoices):
        BREEDING = "breeding", "Breeding"
        GROWING = "growing", "Growing out"
        SOLD = "sold", "Sold"
        CULLED = "culled", "Culled"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="rabbits",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=120)
    sex = models.CharField(max_length=8, choices=Sex.choices)
    breed = models.CharField(max_length=80)
    color = models.CharField(max_length=80)
    birth_date = models.DateField()
    photo = models.ImageField(upload_to=rabbit_photo_path, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.BREEDING,
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        indexes = [
            models.Index(fields=["owner", "archived_at"]),
        ]

    def __str__(self):
        return self.name

    @property
    def is_archived(self):
        return self.archived_at is not None

    def summary(self):
        text = (
            f"{self.get_sex_display()}. {self.breed}. {self.color}. "
            f"Born {self.birth_date.isoformat()}. {self.get_status_display()}."
        )
        if self.is_archived:
            return f"Archived. {text}"
        return text
