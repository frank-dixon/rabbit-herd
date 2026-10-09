from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

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
class UserAdmin(BaseUserAdmin):
    form = AccountUserChangeForm
    add_form = AccountUserCreationForm
    ordering = ("email",)
    list_display = ("email", "is_staff", "is_active")
    search_fields = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
    filter_horizontal = ("groups", "user_permissions")


@admin.register(PasskeyCredential)
class PasskeyCredentialAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "sign_count")
    search_fields = ("user__email",)
