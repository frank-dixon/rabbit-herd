from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User

INPUT_CLASS = "mt-1 w-full rounded border border-neutral-400 bg-white px-3 py-2"


class EmailAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Email or password is incorrect.",
        "inactive": "This account is inactive.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        username = self.fields["username"]
        username.label = "Email"
        username.widget.attrs["autocomplete"] = "username"
        username.widget.attrs["class"] = INPUT_CLASS
        self.fields["password"].widget.attrs["class"] = INPUT_CLASS

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username is not None and password:
            self.user_cache = authenticate(
                self.request,
                username=username.strip().lower(),
                password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class SignupForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"autocomplete": "username", "class": INPUT_CLASS}
        )
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password", "class": INPUT_CLASS}
        ),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password", "class": INPUT_CLASS}
        ),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with that email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The two passwords do not match.")
        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        return User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
        )
