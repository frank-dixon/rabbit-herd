from django import forms
from django.utils import timezone

from . import photo_processing
from .models import Rabbit


class RabbitForm(forms.ModelForm):
    class Meta:
        model = Rabbit
        fields = ["name", "sex", "breed", "color", "birth_date", "status"]
        labels = {"name": "Name or ear tag"}
        help_texts = {
            "name": "A name or an ear tag.",
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


PHOTO_REQUIRED = "An upload needs a photo. Please choose one from your device."
NOTES_TOO_LONG = "Notes can be up to 500 characters. Please shorten them."


class PhotoUploadForm(forms.Form):
    """One photo, with optional notes. The file is checked and cleaned by
    rabbits.photo_processing, so what is stored is a fresh copy."""

    image = forms.FileField(
        label="Photo",
        required=False,
        help_text="A JPEG, PNG or WebP photo, up to 10 MB. Location and camera details are removed when it's saved.",
        widget=forms.FileInput(attrs={"accept": photo_processing.ACCEPT}),
    )
    notes = forms.CharField(
        label="Notes",
        required=False,
        max_length=500,
        error_messages={"max_length": NOTES_TOO_LONG},
        help_text="Optional. For example, the date, the show, or what the photo shows.",
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 500}),
    )

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        if not upload:
            raise forms.ValidationError(PHOTO_REQUIRED)
        return photo_processing.clean_photo(upload)

    def clean_notes(self):
        return self.cleaned_data["notes"].strip()


class PhotoNotesForm(forms.Form):
    notes = forms.CharField(
        required=False, max_length=500, error_messages={"max_length": NOTES_TOO_LONG}
    )

    def clean_notes(self):
        return self.cleaned_data["notes"].strip()
