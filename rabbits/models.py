from decimal import Decimal
from datetime import date
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


def short_breed_text(breed):
    """Shorten "Cross: 50% A, 25% B, 25% C" to "Cross · A 50% +2 more". Other text is kept."""
    text = (breed or "").strip()
    if not text.lower().startswith("cross:"):
        return text
    parts = [part.strip() for part in text[len("cross:"):].split(",") if part.strip()]
    if not parts:
        return "Cross"
    first = parts[0]
    percent, _, name = first.partition(" ")
    if percent.endswith("%") and name:
        first = f"{name.strip()} {percent}"
    more = f" +{len(parts) - 1} more" if len(parts) > 1 else ""
    return f"Cross · {first}{more}"


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
        DECEASED = "deceased", "Deceased"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="rabbits",
        on_delete=models.CASCADE,
    )
    class BreedType(models.TextChoices):
        PUREBRED = "purebred", "Purebred"
        CROSSBRED = "crossbred", "Crossbred"

    name = models.CharField(max_length=120)
    tattoo = models.CharField(
        max_length=20, blank=True, help_text="The ear tattoo ID. Unique within your herd when set."
    )
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
    death_date = models.DateField(null=True, blank=True)
    death_cause = models.CharField(max_length=120, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    location = models.ForeignKey(
        "Location",
        related_name="rabbits",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="The cage, hutch or pen this rabbit is in.",
    )
    source = models.ForeignKey(
        "Contact",
        related_name="rabbits_from",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="The breeder or rabbitry this rabbit came from.",
    )
    litter = models.ForeignKey(
        "Litter",
        related_name="kits",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="The litter this rabbit was born in, when it was added from one.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        indexes = [
            models.Index(fields=["owner", "archived_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                "owner", models.functions.Upper("tattoo"),
                condition=~models.Q(tattoo=""), name="one_tattoo_per_owner",
            ),
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
            parts = [f"{share_text(share.percent)}% {share.breed.name}" for share in shares]
            if parts:
                return f"Cross: {', '.join(parts)}"
        return self.breed

    def age_text(self, today=None):
        """Age such as "1 yr 9 mo", "4 mo" or "under 1 mo"."""
        today = today or date.today()
        months = (today.year - self.birth_date.year) * 12 + today.month - self.birth_date.month
        if today.day < self.birth_date.day:
            months -= 1
        if months < 1:
            return "under 1 mo"
        years, months = divmod(months, 12)
        parts = [f"{years} yr"] if years else []
        if months:
            parts.append(f"{months} mo")
        return " ".join(parts)

    def kindling_note(self, relatives=None):
        """ "Pepper died kindling this litter on May 18, 2026" when the herd
        dam's date of death is this rabbit's birth date and the cause says so."""
        rows = relatives if relatives is not None else self.relatives.select_related("herd_rabbit")
        for row in rows:
            dam = row.herd_rabbit if row.relationship == "dam" else None
            if (
                dam is not None
                and dam.death_date
                and dam.death_date == self.birth_date
                and dam.death_cause.strip().casefold() == "died kindling"
            ):
                day = dam.death_date
                return f"{dam.name} died kindling this litter on {day:%B} {day.day}, {day.year}."
        return ""

    @property
    def is_deceased(self):
        return self.status == self.Status.DECEASED

    @property
    def status_tag(self):
        """Status for tags: "Deceased · May 18, 2026" when the date is known."""
        if self.is_deceased and self.death_date:
            return f"Deceased · {self.death_date:%b} {self.death_date.day}, {self.death_date.year}"
        return self.get_status_display()

    @property
    def short_breed(self):
        """One-line breed for list cards: "Cross · Creme d'Argent 50% +2 more"."""
        return short_breed_text(self.breed)

    def pedigree_by_position(self):
        return {
            entry.position: entry
            for entry in self.pedigree_entries.select_related("herd_rabbit", "outside")
        }


SHARE_PATTERN = r"^-?\d+(\.\d+)?$"


def share_number(text):
    """Any plain number typed as a share, as a Decimal (for the running
    total), or None when it isn't a number."""
    import re
    from decimal import Decimal

    text = str(text if text is not None else "").strip()
    return Decimal(text) if re.match(SHARE_PATTERN, text) else None


def parse_share(text):
    """A valid share: more than 0 and less than 100, with at most two
    decimal places (so 12.5 and 6.25 work for generational mixes)."""
    value = share_number(text)
    if value is None or not 0 < value < 100 or value != value.quantize(Decimal("0.01")):
        return None
    return value.quantize(Decimal("0.01"))


def share_text(value):
    """12.50 -> "12.5", 50.00 -> "50"."""
    value = Decimal(value).quantize(Decimal("0.01"))
    text = f"{value:f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


class BreedShare(models.Model):
    """One breed's percentage in a crossbred rabbit. Shares total 100."""

    rabbit = models.ForeignKey(Rabbit, related_name="breed_shares", on_delete=models.CASCADE)
    breed = models.ForeignKey(Breed, related_name="shares", on_delete=models.PROTECT)
    percent = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["rabbit", "breed"], name="one_share_per_breed"),
            models.CheckConstraint(
                condition=models.Q(percent__gt=0) & models.Q(percent__lt=100),
                name="share_percent_between_0_and_100",
            ),
        ]

    def __str__(self):
        return f"{share_text(self.percent)}% {self.breed}"


class Location(models.Model):
    """A cage, hutch, pen or barn row where rabbits live."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="locations", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="one_location_name_per_owner")]

    def __str__(self):
        return self.name


class Contact(models.Model):
    """A person or rabbitry the keeper deals with: buyers and breeders."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="contacts", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    rabbitry = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    notes = models.TextField(max_length=2000, blank=True)
    is_buyer = models.BooleanField(default=False)
    is_breeder = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return f"{self.name} ({self.rabbitry})" if self.rabbitry else self.name

    @property
    def place(self):
        """What reads after "at": the rabbitry, or the person's name."""
        return self.rabbitry or self.name

    @property
    def roles(self):
        return [label for flag, label in (
            (self.is_buyer, "Buyer"), (self.is_breeder, "Breeder"),
        ) if flag]


GRAMS_PER_OUNCE = Decimal("28.349523125")


class Weight(models.Model):
    """One weighing. Stored in grams; shown in the unit it was entered in."""

    class Unit(models.TextChoices):
        LB_OZ = "lb", "lb and oz"
        KG = "kg", "kg"

    rabbit = models.ForeignKey(Rabbit, related_name="weights", on_delete=models.CASCADE)
    date = models.DateField()
    grams = models.PositiveIntegerField()
    unit = models.CharField(max_length=2, choices=Unit.choices, default=Unit.LB_OZ)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "pk"]
        constraints = [models.CheckConstraint(condition=models.Q(grams__gt=0), name="weight_positive")]

    def __str__(self):
        return f"{self.rabbit} {self.date}: {self.text}"

    @property
    def text(self):
        return weight_text(self.grams, self.unit)


