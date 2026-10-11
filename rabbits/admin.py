from django.contrib import admin

from .models import Breed, Rabbit


@admin.register(Rabbit)
class RabbitAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "sex", "status", "archived_at")
    list_filter = ("sex", "status")
    search_fields = ("name", "breed", "color", "owner__email")
    raw_id_fields = ("owner",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Breed)
class BreedAdmin(admin.ModelAdmin):
    list_display = ("name", "registry")
    list_filter = ("registry",)
    search_fields = ("name",)
