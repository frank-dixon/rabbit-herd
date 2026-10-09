from email.policy import SMTP

from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_confirmation_token

# The default email policy folds lines at 78 characters, which splits a
# confirmation link in the console. 998 is the SMTP limit, long enough for
# the link to stay on one line.
_PLAIN_POLICY = SMTP.clone(max_line_length=998)


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


def send_confirmation_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_confirmation_token.make_token(user)
    url = request.build_absolute_uri(
        reverse("confirm_email", kwargs={"uidb64": uid, "token": token})
    )
    send_account_mail(
        "Confirm your Rabbit Herd account",
        (
            "Confirm your email to finish creating your Rabbit Herd account.\n\n"
            f"{url}\n"
        ),
        user.email,
    )
