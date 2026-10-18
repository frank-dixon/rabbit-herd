"""Create the attempt-limit cache table under the name settings use.

0016 passed "ratelimit" to createcachetable, which is read as a table name, so a
fresh database got a table called "ratelimit" while CACHES points at
"rate_limit_cache", and every limit failed open. With no argument the command
creates the table of every database cache in CACHES and skips tables that exist,
so this is safe on fresh and existing databases. The stray "ratelimit" table is
left alone (harmless, and dropping it is not needed).
"""

from django.core.management import call_command
from django.db import migrations


def create_table(apps, schema_editor):
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0018_heritage_theme")]
    operations = [migrations.RunPython(create_table, migrations.RunPython.noop)]
