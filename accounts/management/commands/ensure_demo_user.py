import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User


class Command(BaseCommand):
    help = (
        "Create or update a confirmed demo user from DEMO_EMAIL and DEMO_PASSWORD. "
        "Safe to run on every deploy. Does nothing when either variable is unset."
    )

    def handle(self, *args, **options):
        email = os.environ.get("DEMO_EMAIL", "").strip().lower()
        password = os.environ.get("DEMO_PASSWORD", "")
        if not email or not password:
            self.stdout.write(
                "DEMO_EMAIL and DEMO_PASSWORD are unset, so no demo user was changed."
            )
            return

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User(email=email)
        user.email = email
        user.is_guest = False
        user.is_active = True
        user.email_confirmed = True
        if user.email_confirmed_at is None:
            user.email_confirmed_at = timezone.now()
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Demo user {email} is ready."))
