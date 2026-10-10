from django import forms


class ComponentExampleForm(forms.Form):
    """Sample fields for the component reference page."""

    name = forms.CharField(help_text="The name on the record.")
    email = forms.EmailField()
    password = forms.CharField(label="Password", widget=forms.PasswordInput)
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text="Optional notes.",
    )
    status = forms.ChoiceField(
        choices=[("breeding", "Breeding"), ("growing", "Growing out")]
    )
    archived = forms.BooleanField(required=False, label="Archived")
    born = forms.DateField(required=False, label="Born")
