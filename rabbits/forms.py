from django import forms

from . import photo_processing
from .models import Gene


PHOTO_REQUIRED = "An upload needs a photo. Please choose one from your device."
NOTES_TOO_LONG = "Notes can be up to 500 characters. Please shorten them."


class PhotoUploadForm(forms.Form):
    """One photo, with optional notes. The file is checked and cleaned by
    rabbits.photo_processing, so what is stored is a fresh copy."""

    image = forms.FileField(
        label="Photo",
        required=False,
        help_text="A JPEG, PNG, WebP or HEIC photo. Big photos are shrunk in your browser before uploading; if your browser can't, choose one under 4 MB. Location and camera details are removed when it's saved.",
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

    # Set by the browser when it had to redraw (shrink) the photo, which loses
    # its metadata: the date it read from the original file first.
    taken_hint = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        if not upload:
            raise forms.ValidationError(PHOTO_REQUIRED)
        self.taken_at = photo_processing.read_taken_date(upload)
        return photo_processing.clean_photo(upload)

    def taken_date(self):
        """The metadata date from the file, else the browser's hint."""
        return getattr(self, "taken_at", None) or photo_processing.parse_exif_date(self.cleaned_data.get("taken_hint"))

    def clean_notes(self):
        return self.cleaned_data["notes"].strip()


class PhotoNotesForm(forms.Form):
    notes = forms.CharField(
        required=False, max_length=500, error_messages={"max_length": NOTES_TOO_LONG}
    )

    def clean_notes(self):
        return self.cleaned_data["notes"].strip()


class GenesForm(forms.Form):
    """A rabbit's own genes: a genotype per standard locus plus free-text
    Other, each known or probable. A blank genotype clears that locus."""

    def __init__(self, *args, rabbit, **kwargs):
        self.rabbit = rabbit
        current = {gene.locus: gene for gene in rabbit.genes.all()}
        initial = {}
        for locus, label in Gene.Locus.choices:
            gene = current.get(locus)
            initial[f"gene_{locus}"] = gene.genotype if gene else ""
            initial[f"cert_{locus}"] = gene.certainty if gene else Gene.Certainty.PROBABLE
        super().__init__(*args, initial=initial, **kwargs)
        for locus, label in Gene.Locus.choices:
            limit = 200 if locus == Gene.Locus.OTHER else 40
            self.fields[f"gene_{locus}"] = forms.CharField(
                label=label, max_length=limit, required=False,
                help_text="Free text, for example rex carrier." if locus == Gene.Locus.OTHER else "For example C/c.",
            )
            self.fields[f"cert_{locus}"] = forms.ChoiceField(
                label=f"{locus if locus != Gene.Locus.OTHER else 'Other'}: known or probable",
                choices=Gene.Certainty.choices,
                required=False,
            )

    def save(self):
        for locus, _ in Gene.Locus.choices:
            genotype = self.cleaned_data[f"gene_{locus}"].strip()
            certainty = self.cleaned_data[f"cert_{locus}"] or Gene.Certainty.PROBABLE
            existing = self.rabbit.genes.filter(locus=locus).first()
            if not genotype:
                if existing:
                    existing.delete()
                continue
            if existing:
                if (existing.genotype, existing.certainty) != (genotype, certainty):
                    existing.genotype, existing.certainty = genotype, certainty
                    existing.save()
            else:
                Gene.objects.create(rabbit=self.rabbit, locus=locus, genotype=genotype, certainty=certainty)
