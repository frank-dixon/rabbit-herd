from django import forms

from .models import BreedingSchedule, HerdSettings

TATTOO_TOKENS = ("{prefix}", "{yy}", "{year}", "{n}", "{nn}", "{nnn}")


class UnitsForm(forms.ModelForm):
    class Meta:
        model = HerdSettings
        fields = ["weight_unit"]


class ScheduleChecks:
    """Range and order checks shared by Standard and named schedules."""
    LIMITS = {
        "gestation_days": (28, 35), "palpate_day": (9, 18), "nest_box_day": (24, 31),
        "wean_age": (21, 84), "process_age": (42, 200), "rebreed_days": (0, 120), "breeding_age_months": (3, 12),
    }

    def clean(self):
        data = super().clean()
        for name, (low, high) in self.LIMITS.items():
            value = data.get(name)
            if value is not None and not low <= value <= high:
                self.add_error(name, f"Enter a number from {low} to {high}.")
        nest, gestation = data.get("nest_box_day"), data.get("gestation_days")
        if nest and gestation and nest >= gestation and "nest_box_day" not in self.errors:
            self.add_error("nest_box_day", "The nest box goes in before the due day. Enter a smaller number.")
        wean, process = data.get("wean_age"), data.get("process_age")
        if wean and process and process <= wean and "process_age" not in self.errors:
            self.add_error("process_age", "Processing comes after weaning. Enter a larger number.")
        return data


class ScheduleForm(ScheduleChecks, forms.ModelForm):
    class Meta:
        model = HerdSettings
        fields = ["gestation_days", "palpate_day", "nest_box_day", "wean_age", "process_age",
                  "rebreed_days", "breeding_age_months"]


class BreedingScheduleForm(ScheduleChecks, forms.ModelForm):
    """Add and edit a named schedule. New ones start from the Standard values."""

    class Meta:
        model = BreedingSchedule
        fields = ["name", "gestation_days", "palpate_day", "nest_box_day", "wean_age", "process_age", "rebreed_days"]
        labels = {"name": "Name"}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean_name(self):
        name = " ".join(self.cleaned_data.get("name", "").split())
        if name.casefold() == "standard":
            raise forms.ValidationError("Standard is your default schedule. Choose another name.")
        taken = BreedingSchedule.objects.filter(owner=self.owner, name__iexact=name).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("You already have a schedule with this name.")
        return name


class RabbitryForm(forms.ModelForm):
    class Meta:
        model = HerdSettings
        fields = ["rabbitry_name", "prefix", "tattoo_format", "deleted_retention_days"]
        labels = {"prefix": "Prefix"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deleted_retention_days"].required = False  # older forms without the field keep the setting

    def clean_deleted_retention_days(self):
        return self.cleaned_data.get("deleted_retention_days") or self.instance.deleted_retention_days or 30

    def clean_tattoo_format(self):
        value = " ".join(self.cleaned_data.get("tattoo_format", "").split())
        rest = value
        for token in TATTOO_TOKENS:
            rest = rest.replace(token, "")
        if "{" in rest or "}" in rest:
            raise forms.ValidationError("Use only {prefix}, {yy}, {year}, {n}, {nn} or {nnn} in braces.")
        return value


class RemindersForm(forms.ModelForm):
    class Meta:
        model = HerdSettings
        fields = ["remind_palpate", "remind_nest_box", "remind_due", "remind_wean", "remind_process",
                  "remind_rebreed", "remind_tasks", "daily_email", "daily_email_time"]
        widgets = {"daily_email_time": forms.TimeInput(format="%H:%M")}


SECTIONS = {"units": UnitsForm, "schedule": ScheduleForm, "rabbitry": RabbitryForm, "reminders": RemindersForm}
