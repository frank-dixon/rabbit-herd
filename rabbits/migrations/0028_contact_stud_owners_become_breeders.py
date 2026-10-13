from django.db import migrations


def stud_owners_to_breeders(apps, schema_editor):
    Contact = apps.get_model("rabbits", "Contact")
    Contact.objects.filter(is_stud_owner=True).update(is_breeder=True)


class Migration(migrations.Migration):
    """The stud-owner role is gone; anyone who had it is kept as a breeder."""

    dependencies = [("rabbits", "0027_gene_v_si")]

    operations = [
        migrations.RunPython(stud_owners_to_breeders, migrations.RunPython.noop),
        migrations.RemoveField(model_name="contact", name="is_stud_owner"),
    ]
