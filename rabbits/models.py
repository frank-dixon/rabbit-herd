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


class Breed(models.Model):
    """A rabbit breed people can pick for a purebred or part of a cross."""

    class Registry(models.TextChoices):
        ARBA = "arba", "ARBA recognized"
        OTHER = "other", "Not ARBA recognized"

    name = models.CharField(max_length=80, unique=True)
    registry = models.CharField(max_length=8, choices=Registry.choices)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


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
    class BreedType(models.TextChoices):
        PUREBRED = "purebred", "Purebred"
        CROSSBRED = "crossbred", "Crossbred"

    name = models.CharField(max_length=120)
    sex = models.CharField(max_length=8, choices=Sex.choices)
    # A short, readable breed line. The add-a-rabbit flows fill it from the
    # purebred breed or the crossbred shares; the plain form takes it as text.
    breed = models.CharField(max_length=80)
    breed_type = models.CharField(max_length=10, choices=BreedType.choices, blank=True)
    purebred = models.ForeignKey(
        Breed,
        related_name="purebred_rabbits",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
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

    def breed_line(self):
        """Readable breed text built from the purebred breed or the shares."""
        if self.breed_type == self.BreedType.PUREBRED and self.purebred_id:
            return self.purebred.name
        if self.breed_type == self.BreedType.CROSSBRED:
            shares = self.breed_shares.select_related("breed").order_by("-percent", "breed__name")
            parts = [f"{share.percent}% {share.breed.name}" for share in shares]
            if parts:
                return f"Cross: {', '.join(parts)}"
        return self.breed

    def pedigree_by_position(self):
        return {
            entry.position: entry
            for entry in self.pedigree_entries.select_related("herd_rabbit", "outside")
        }


class BreedShare(models.Model):
    """One breed's percentage in a crossbred rabbit. Shares total 100."""

    rabbit = models.ForeignKey(Rabbit, related_name="breed_shares", on_delete=models.CASCADE)
    breed = models.ForeignKey(Breed, related_name="shares", on_delete=models.PROTECT)
    percent = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rabbit", "breed"], name="one_share_per_breed"),
            models.CheckConstraint(
                condition=models.Q(percent__gte=1) & models.Q(percent__lte=99),
                name="share_percent_1_to_99",
            ),
        ]

    def __str__(self):
        return f"{self.percent}% {self.breed}"


class OutsideRabbit(models.Model):
    """A rabbit that is not in the herd, kept so relatives and pedigrees can
    name it. Entries are reusable across the owner's rabbits."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="outside_rabbits",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=120)
    details = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional. Ear tag, registration number, breeder, or color.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        if self.details:
            return f"{self.name} ({self.details})"
        return self.name


def one_reference():
    """Exactly one of herd_rabbit and outside is set."""
    return (
        models.Q(herd_rabbit__isnull=False, outside__isnull=True)
        | models.Q(herd_rabbit__isnull=True, outside__isnull=False)
    )


class Relative(models.Model):
    """A known relative, either a herd rabbit or an outside entry."""

    class Relationship(models.TextChoices):
        DAM = "dam", "Dam (mother)"
        SIRE = "sire", "Sire (father)"
        SIBLING = "sibling", "Full sibling"
        HALF_SIBLING = "half_sibling", "Half sibling"
        OFFSPRING = "offspring", "Offspring"
        GRANDDAM = "granddam", "Granddam"
        GRANDSIRE = "grandsire", "Grandsire"
        GRANDOFFSPRING = "grandoffspring", "Grandchild"
        AUNT_UNCLE = "aunt_uncle", "Aunt or uncle"
        NIECE_NEPHEW = "niece_nephew", "Niece or nephew"
        COUSIN = "cousin", "Cousin"
        OTHER = "other", "Other relative"

    rabbit = models.ForeignKey(Rabbit, related_name="relatives", on_delete=models.CASCADE)
    relationship = models.CharField(max_length=16, choices=Relationship.choices)
    herd_rabbit = models.ForeignKey(
        Rabbit,
        related_name="relative_of",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    outside = models.ForeignKey(
        OutsideRabbit,
        related_name="relative_of",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )

    class Meta:
        ordering = ["relationship", "pk"]
        constraints = [
            models.CheckConstraint(condition=one_reference(), name="relative_has_one_reference"),
        ]

    @property
    def other(self):
        return self.herd_rabbit or self.outside

    def __str__(self):
        return f"{self.get_relationship_display()}: {self.other}"


def pedigree_positions(generations=3):
    """Positions as paths from the rabbit: s is the sire, d the dam, sd the
    sire's dam, and so on. Three generations give 2 + 4 + 8 = 14 positions."""
    positions = []
    current = [""]
    for _ in range(generations):
        current = [path + step for path in current for step in "sd"]
        positions.extend(current)
    return positions


PEDIGREE_GENERATIONS = 3
PEDIGREE_POSITIONS = pedigree_positions(PEDIGREE_GENERATIONS)


def position_label(position):
    """Plain words for a path, such as "Sire's dam" for sd."""
    words = {"s": "sire", "d": "dam"}
    names = [words[step] for step in position]
    text = "'s ".join(names)
    return text[0].upper() + text[1:]


class PedigreeEntry(models.Model):
    """One ancestor in a rabbit's pedigree, at a sire/dam path position."""

    rabbit = models.ForeignKey(Rabbit, related_name="pedigree_entries", on_delete=models.CASCADE)
    position = models.CharField(
        max_length=PEDIGREE_GENERATIONS,
        choices=[(position, position_label(position)) for position in PEDIGREE_POSITIONS],
    )
    herd_rabbit = models.ForeignKey(
        Rabbit,
        related_name="pedigree_appearances",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    outside = models.ForeignKey(
        OutsideRabbit,
        related_name="pedigree_appearances",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["rabbit", "position"], name="one_ancestor_per_position"),
            models.CheckConstraint(condition=one_reference(), name="pedigree_has_one_reference"),
        ]

    @property
    def ancestor(self):
        return self.herd_rabbit or self.outside

    @property
    def expected_sex(self):
        return Rabbit.Sex.BUCK if self.position.endswith("s") else Rabbit.Sex.DOE

    def __str__(self):
        return f"{position_label(self.position)}: {self.ancestor}"
