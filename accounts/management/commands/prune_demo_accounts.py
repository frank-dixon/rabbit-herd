from django.core.management.base import BaseCommand

from accounts.demo import prune_demo_accounts


class Command(BaseCommand):
    help = "Delete See a demo herd copies unused for the demo herd's keep hours (24 by default)."

    def handle(self, **options):
        count = prune_demo_accounts()
        self.stdout.write(f"Deleted {count} demo account{'s' if count != 1 else ''}.")