def weight_text(grams, unit):
    """1985 g -> "4 lb 6 oz" or "1.99 kg"."""
    if unit == Weight.Unit.KG:
        return f"{Decimal(grams) / 1000:.2f}".rstrip("0").rstrip(".") + " kg"
    ounces = int((Decimal(grams) / GRAMS_PER_OUNCE).quantize(Decimal("1")))
    pounds, ounces = divmod(ounces, 16)
    if not pounds:
        return f"{ounces} oz"
    return f"{pounds} lb" + (f" {ounces} oz" if ounces else "")


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
    breed = models.CharField(
        max_length=80, blank=True, help_text="An outside relative's breed. Herd rabbits use their own breed."
    )

    class Meta:
        ordering = ["relationship", "pk"]
        constraints = [
            models.CheckConstraint(condition=one_reference(), name="relative_has_one_reference"),
        ]

    @property
    def other(self):
        return self.herd_rabbit or self.outside

    @property
    def breed_text(self):
        """A herd rabbit's own breed in short form, else the recorded breed."""
        if self.herd_rabbit_id:
            return self.herd_rabbit.short_breed
        return self.breed

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


def valid_taken_date(value, birth_date=None, today=None):
    """The date, or None when it's in the future or before the birth date."""
    today = today or timezone.localdate()
    if value is None or value > today or (birth_date and value < birth_date):
        return None
    return value


class RabbitPhoto(models.Model):
    """A photo of a rabbit, with notes. At most one per rabbit is the main
    photo, the one shown on the list and at the top of the detail page."""

    rabbit = models.ForeignKey(Rabbit, related_name="photos", on_delete=models.CASCADE)
    image = models.ImageField(upload_to=photo_file_path)
    notes = models.TextField(blank=True, max_length=500)
    is_main = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(default=timezone.now)
    # Only the date the photo was taken is kept from its metadata; the rest
    # is stripped. taken_from_metadata is False once the keeper sets it.
    taken_at = models.DateField(null=True, blank=True)
    taken_from_metadata = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_main", "uploaded_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["rabbit"],
                condition=models.Q(is_main=True),
                name="one_main_photo_per_rabbit",
            ),
        ]

    @property
    def date_badge(self):
        """ "Taken Mar 3, 2026" when the taken date is usable, else "Added <date>"."""
        taken = valid_taken_date(self.taken_at, self.rabbit.birth_date)
        if taken:
            return f"Taken {taken:%b} {taken.day}, {taken.year}"
        added = timezone.localtime(self.uploaded_at).date()
        return f"Added {added:%b} {added.day}, {added.year}"

    @property
    def badge_parts(self):
        """("Taken", "Mar 3, 2026") so small tiles can drop the word."""
        word, _, day = self.date_badge.partition(" ")
        return word, day

    @property
    def shows_taken(self):
        return valid_taken_date(self.taken_at, self.rabbit.birth_date) is not None

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
        V = "V", "V (Vienna, blue-eyed white)"
        SI = "Si", "Si (silvering)"
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


