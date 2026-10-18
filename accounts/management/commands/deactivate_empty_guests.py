from django.core.management.base import BaseCommand

from accounts.guest import EMPTY_GUEST_DAYS, deactivate_empty_guests


class Command(BaseCommand):
    help = (f"Deactivate guest accounts with no records that went unused for {EMPTY_GUEST_DAYS} days. "
            "Guests with records are kept. Staff can reactivate them in the admin.")

    def handle(self, **options):
        count = deactivate_empty_guests()
        self.stdout.write(f"Deactivated {count} empty guest{'s' if count != 1 else ''}.")
