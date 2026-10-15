"""Remove stored genetics rows that are computable copies (genes design B).

Only the seeded demo account and sample content are ever touched, and only
rows the parity tool proves change nothing (see rabbits/genes_cleanup.py).
Known genes, genes with a note and every keeper's own rows are never touched.

    python manage.py genes_cleanup --dry-run            # counts only, writes nothing
    python manage.py genes_cleanup --backup FILE.json   # remove, saving every row first
    python manage.py genes_cleanup --restore FILE.json  # undo exactly

Run genetics_parity first; this refuses to run while GENETICS_READ is "old",
since the removed values would then stop showing.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Remove computable Gene and PedigreeEntry rows (demo and sample content only), reversibly."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report counts and write nothing.")
        parser.add_argument("--backup", help="Where to save the removed rows (required to remove).")
        parser.add_argument("--restore", help="Put back the rows saved in this backup file.")

    def handle(self, *args, dry_run=False, backup=None, restore=None, **opts):
        import json

        from rabbits import genes_cleanup
        from rabbits.models import Gene, PedigreeEntry

        if restore:
            data = json.loads(Path(restore).read_text())
            done = genes_cleanup.restore(data)
            self.stdout.write(f"Restored {done['genes']} gene rows and {done['pedigree']} pedigree rows; "
                              f"{done['unflagged']} rabbits read stored genes only again.")
            return

        p = genes_cleanup.plan()
        self.stdout.write(f"Gene rows: {Gene.objects.count()} now, {len(p['genes'])} computable "
                          f"(on {len(p['flag'])} rabbits), {Gene.objects.count() - len(p['genes'])} after.")
        self.stdout.write(f"Pedigree rows: {PedigreeEntry.objects.count()} now, {len(p['pedigree'])} computable, "
                          f"{PedigreeEntry.objects.count() - len(p['pedigree'])} after.")
        if dry_run:
            self.stdout.write("Dry run: nothing was changed.")
            return
        if getattr(settings, "GENETICS_READ", "old") == "old":
            raise CommandError('GENETICS_READ is "old"; set it to "new" (or "both") before removing rows.')
        if not backup:
            raise CommandError("Pass --backup FILE.json so the removal can be undone with --restore.")
        path = Path(backup)
        if path.exists():
            raise CommandError(f"{path} already exists; pick a new file.")
        path.write_text(genes_cleanup.dumps(genes_cleanup.backup(p)))
        done = genes_cleanup.apply(p)
        self.stdout.write(f"Removed {done['genes']} gene rows and {done['pedigree']} pedigree rows; "
                          f"{done['flagged']} rabbits now read their coat genes on the fly. Backup: {path}")
