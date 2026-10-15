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
