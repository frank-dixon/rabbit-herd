from django.core.management import call_command
from django.db import migrations


def create_table(apps, schema_editor):
    call_command("createcachetable", "ratelimit", verbosity=0)  # no-op when the table exists


class Migration(migrations.Migration):
    dependencies = [("accounts", "0015_ui_mark")]
    operations = [migrations.RunPython(create_table, migrations.RunPython.noop)]
