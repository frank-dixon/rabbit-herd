from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Breed, BreedShare, OutsideRabbit, PedigreeEntry, Rabbit, Relative


class BreedShareInline(TabularInline):
    model = BreedShare
    extra = 0


class RelativeInline(TabularInline):
    model = Relative
    fk_name = "rabbit"
    extra = 0
    raw_id_fields = ("herd_rabbit", "outside")


class PedigreeEntryInline(TabularInline):
    model = PedigreeEntry
    fk_name = "rabbit"
    extra = 0
    raw_id_fields = ("herd_rabbit", "outside")


@admin.register(Rabbit)
class RabbitAdmin(ModelAdmin):
    inlines = [BreedShareInline, RelativeInline, PedigreeEntryInline]
    list_display = ("name", "owner", "sex", "status", "archived_at")
    list_filter = ("sex", "status")
    search_fields = ("name", "breed", "color", "owner__email")
    raw_id_fields = ("owner",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Breed)
class BreedAdmin(ModelAdmin):
    list_display = ("name", "registry")
    list_filter = ("registry",)
    search_fields = ("name",)


@admin.register(OutsideRabbit)
class OutsideRabbitAdmin(ModelAdmin):
    list_display = ("name", "details", "owner")
    search_fields = ("name", "details", "owner__email")
    raw_id_fields = ("owner",)


# ---------------------------------------------------------------------------
# Every other rabbits model, on stock Unfold. Owner filters use an autocomplete
# so the user table is never loaded whole; foreign keys to big tables are raw ids.

from unfold.contrib.filters.admin import AutocompleteSelectFilter  # noqa: E402

from .models import (  # noqa: E402
    BreedingSchedule, Contact, Cover, CullNote, Expense, Gene, HealthNote, HerdSettings,
    HistoryEntry, KitCheck, Litter, LitterCheck, LitterKit, LitterNote, Location, Pairing,
    Program, ProgramBreeder, RabbitPhoto, ShowEntry, SyncOp, Task, WaitlistEntry, Weight,
)

OWNER_FILTER = ("owner", AutocompleteSelectFilter)


class OwnedAdmin(ModelAdmin):
    """Records with an owner: filter by owner, find by owner email."""

    list_filter_submit = True
    raw_id_fields = ("owner",)