class Pairing(models.Model):
    """A planned or done doe x buck pairing from the keeper's own herd."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="pairings", on_delete=models.CASCADE)
    doe = models.ForeignKey(Rabbit, related_name="pairings_as_doe", on_delete=models.CASCADE)
    buck = models.ForeignKey(Rabbit, related_name="pairings_as_buck", on_delete=models.CASCADE)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.doe.name} × {self.buck.name}"


class Litter(models.Model):
    """A breeding from a pairing: the breed date gives the palpate, nest box
    and due dates; after kindling it records kits born, losses and survivors."""

    PALPATE_DAY = 12
    NEST_BOX_DAY = 28
    DUE_DAY = 31

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="litters", on_delete=models.CASCADE)
    pairing = models.ForeignKey(Pairing, related_name="litters", on_delete=models.CASCADE)
    bred_on = models.DateField()
    palpated = models.BooleanField(default=False)
    nest_box_in = models.BooleanField(default=False)
    kindled_on = models.DateField(null=True, blank=True)
    born_alive = models.PositiveSmallIntegerField(null=True, blank=True)
    born_dead = models.PositiveSmallIntegerField(default=0)
    died_after = models.PositiveSmallIntegerField(default=0, help_text="Kits lost after birth.")
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-bred_on", "-pk"]

    def __str__(self):
        return f"{self.pairing} · bred {self.bred_on:%b} {self.bred_on.day}"

    def day(self, n):
        from datetime import timedelta

        return self.bred_on + timedelta(days=n)

    @property
    def due_on(self):
        return self.day(self.DUE_DAY)

    @property
    def survivors(self):
        if self.born_alive is None:
            return None
        return max(self.born_alive - self.died_after, 0)

    def tasks(self):
        """The automatic dates, each with whether it is done."""
        kindled = self.kindled_on is not None
        return [
            {"key": "palpate", "label": "Palpate", "day": self.PALPATE_DAY, "date": self.day(self.PALPATE_DAY),
             "done": self.palpated or kindled},
            {"key": "nest_box", "label": "Put the nest box in", "day": self.NEST_BOX_DAY,
             "date": self.day(self.NEST_BOX_DAY), "done": self.nest_box_in or kindled},
            {"key": "due", "label": "Due to kindle", "day": self.DUE_DAY, "date": self.due_on, "done": kindled},
        ]

    def next_task(self):
        return next((task for task in self.tasks() if not task["done"]), None)


class Task(models.Model):
    """A to-do with a due date, added by hand or by a health note's follow-up.
    Litter dates are not stored here; they come from Litter.tasks()."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="tasks", on_delete=models.CASCADE)
    title = models.CharField(max_length=120)
    due_on = models.DateField()
    rabbit = models.ForeignKey(Rabbit, related_name="tasks", null=True, blank=True, on_delete=models.CASCADE)
    done_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_on", "pk"]

    def __str__(self):
        return self.title


