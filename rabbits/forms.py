from django import forms
from django.utils import timezone

from .models import Rabbit

MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


class RabbitForm(forms.ModelForm):
    class Meta:
        model = Rabbit
        fields = ["name", "sex", "breed", "color", "birth_date", "photo", "status"]
        labels = {"name": "Name or ear tag"}
        help_texts = {
            "name": "A name or an ear tag.",
            "photo": "Optional. JPEG, PNG, GIF, or WebP, up to 5 MB.",
        }
        widgets = {"birth_date": forms.DateInput()}

    def save(self, commit=True):
        # The flow checked the color against the breed. A hand edit of either
        # one means that check no longer applies.
        if {"color", "breed"} & set(self.changed_data):
            self.instance.color_is_standard = None
        return super().save(commit=commit)

    def clean_birth_date(self):
        birth_date = self.cleaned_data["birth_date"]
        if birth_date > timezone.localdate():
            raise forms.ValidationError("Birth date cannot be in the future.")
        return birth_date

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo:
            return photo
        content_type = getattr(photo, "content_type", "") or ""
        if content_type and content_type not in ALLOWED_PHOTO_TYPES:
            raise forms.ValidationError("Photo must be a JPEG, PNG, GIF, or WebP image.")
        if getattr(photo, "size", 0) > MAX_PHOTO_BYTES:
            raise forms.ValidationError("Photo must be 5 MB or smaller.")
        return photo
