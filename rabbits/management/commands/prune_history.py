"""Apply the rabbit history retention limit.

History is a real audit log, so nothing recent is touched. Entries older than
--days (default 730, two years) are deleted, and each rabbit also keeps at most
--keep (default 500) newest entries.

    python manage.py prune_history [--days 730] [--keep 500] [--dry-run]
"""

import datetime

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete rabbit history older than --days, and beyond --keep entries per rabbit."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=730)
        parser.add_argument("--keep", type=int, default=500)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, days=730, keep=500, dry_run=False, **opts):
        from rabbits.models import HistoryEntry

        days, keep = max(days, 30), max(keep, 50)
        aged = HistoryEntry.objects.filter(created_at__lt=timezone.now() - datetime.timedelta(days=days))
        extra_ids = []
        for row in HistoryEntry.objects.values("rabbit_id").annotate(n=Count("id")).filter(n__gt=keep):
            ids = (HistoryEntry.objects.filter(rabbit_id=row["rabbit_id"]).order_by("-created_at", "-pk")
                   .values_list("pk", flat=True)[keep:])
            extra_ids += list(ids)
        over = HistoryEntry.objects.filter(pk__in=extra_ids).exclude(pk__in=aged.values("pk"))
        aged_n, over_n = aged.count(), over.count()
        if dry_run:
            self.stdout.write(f"{aged_n} entries older than {days} days and {over_n} beyond {keep} per rabbit "
                              "would be deleted (dry run).")
            return
        aged.delete()
        over.delete()
        self.stdout.write(f"Deleted {aged_n} entries older than {days} days and {over_n} beyond {keep} per rabbit.")
