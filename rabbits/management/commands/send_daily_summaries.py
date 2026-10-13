from django.core.management.base import BaseCommand

from rabbits.reminders import send_due


class Command(BaseCommand):
    help = "Email each keeper's daily summary once their chosen time has passed. Run every few minutes."

    def handle(self, *args, **options):
        self.stdout.write(f"Sent {send_due()} daily summaries.")
