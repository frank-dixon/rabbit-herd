from django import forms
from django.utils import timezone

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
