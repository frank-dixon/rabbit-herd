from datetime import timedelta
from email.policy import SMTP

from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode

from .tokens import email_confirmation_token

# The default email policy folds lines at 78 characters, which splits a
# confirmation link in the console. 998 is the SMTP limit, long enough for
# the link to stay on one line.
_PLAIN_POLICY = SMTP.clone(max_line_length=998)

# A repeat signup for an unconfirmed account re-sends its link at most this
# often, so the signup form cannot be used to flood someone's inbox.
CONFIRMATION_RESEND_INTERVAL = timedelta(minutes=5)


class PlainEmailMessage(EmailMessage):
    def message(self, *, policy=_PLAIN_POLICY):
        return super().message(policy=policy)


def send_account_mail(subject, body, recipient):
    PlainEmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    ).send()


def account_url(request, path):
    """Absolute URL for an account link.

    APP_HOSTNAME is the stable public host, so a message sent from production
    uses https on that host. Local requests keep the host the browser used.
    """
    host = settings.APP_HOSTNAME
    if host:
        return f"https://{host}{path}"
    return request.build_absolute_uri(path)


def send_confirmation_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_confirmation_token.make_token(user)
    url = account_url(
        request,
        reverse("confirm_email", kwargs={"uidb64": uid, "token": token}),
    )
    send_account_mail(
        "Confirm your Rabbit Herd account",
        (
            "Confirm your email to finish creating your Rabbit Herd account.\n\n"
            f"{url}\n"
        ),
        user.email,
    )
    user.confirmation_sent_at = timezone.now()
    user.save(update_fields=["confirmation_sent_at"])


def resend_confirmation_email(request, user):
    """Send a fresh confirmation link unless one went out recently.

    Returns True when a message was sent. The timestamp lives in the database
    because each serverless instance has its own memory cache.
    """
    sent_at = user.confirmation_sent_at
    if sent_at and timezone.now() - sent_at < CONFIRMATION_RESEND_INTERVAL:
        return False
    send_confirmation_email(request, user)
    return True
