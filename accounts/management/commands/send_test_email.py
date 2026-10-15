"""Send one test email through the configured backend (Resend, SMTP or console).

    python manage.py send_test_email you@example.com

Prints the backend and From address, never keys. With Resend's onboarding
sender, Resend only delivers to the address that owns the Resend account."""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Send a test email to check that outgoing mail works."

    def add_arguments(self, parser):
        parser.add_argument("to", help="Recipient address")

    def handle(self, *args, to, **options):
        backend = settings.EMAIL_BACKEND.rsplit(".", 2)[-2]
        try:
            sent = send_mail(
                f"{settings.APP_NAME} test email",
                f"This is a test from {settings.APP_NAME}. If you can read it, outgoing mail works.",
                settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        except Exception as exc:  # report the failure kind, not settings
            raise CommandError(f"Sending failed via {backend}: {exc.__class__.__name__}: {exc}") from exc
        self.stdout.write(f"Sent {sent} message to {to} via {backend} from {settings.DEFAULT_FROM_EMAIL}")