class ReadOnlyAdmin(ModelAdmin):
    """System tables: viewable, never edited from the admin."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Location)
class LocationAdmin(OwnedAdmin):
    list_display = ("name", "owner", "is_sample", "created_at")
    list_filter = (OWNER_FILTER, "is_sample")
    search_fields = ("name", "owner__email")
    list_select_related = ("owner",)


@admin.register(Contact)
class ContactAdmin(OwnedAdmin):
    list_display = ("name", "rabbitry", "email", "phone", "is_buyer", "is_breeder", "owner")
    list_filter = (OWNER_FILTER, "is_buyer", "is_breeder", "is_sample")
    search_fields = ("name", "rabbitry", "email", "phone", "owner__email")
    list_select_related = ("owner",)


@admin.register(Weight)
class WeightAdmin(ModelAdmin):
    list_display = ("rabbit", "date", "grams", "unit", "is_sample")
    list_filter = ("date", "unit", "is_sample")
    search_fields = ("rabbit__name", "rabbit__owner__email")
    raw_id_fields = ("rabbit",)
    list_select_related = ("rabbit",)
    date_hierarchy = "date"


@admin.register(Relative)
class RelativeAdmin(ModelAdmin):
    list_display = ("rabbit", "relationship", "herd_rabbit", "outside", "is_sample")
    list_filter = ("relationship", "is_sample")
    search_fields = ("rabbit__name", "herd_rabbit__name", "outside__name", "rabbit__owner__email")
    raw_id_fields = ("rabbit", "herd_rabbit", "outside")
    list_select_related = ("rabbit", "herd_rabbit", "outside")


@admin.register(PedigreeEntry)
class PedigreeEntryAdmin(ModelAdmin):
    list_display = ("rabbit", "position", "herd_rabbit", "outside", "is_sample")
    list_filter = ("is_sample",)
    search_fields = ("rabbit__name", "herd_rabbit__name", "outside__name", "rabbit__owner__email")
    raw_id_fields = ("rabbit", "herd_rabbit", "outside")
    list_select_related = ("rabbit", "herd_rabbit", "outside")


@admin.register(BreedShare)
class BreedShareAdmin(ModelAdmin):
    list_display = ("rabbit", "breed", "percent")
    list_filter = ("breed",)
    search_fields = ("rabbit__name", "breed__name")
    raw_id_fields = ("rabbit",)
    list_select_related = ("rabbit", "breed")


@admin.register(RabbitPhoto)
class RabbitPhotoAdmin(ModelAdmin):
    list_display = ("rabbit", "is_main", "uploaded_at", "taken_at", "is_sample")
    list_filter = ("is_main", "uploaded_at", "is_sample")
    search_fields = ("rabbit__name", "rabbit__owner__email", "notes")
    raw_id_fields = ("rabbit", "health_note")
    list_select_related = ("rabbit",)


@admin.register(Gene)
class GeneAdmin(ModelAdmin):
    list_display = ("rabbit", "relative", "locus", "genotype", "certainty")
    list_filter = ("locus", "certainty")
    search_fields = ("rabbit__name", "genotype")
    raw_id_fields = ("rabbit", "relative")
    list_select_related = ("rabbit", "relative")


@admin.register(BreedingSchedule)
class BreedingScheduleAdmin(OwnedAdmin):
    list_display = ("name", "owner", "gestation_days", "wean_age", "process_age", "created_at")
    list_filter = (OWNER_FILTER,)
    search_fields = ("name", "owner__email")
    list_select_related = ("owner",)


@admin.register(Pairing)
class PairingAdmin(OwnedAdmin):
    list_display = ("doe", "buck", "owner", "breeding_schedule", "is_sample", "created_at")
    list_filter = (OWNER_FILTER, "is_sample", "created_at")
    search_fields = ("doe__name", "buck__name", "owner__email")
    raw_id_fields = ("owner", "doe", "buck", "breeding_schedule")
    list_select_related = ("owner", "doe", "buck", "breeding_schedule")


class LitterKitInline(TabularInline):
    model = LitterKit
    extra = 0
    raw_id_fields = ("rabbit",)


@admin.register(Litter)
class LitterAdmin(OwnedAdmin):
    inlines = [LitterKitInline]
    list_display = ("__str__", "owner", "bred_on", "kindled_on", "born_alive", "weaned", "converted_at", "is_sample")
    list_filter = (OWNER_FILTER, "bred_on", "kindled_on", "weaned", "processed", "is_sample")
    search_fields = ("pairing__doe__name", "pairing__buck__name", "owner__email", "notes")
    raw_id_fields = ("owner", "pairing", "breeding_schedule")
    list_select_related = ("owner", "pairing__doe", "pairing__buck")
    date_hierarchy = "bred_on"


@admin.register(LitterKit)
class LitterKitAdmin(ModelAdmin):
    list_display = ("litter", "number", "sex", "color", "rabbit", "is_sample")
    list_filter = ("sex", "is_sample")
    search_fields = ("color", "rabbit__name", "litter__owner__email")
    raw_id_fields = ("litter", "rabbit")
    list_select_related = ("litter__pairing__doe", "litter__pairing__buck", "rabbit")


@admin.register(LitterNote)
class LitterNoteAdmin(ModelAdmin):
    list_display = ("litter", "date", "text")
    list_filter = ("date",)
    search_fields = ("text", "litter__owner__email")
    raw_id_fields = ("litter",)
    list_select_related = ("litter__pairing__doe", "litter__pairing__buck")


@admin.register(LitterCheck)
class LitterCheckAdmin(ModelAdmin):
    list_display = ("litter", "date", "mode", "kit_count", "grams", "status")
    list_filter = ("date", "mode", "status")
    search_fields = ("note", "litter__owner__email")
    raw_id_fields = ("litter",)
    list_select_related = ("litter__pairing__doe", "litter__pairing__buck")


@admin.register(KitCheck)
class KitCheckAdmin(ModelAdmin):
    list_display = ("kit", "litter_check", "grams", "status")
    list_filter = ("status",)
    search_fields = ("note",)
    raw_id_fields = ("litter_check", "kit")
    list_select_related = ("kit", "litter_check")


@admin.register(Cover)
class CoverAdmin(ModelAdmin):
    list_display = ("litter", "date", "time", "outcome")
    list_filter = ("date", "outcome")
    search_fields = ("note", "litter__owner__email")
    raw_id_fields = ("litter",)
    list_select_related = ("litter__pairing__doe", "litter__pairing__buck")


class ProgramBreederInline(TabularInline):
    model = ProgramBreeder
    extra = 0


@admin.register(Program)
class ProgramAdmin(OwnedAdmin):
    inlines = [ProgramBreederInline]
    list_display = ("name", "owner", "target_label", "step", "dam", "sire", "is_sample", "created_at")
    list_filter = (OWNER_FILTER, "step", "is_sample")
    search_fields = ("name", "target_label", "owner__email")
    raw_id_fields = ("owner", "dam", "sire", "sire_outside", "g2_sire", "g2_outside", "g2_task")
    list_select_related = ("owner", "dam", "sire")


@admin.register(ProgramBreeder)
class ProgramBreederAdmin(ModelAdmin):
    list_display = ("name", "program", "sex", "breed", "rabbitry")
    list_filter = ("sex",)
    search_fields = ("name", "breed", "rabbitry", "program__name")
    raw_id_fields = ("program",)
    list_select_related = ("program",)


@admin.register(Task)
class TaskAdmin(OwnedAdmin):
    list_display = ("title", "owner", "due_on", "rabbit", "done_at", "repeat", "is_sample")
    list_filter = (OWNER_FILTER, "due_on", "done_at", "repeat", "is_sample")
    search_fields = ("title", "rabbit__name", "owner__email")
    raw_id_fields = ("owner", "rabbit", "next_occurrence")
    list_select_related = ("owner", "rabbit")
    date_hierarchy = "due_on"


@admin.register(HealthNote)
class HealthNoteAdmin(ModelAdmin):
    list_display = ("rabbit", "date", "kind", "follow_up_on", "resolved", "is_sample")
    list_filter = ("date", "kind", "resolved", "is_sample")
    search_fields = ("rabbit__name", "notes", "rabbit__owner__email")
    raw_id_fields = ("rabbit", "task")
    list_select_related = ("rabbit",)
    date_hierarchy = "date"


@admin.register(CullNote)
class CullNoteAdmin(ModelAdmin):
    list_display = ("rabbit", "date", "decision")
    list_filter = ("date", "decision")
    search_fields = ("rabbit__name", "reason", "rabbit__owner__email")
    raw_id_fields = ("rabbit",)
    list_select_related = ("rabbit",)


@admin.register(ShowEntry)
class ShowEntryAdmin(ModelAdmin):
    list_display = ("show_name", "date", "rabbit", "show_class", "placing", "out_of", "award", "leg", "is_sample")
    list_filter = ("date", "leg", "is_sample")
    search_fields = ("show_name", "location", "judge", "rabbit__name", "rabbit__owner__email")
    raw_id_fields = ("rabbit",)
    list_select_related = ("rabbit",)
    date_hierarchy = "date"


@admin.register(Expense)
class ExpenseAdmin(OwnedAdmin):
    list_display = ("date", "category", "description", "amount", "owner", "rabbit", "is_sample")
    list_filter = (OWNER_FILTER, "date", "category", "is_sample")
    search_fields = ("description", "owner__email", "rabbit__name")
    raw_id_fields = ("owner", "rabbit", "litter")
    list_select_related = ("owner", "rabbit")
    date_hierarchy = "date"


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(OwnedAdmin):
    list_display = ("buyer", "requested_on", "breed", "sex", "status", "deposit", "owner", "is_sample")
    list_filter = (OWNER_FILTER, "status", "requested_on", "is_sample")
    search_fields = ("buyer", "reach", "breed", "owner__email")
    raw_id_fields = ("owner", "rabbit")
    list_select_related = ("owner", "rabbit")


@admin.register(HerdSettings)
class HerdSettingsAdmin(ModelAdmin):
    list_display = ("user", "rabbitry_name", "weight_unit", "daily_email", "deleted_retention_days")
    list_filter = ("weight_unit", "daily_email")
    search_fields = ("user__email", "rabbitry_name", "prefix")
    raw_id_fields = ("user",)
    list_select_related = ("user",)


@admin.register(HistoryEntry)
class HistoryEntryAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "rabbit", "action", "subject", "summary")
    list_filter = ("action", "created_at")
    search_fields = ("rabbit__name", "subject", "summary")
    list_select_related = ("rabbit",)
    date_hierarchy = "created_at"


@admin.register(SyncOp)
class SyncOpAdmin(ReadOnlyAdmin):
    list_display = ("applied_at", "kind", "op_id", "owner")
    list_filter = ("kind", "applied_at")
    search_fields = ("op_id", "owner__email")
    list_select_related = ("owner",)
    date_hierarchy = "applied_at"
