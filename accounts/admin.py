from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm

from unfold.decorators import action

from .models import DemoBaseline, PasskeyCredential, User


class AccountUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)


class AccountUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    change_password_form = AdminPasswordChangeForm
    form = AccountUserChangeForm
    add_form = AccountUserCreationForm
    ordering = ("email",)
    list_display = ("email", "is_staff", "is_active", "email_confirmed", "is_guest", "is_demo", "last_seen_at")
    list_filter = ("is_active", "is_guest", "is_demo", "is_staff", "email_confirmed")
    search_fields = ("email",)
    actions = ["reactivate"]
    readonly_fields = ("last_seen_at", "claimed_at", "deactivated_at", "merged_into")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Status",
            {"fields": ("is_active", "is_guest", "is_demo", "email_confirmed", "email_confirmed_at", "passkey_offer")},
        ),
        (
            "Guest lifecycle",
            {"fields": ("last_seen_at", "claimed_at", "deactivated_at", "merged_into")},
        ),
        (
            "Permissions",
            {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
    filter_horizontal = ("groups", "user_permissions")

    @action(description="Reactivate selected accounts")
    def reactivate(self, request, queryset):
        """Bring back guests deactivated for being empty and unused (never merged ones)."""
        count = queryset.filter(is_active=False, merged_into__isnull=True, is_demo=False).update(is_active=True, deactivated_at=None)
        self.message_user(request, f"Reactivated {count} account{'s' if count != 1 else ''}.")


@admin.register(DemoBaseline)
class DemoBaselineAdmin(ModelAdmin):
    """The sample herd that See a demo herd copies. Its rabbits, litters and
    tasks are the owner's ordinary records: filter any list by that owner to edit them."""

    list_display = ("owner", "as_of", "keep_hours", "enabled", "updated_at")
    list_select_related = ("owner",)
    autocomplete_fields = ("owner",)


@admin.register(PasskeyCredential)
class PasskeyCredentialAdmin(ModelAdmin):
    list_display = ("user", "created_at", "sign_count")
    search_fields = ("user__email",)


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


from django.contrib.admin.models import LogEntry  # noqa: E402


@admin.register(LogEntry)
class LogEntryAdmin(ModelAdmin):
    """The admin's own change log, read-only."""

    list_display = ("action_time", "user", "content_type", "object_repr", "action_flag")
    list_filter = ("action_flag", "action_time")
    search_fields = ("object_repr", "user__email")
    list_select_related = ("user", "content_type")
    date_hierarchy = "action_time"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
