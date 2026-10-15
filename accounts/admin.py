from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm

from .models import PasskeyCredential, User


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
    list_display = ("email", "is_staff", "is_active", "email_confirmed", "is_guest")
    search_fields = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Status",
            {"fields": ("is_active", "is_guest", "email_confirmed", "email_confirmed_at")},
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


@admin.register(PasskeyCredential)
class PasskeyCredentialAdmin(ModelAdmin):
    list_display = ("user", "created_at", "sign_count")
    search_fields = ("user__email",)


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
