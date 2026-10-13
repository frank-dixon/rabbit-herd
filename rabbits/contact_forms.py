from django import forms

from .models import Contact


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["name", "rabbitry", "phone", "email", "location", "notes", "is_buyer", "is_breeder"]
        labels = {
            "name": "Name", "rabbitry": "Rabbitry name (optional)", "phone": "Phone (optional)",
            "email": "Email (optional)", "location": "Location (optional)", "notes": "Notes (optional)",
            "is_buyer": "Buyer", "is_breeder": "Breeder",
        }
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
        error_messages = {"name": {"required": "A contact needs a name. Add one."}}

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())
