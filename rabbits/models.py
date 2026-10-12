import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


def rabbit_photo_path(instance, filename):
    """Upload path of the old single Rabbit.photo field. Kept because
    migration 0001 refers to it; new photos use photo_file_path."""
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
    colors = models.JSONField(
        default=list,
        blank=True,
        help_text='The recognized colors, in standard order, as [{"name": ..., "hint": ...}].',
    )
    any_color = models.BooleanField(
        default=False,
        help_text="The standard recognizes so many colors that keepers type the color in.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def color_names(self):
        """The recognized color names, in standard order."""
        return [color["name"] for color in self.colors]


OFF_STANDARD_NOTE = "(not a recognized color for this breed)"


def color_text(color, is_standard):
    """A color for display, with a note when it is known to be off-standard."""
    return f"{color} {OFF_STANDARD_NOTE}" if is_standard is False else color


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
    # True: one of the purebred breed's recognized colors. False: described
    # with Another color although the breed has a list. None: not checked
    # (crossbreds, any-color breeds, older records, or a color edited by hand).
    color_is_standard = models.BooleanField(null=True, blank=True, default=None)
    birth_date = models.DateField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.BREEDING,
    )
    line = models.CharField(
        max_length=80,
        blank=True,
        help_text="The line or strain, such as a breeder's herd name, to tell same-breed lines apart.",
    )
    c_carrier_dismissed = models.BooleanField(
        default=False,
        help_text="The keeper removed the suggested 'probable carrier of c (albino)' note.",
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
            f"{self.get_sex_display()}. {self.breed}. {self.color_line}. "
            f"Born {self.birth_date.isoformat()}. {self.get_status_display()}."
        )
        if self.is_archived:
            return f"Archived. {text}"
        return text

    @property
    def color_line(self):
        """The color, marked when it is off the breed's standard."""
        return color_text(self.color, self.color_is_standard)

    @property
    def main_photo(self):
        """The photo marked as main, or None. Uses prefetched photos when present."""
        return next((photo for photo in self.photos.all() if photo.is_main), None)

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
        help_text="Anything that helps identify it, like an ear tag, registration number, breeder, or color.",
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
        SIBLING = "sibling", "Full sibling (same dam and sire)"
        HALF_SIBLING = "half_sibling", "Half sibling (one parent in common)"
        OFFSPRING = "offspring", "Offspring (a kit or grown young)"
        GRANDDAM = "granddam", "Granddam (grandmother)"
        GRANDSIRE = "grandsire", "Grandsire (grandfather)"
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

    color = models.CharField(
        max_length=80, blank=True, help_text="The relative's color variety, such as ruby-eyed white."
    )
    line = models.CharField(max_length=80, blank=True, help_text="The relative's line or strain.")

    class Meta:
        ordering = ["relationship", "pk"]
        constraints = [
            models.CheckConstraint(condition=one_reference(), name="relative_has_one_reference"),
        ]

    @property
    def other(self):
        return self.herd_rabbit or self.outside

    def __str__(self):
        text = f"{self.get_relationship_display()}: {self.other}"
        traits = ", ".join(part for part in (self.color, self.line) if part)
        return f"{text} · {traits}" if traits else text


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


def photo_file_path(instance, filename):
    """A random name under the owner's folder. The name a keeper's phone gave
    the file is never kept, and photos are only served through an owner
    check (rabbits.photo_views), never straight from storage."""
    extension = Path(filename).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ""
    return f"rabbit-photos/{instance.rabbit.owner_id}/{uuid.uuid4().hex}{extension}"


class RabbitPhoto(models.Model):
    """A photo of a rabbit, with notes. At most one per rabbit is the main
    photo, the one shown on the list and at the top of the detail page."""

    rabbit = models.ForeignKey(Rabbit, related_name="photos", on_delete=models.CASCADE)
    image = models.ImageField(upload_to=photo_file_path)
    notes = models.TextField(blank=True, max_length=500)
    is_main = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-is_main", "uploaded_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["rabbit"],
                condition=models.Q(is_main=True),
                name="one_main_photo_per_rabbit",
            ),
        ]

    def __str__(self):
        return f"Photo of {self.rabbit.name}"


class Gene(models.Model):
    """A known or probable genotype at one locus, for a herd rabbit or for a
    relative as recorded on a rabbit (such as its dam). "Other" holds free
    text for anything outside the standard loci."""

    class Locus(models.TextChoices):
        A = "A", "A (agouti)"
        B = "B", "B (brown)"
        C = "C", "C (color, albino)"
        D = "D", "D (dilute)"
        E = "E", "E (extension)"
        EN = "En", "En (broken)"
        OTHER = "other", "Other genes"

    class Certainty(models.TextChoices):
        KNOWN = "known", "Known"
        PROBABLE = "probable", "Probable"

    rabbit = models.ForeignKey(
        Rabbit, related_name="genes", null=True, blank=True, on_delete=models.CASCADE
    )
    relative = models.ForeignKey(
        Relative, related_name="genes", null=True, blank=True, on_delete=models.CASCADE
    )
    locus = models.CharField(max_length=8, choices=Locus.choices)
    genotype = models.CharField(max_length=200, help_text="For example c/c, or En/en.")
    certainty = models.CharField(
        max_length=8, choices=Certainty.choices, default=Certainty.PROBABLE
    )
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rabbit__isnull=False, relative__isnull=True)
                | models.Q(rabbit__isnull=True, relative__isnull=False),
                name="gene_has_one_owner",
            ),
            models.UniqueConstraint(fields=["rabbit", "locus"], name="one_gene_per_rabbit_locus"),
            models.UniqueConstraint(fields=["relative", "locus"], name="one_gene_per_relative_locus"),
        ]

    def __str__(self):
        return f"{self.locus}: {self.genotype} ({self.get_certainty_display().lower()})"