class HealthNote(models.Model):
    """A dated health record for one rabbit. A follow-up date adds a task."""

    class Kind(models.TextChoices):
        TREATMENT = "treatment", "Treatment"
        ILLNESS = "illness", "Illness"
        INJURY = "injury", "Injury"
        CHECKUP = "checkup", "Checkup"
        OTHER = "other", "Other"

    rabbit = models.ForeignKey(Rabbit, related_name="health_notes", on_delete=models.CASCADE)
    date = models.DateField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    notes = models.TextField(max_length=1000, blank=True)
    follow_up_on = models.DateField(null=True, blank=True)
    task = models.OneToOneField(Task, related_name="health_note", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-pk"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.date}"


class CullNote(models.Model):
    """A keep-or-cull evaluation of one rabbit: the decision, why, and when."""

    class Decision(models.TextChoices):
        KEEP = "keep", "Keep"
        CULL = "cull", "Cull"
        UNDECIDED = "undecided", "Undecided"

    rabbit = models.ForeignKey(Rabbit, related_name="cull_notes", on_delete=models.CASCADE)
    date = models.DateField()
    decision = models.CharField(max_length=10, choices=Decision.choices)
    reason = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-pk"]

    def __str__(self):
        return f"{self.get_decision_display()} · {self.date}"


class ShowEntry(models.Model):
    """One rabbit's result at one show. A leg is an ARBA grand champion leg;
    three make a grand champion."""

    LEGS_FOR_GRAND = 3

    rabbit = models.ForeignKey(Rabbit, related_name="show_entries", on_delete=models.CASCADE)
    show_name = models.CharField(max_length=120)
    date = models.DateField()
    location = models.CharField(max_length=120, blank=True)
    show_class = models.CharField(max_length=80, blank=True, help_text="Such as Senior Doe or Junior Buck.")
    placing = models.PositiveSmallIntegerField(null=True, blank=True)
    out_of = models.PositiveSmallIntegerField(null=True, blank=True, help_text="How many were in the class.")
    award = models.CharField(max_length=80, blank=True, help_text="Such as Best of Breed or Best Opposite Sex.")
    judge = models.CharField(max_length=120, blank=True)
    leg = models.BooleanField(default=False)
    notes = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-pk"]

    def __str__(self):
        return f"{self.show_name} · {self.date}"

    @property
    def placing_text(self):
        if not self.placing:
            return ""
        n = self.placing
        suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix}" + (f" of {self.out_of}" if self.out_of else "")


class Expense(models.Model):
    """Money spent on the herd: a feed purchase or another cost. Linking a
    rabbit or a litter counts it toward that rabbit's or litter's cost."""

    class Category(models.TextChoices):
        FEED = "feed", "Feed"
        HAY = "hay", "Hay"
        SUPPLIES = "supplies", "Supplies"
        VET = "vet", "Vet and medicine"
        SHOWS = "shows", "Show fees"
        OTHER = "other", "Other"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="expenses", on_delete=models.CASCADE)
    date = models.DateField()
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.FEED)
    description = models.CharField(max_length=120, help_text="Such as 50 lb pellets or a water bottle.")
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    weight_lb = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True,
                                    help_text="For feed and hay: how many pounds were bought.")
    rabbit = models.ForeignKey(Rabbit, related_name="expenses", null=True, blank=True, on_delete=models.SET_NULL)
    litter = models.ForeignKey(Litter, related_name="expenses", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="expense_amount_not_negative"),
        ]

    def __str__(self):
        return f"{self.description} · ${self.amount}"

    @property
    def per_lb(self):
        if self.weight_lb:
            return (self.amount / self.weight_lb).quantize(Decimal("0.01"))
        return None


class WaitlistEntry(models.Model):
    """A buyer waiting for a rabbit of a given breed, sex and color."""

    class Sex(models.TextChoices):
        ANY = "", "Either"
        DOE = "doe", "Doe"
        BUCK = "buck", "Buck"

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        OFFERED = "offered", "Offered a rabbit"
        DONE = "done", "Sold"
        CANCELLED = "cancelled", "Cancelled"

    OPEN = (Status.WAITING, Status.OFFERED)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="waitlist", on_delete=models.CASCADE)
    buyer = models.CharField(max_length=120)
    reach = models.CharField(max_length=160, blank=True, help_text="Phone, email or how to reach them.")
    requested_on = models.DateField()
    breed = models.CharField(max_length=80, blank=True)
    sex = models.CharField(max_length=4, choices=Sex.choices, blank=True)
    color = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WAITING)
    deposit = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    rabbit = models.ForeignKey(Rabbit, related_name="waitlist_entries", null=True, blank=True, on_delete=models.SET_NULL,
                               help_text="The rabbit offered or sold to them.")
    notes = models.TextField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["requested_on", "pk"]

    def __str__(self):
        return f"{self.buyer} · {self.wants}"

    @property
    def wants(self):
        sex = self.get_sex_display().lower() if self.sex else ""
        if not (self.color or self.breed):
            return f"Any {sex or 'rabbit'}"
        return " ".join(part for part in (self.color, self.breed, sex) if part)

    def matches(self, rabbits):
        """Rabbits that fit the request: same sex when given, breed and color contained when given."""
        found = []
        for rabbit in rabbits:
            if self.sex and rabbit.sex != self.sex:
                continue
            if self.breed and self.breed.casefold() not in rabbit.breed.casefold():
                continue
            if self.color and self.color.casefold() not in rabbit.color.casefold():
                continue
            found.append(rabbit)
        return found
