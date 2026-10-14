import datetime
from decimal import Decimal
from datetime import date, time as clock_time
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


class LiveRabbitManager(models.Manager):
    """Rabbits that are not in Recently deleted."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


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

    # No longer in the herd: shown on the rabbit list's Former tab.
    FORMER = ("sold", "culled", "deceased")

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
    eye_color = models.CharField(max_length=20, blank=True)
    birth_date = models.DateField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.BREEDING,
    )
    # A doe's breeding schedule; null is Standard.
    breeding_schedule = models.ForeignKey("BreedingSchedule", related_name="does", null=True, blank=True,
                                          on_delete=models.SET_NULL)
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
    sold_on = models.DateField("Sold on", null=True, blank=True)
    sold_to = models.ForeignKey("Contact", related_name="rabbits_bought", null=True, blank=True,
                                on_delete=models.SET_NULL, verbose_name="Sold to")
    sale_price = models.DecimalField("Sale price", max_digits=8, decimal_places=2, null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    # Set when deleted: the rabbit sits in Recently deleted until restored or purged
    # (HerdSettings.deleted_retention_days). Rabbit.objects hides it everywhere.
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
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

    objects = LiveRabbitManager()
    all_objects = models.Manager()  # includes Recently deleted

    class Meta:
        ordering = ["name", "pk"]
        base_manager_name = "all_objects"
        indexes = [
            models.Index(fields=["owner", "archived_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                "owner", models.functions.Upper("tattoo"),
                condition=~models.Q(tattoo="") & models.Q(deleted_at__isnull=True), name="one_tattoo_per_owner",
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
        """The tiered age everywhere in the app ("19 days", "14 wk", "9 mo",
        "2 yr 8 mo"). A rabbit that died stops ageing on its death date."""
        return self.age_short(today, until=self.death_date if self.status in self.FORMER else None)

    @property
    def age_title(self):
        """The exact age, for the tooltip next to the tiered one."""
        return self.age_exact(until=self.death_date if self.status in self.FORMER else None)

    def age_short(self, today=None, until=None):
        """Tiered age: days under 8 weeks, weeks to 6 months, months to 2
        years, then "2 yr 8 mo". `until` (a death date, say) ends the count."""
        return age_tiered(self.birth_date, until or today or date.today())

    def age_exact(self, today=None, until=None):
        """The exact age for a tooltip: "147 days" or "4 months 25 days"."""
        return age_exact(self.birth_date, until or today or date.today())

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
        """Short status for pills: "Deceased", "Sold". The date goes on the meta line (died_text)."""
        return self.get_status_display()

    @property
    def died_text(self):
        """ "Died Mon, May 18" (the year too when it isn't this year), or "" when no date."""
        if not (self.is_deceased and self.death_date):
            return ""
        from django.utils import timezone

        d = self.death_date
        year = f", {d.year}" if d.year != timezone.localdate().year else ""
        return f"Died {d:%a}, {d:%b} {d.day}{year}"

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


def _months_and_days(born, on):
    months = (on.year - born.year) * 12 + on.month - born.month
    if on.day < born.day:
        months -= 1
    anchor_year, anchor_month = divmod(born.month - 1 + months, 12)
    import calendar
    year, month = born.year + anchor_year, anchor_month + 1
    day = min(born.day, calendar.monthrange(year, month)[1])
    return months, (on - date(year, month, day)).days


def age_tiered(born, on):
    if not born:
        return ""
    days = (on - born).days
    if days < 0:
        return ""
    if days < 56:
        return f"{days} day{'' if days == 1 else 's'}"
    months, _ = _months_and_days(born, on)
    if months < 6:
        return f"{days // 7} wk"
    if months < 24:
        return f"{months} mo"
    years, rest = divmod(months, 12)
    return f"{years} yr" + (f" {rest} mo" if rest else "")


def age_exact(born, on):
    if not born or on < born:
        return ""
    days = (on - born).days
    if days < 56:
        return f"{days} day{'' if days == 1 else 's'}"
    months, extra = _months_and_days(born, on)
    years, months = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'' if years == 1 else 's'}")
    if months:
        parts.append(f"{months} month{'' if months == 1 else 's'}")
    if extra:
        parts.append(f"{extra} day{'' if extra == 1 else 's'}")
    return " ".join(parts)


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
    def live_herd_rabbit(self):
        """The herd rabbit to link to, or None when it's in Recently deleted (shown, but unavailable)."""
        rabbit = self.herd_rabbit
        return rabbit if rabbit is not None and not rabbit.deleted_at else None

    @property
    def unavailable(self):
        return self.herd_rabbit is not None and bool(self.herd_rabbit.deleted_at)

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


