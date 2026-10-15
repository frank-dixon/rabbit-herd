"""Delete offline-sync replay records older than the retention window.

A SyncOp only guards against the same queued write being applied twice, so it
needs to outlive an offline queue, not the account. Default: 30 days.

    python manage.py prune_sync_ops [--days 30] [--dry-run]
"""

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete SyncOp rows older than --days (default 30)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, days=30, dry_run=False, **opts):
        from rabbits.models import SyncOp

        old = SyncOp.objects.filter(applied_at__lt=timezone.now() - datetime.timedelta(days=max(days, 1)))
        count = old.count()
        if dry_run:
            self.stdout.write(f"{count} sync records older than {days} days would be deleted (dry run).")
            return
        old.delete()
        self.stdout.write(f"Deleted {count} sync records older than {days} days.")