class BreedingSchedule(models.Model):
    """A named set of breeding dates, such as a faster or slower rhythm for one
    doe. Standard is the keeper's own Settings values (HerdSettings), so it
    has no row; a null schedule anywhere means Standard."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="breeding_schedules", on_delete=models.CASCADE)
    name = models.CharField(max_length=60)
    gestation_days = models.PositiveSmallIntegerField("Gestation (days)", default=31)
    palpate_day = models.PositiveSmallIntegerField("Palpate on day", default=12)
    nest_box_day = models.PositiveSmallIntegerField("Nest box in on day", default=28)
    wean_age = models.PositiveSmallIntegerField("Wean at (days old)", default=28)
    process_age = models.PositiveSmallIntegerField("Process at (days old)", default=75)
    rebreed_days = models.PositiveSmallIntegerField("Rebreed (days after kindling)", default=42)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="one_schedule_name_per_owner")]

    def __str__(self):
        return self.name

    @property
    def summary(self):
        return f"Due day {self.gestation_days} · wean at {self.wean_age} days · rebreed {self.rebreed_days} days after"


class Pairing(models.Model):
    """A planned or done doe x buck pairing from the keeper's own herd."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="pairings", on_delete=models.CASCADE)
    doe = models.ForeignKey(Rabbit, related_name="pairings_as_doe", on_delete=models.CASCADE)
    buck = models.ForeignKey(Rabbit, related_name="pairings_as_buck", on_delete=models.CASCADE)
    notes = models.CharField(max_length=200, blank=True)
    # Override: a named schedule, or standard_schedule for Standard; neither follows the doe.
    breeding_schedule = models.ForeignKey(BreedingSchedule, related_name="pairings", null=True, blank=True,
                                          on_delete=models.SET_NULL)
    standard_schedule = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.doe.name} × {self.buck.name}"

    @property
    def follows_doe(self):
        return not self.standard_schedule and self.breeding_schedule_id is None

    def resolved_schedule(self):
        """The named schedule a new litter uses, or None for Standard."""
        if self.standard_schedule:
            return None
        return self.breeding_schedule or self.doe.breeding_schedule

    @property
    def schedule(self):
        return self.resolved_schedule() or prefs(self.owner)


class Litter(models.Model):
    """A breeding from a pairing: the breed date gives the palpate, nest box
    and due dates; after kindling it records kits born, losses and survivors."""

    # Defaults; each keeper's own come from Settings (HerdSettings).
    PALPATE_DAY = 12
    NEST_BOX_DAY = 28
    DUE_DAY = 31
    # Kit age in days, counted from kindling.
    WEAN_AGE = 28
    PROCESS_AGE = 75

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="litters", on_delete=models.CASCADE)
    pairing = models.ForeignKey(Pairing, related_name="litters", on_delete=models.CASCADE)
    # Fixed when the litter starts, so later changes only move it on request. Null is Standard.
    breeding_schedule = models.ForeignKey(BreedingSchedule, related_name="litters", null=True, blank=True,
                                          on_delete=models.SET_NULL)
    bred_on = models.DateField()
    palpated = models.BooleanField(default=False)
    nest_box_in = models.BooleanField(default=False)
    kindled_on = models.DateField(null=True, blank=True)
    rebred = models.BooleanField(default=False)
    weaned = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
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
    def schedule(self):
        """The litter's named schedule, or the owner's Standard one."""
        return self.breeding_schedule or prefs(self.owner)

    @property
    def schedule_name(self):
        return self.breeding_schedule.name if self.breeding_schedule_id else "Standard"

    @property
    def due_on(self):
        return self.day(self.schedule.gestation_days)

    @property
    def survivors(self):
        if self.born_alive is None:
            return None
        return max(self.born_alive - self.died_after, 0)

    def tasks(self):
        """The automatic dates, each with whether it is done."""
        kindled = self.kindled_on is not None
        s = self.schedule
        return [
            {"key": "palpate", "label": "Palpate", "day": s.palpate_day, "date": self.day(s.palpate_day),
             "done": self.palpated or kindled},
            {"key": "nest_box", "label": "Put the nest box in", "day": s.nest_box_day,
             "date": self.day(s.nest_box_day), "done": self.nest_box_in or kindled},
            {"key": "due", "label": "Due to kindle", "day": s.gestation_days, "date": self.due_on, "done": kindled},
        ] + self.kit_tasks()

    def kit_tasks(self):
        """Rebreed, wean and process dates, from the kindling date, once kindled."""
        if self.kindled_on is None:
            return []
        from datetime import timedelta

        s = self.schedule
        bred_days = (self.kindled_on - self.bred_on).days
        rows = [
            {"key": "rebreed", "label": "Rebreed the doe", "age": s.rebreed_days, "day": bred_days + s.rebreed_days,
             "date": self.kindled_on + timedelta(days=s.rebreed_days), "done": self.rebred},
            {"key": "wean", "label": "Wean", "age": s.wean_age, "day": bred_days + s.wean_age,
             "date": self.kindled_on + timedelta(days=s.wean_age), "done": self.weaned},
            {"key": "process", "label": "Process", "age": s.process_age, "day": bred_days + s.process_age,
             "date": self.kindled_on + timedelta(days=s.process_age), "done": self.processed},
        ]
        return sorted(rows, key=lambda row: row["date"])

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

    class Repeat(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        BIWEEKLY = "biweekly", "Every 2 weeks"
        MONTHLY = "monthly", "Monthly"
        BIMONTHLY = "bimonthly", "Every 2 months"
        QUARTERLY = "quarterly", "Every 3 months"
        CUSTOM = "custom", "Custom"

    class Unit(models.TextChoices):
        DAYS = "days", "days"
        WEEKS = "weeks", "weeks"
        MONTHS = "months", "months"

    # Blank repeat means a one-off task. Custom uses repeat_every and repeat_unit.
    repeat = models.CharField(max_length=10, choices=Repeat.choices, blank=True, default="")
    repeat_every = models.PositiveSmallIntegerField(null=True, blank=True)
    repeat_unit = models.CharField(max_length=6, choices=Unit.choices, blank=True, default="")
    # The occurrence made when this one was marked done; undo removes it.
    next_occurrence = models.OneToOneField("self", related_name="previous", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["due_on", "pk"]

    def __str__(self):
        return self.title

    PRESETS = {"daily": (1, "days"), "weekly": (1, "weeks"), "biweekly": (2, "weeks"),
               "monthly": (1, "months"), "bimonthly": (2, "months"), "quarterly": (3, "months")}

    def repeat_step(self):
        """(n, unit) or None for a one-off."""
        if self.repeat == "custom":
            return (self.repeat_every, self.repeat_unit) if self.repeat_every and self.repeat_unit else None
        return self.PRESETS.get(self.repeat)

    def repeat_label(self):
        step = self.repeat_step()
        if not step:
            return ""
        if self.repeat != "custom":
            return self.get_repeat_display()
        n, unit = step
        return f"Every {unit[:-1]}" if n == 1 else f"Every {n} {unit}"

    def next_due(self):
        step = self.repeat_step()
        return add_interval(self.due_on, *step) if step else None


def add_interval(day, n, unit):
    """day plus n days, weeks or months. Months clamp to the month's end (Jan 31 + 1 month = Feb 28/29)."""
    import calendar
    if unit == "days":
        return day + datetime.timedelta(days=n)
    if unit == "weeks":
        return day + datetime.timedelta(weeks=n)
    months = day.month - 1 + n
    year, month = day.year + months // 12, months % 12 + 1
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


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


class Cover(models.Model):
    """One mating in a litter's breeding session. Breeders often cover a doe
    more than once (again a few hours later, or the next day); the litter's
    bred date is the first cover that took, so the due dates follow it."""

    class Outcome(models.TextChoices):
        COVERED = "covered", "Covered (fall-off)"
        NO_FALL = "no_fall", "Mounted, no fall-off"
        REFUSED = "refused", "Refused"

    litter = models.ForeignKey("Litter", related_name="covers", on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    outcome = models.CharField(max_length=10, choices=Outcome.choices, default=Outcome.COVERED)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "time", "pk"]

    def __str__(self):
        return f"{self.get_outcome_display()} · {self.date}"


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


class HerdSettings(models.Model):
    """One keeper's herd preferences from the Settings page: weight units,
    breeding schedule defaults, rabbitry name and tattoo format, and which
    dates remind them. A user without a row gets the defaults (see prefs)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="herd_settings", on_delete=models.CASCADE)
    weight_unit = models.CharField("Weights in", max_length=2, choices=Weight.Unit.choices, default=Weight.Unit.LB_OZ)

    gestation_days = models.PositiveSmallIntegerField("Gestation (days)", default=31)
    palpate_day = models.PositiveSmallIntegerField("Palpate on day", default=12)
    nest_box_day = models.PositiveSmallIntegerField("Nest box in on day", default=28)
    wean_age = models.PositiveSmallIntegerField("Wean at (days old)", default=28)
    process_age = models.PositiveSmallIntegerField("Process at (days old)", default=75)
    rebreed_days = models.PositiveSmallIntegerField("Rebreed (days after kindling)", default=42)
    breeding_age_months = models.PositiveSmallIntegerField("Ready to breed at (months)", default=6)

    rabbitry_name = models.CharField(max_length=80, blank=True)
    prefix = models.CharField("Name prefix", max_length=20, blank=True)
    tattoo_format = models.CharField(max_length=40, blank=True, default="{prefix}{yy}{nn}")

    remind_palpate = models.BooleanField("Palpate", default=True)
    remind_nest_box = models.BooleanField("Nest box", default=True)
    remind_due = models.BooleanField("Due to kindle", default=True)
    remind_wean = models.BooleanField("Wean", default=True)
    remind_process = models.BooleanField("Process", default=True)
    remind_rebreed = models.BooleanField("Rebreed", default=True)
    remind_tasks = models.BooleanField("Your own tasks", default=True)
    daily_email = models.BooleanField("Email me a daily summary", default=False)
    daily_email_time = models.TimeField("Send at", default=clock_time(6, 0))
    daily_email_sent_on = models.DateField(null=True, blank=True, editable=False)

    class Retention(models.IntegerChoices):
        WEEK = 7, "7 days"
        MONTH = 30, "30 days"
        QUARTER = 90, "90 days"
        YEAR = 365, "1 year"

    deleted_retention_days = models.PositiveSmallIntegerField(
        "Keep deleted rabbits for", choices=Retention.choices, default=Retention.MONTH,
        help_text="Deleted rabbits wait in Recently deleted this long, then are removed for good.")

    name = "Standard"

    REMINDER_KEYS = {"palpate": "remind_palpate", "nest_box": "remind_nest_box", "due": "remind_due",
                     "wean": "remind_wean", "process": "remind_process", "rebreed": "remind_rebreed",
                     "task": "remind_tasks"}

    def __str__(self):
        return f"Settings for {self.user}"


def prefs(user):
    """The user's HerdSettings, or an unsaved default one. Cached on the user
    object for the request."""
    if user is None or not getattr(user, "is_authenticated", False):
        return HerdSettings()
    cached = getattr(user, "_herd_settings_cache", None)
    if cached is None:
        cached = HerdSettings.objects.filter(user=user).first() or HerdSettings(user=user)
        user._herd_settings_cache = cached
    return cached


class HistoryEntry(models.Model):
    """One change to a rabbit or its records, Django-admin style: when, what kind of change,
    a one-line summary, and the field changes (label, old, new) as display text. Written by
    rabbits.history from model signals, so every edit path (forms, inline edits, the add flow,
    imports) is logged the same way."""

    class Action(models.TextChoices):
        ADDED = "added", "Added"
        CHANGED = "changed", "Changed"
        DELETED = "deleted", "Deleted"

    rabbit = models.ForeignKey(Rabbit, related_name="history", on_delete=models.CASCADE)
    action = models.CharField(max_length=8, choices=Action.choices)
    subject = models.CharField(max_length=40, help_text="What changed: the rabbit itself, or a weight, photo…")
    summary = models.CharField(max_length=200)
    changes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.summary
