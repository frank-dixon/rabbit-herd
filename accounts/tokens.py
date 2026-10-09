from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailConfirmationTokenGenerator(PasswordResetTokenGenerator):
    """One-time token that stops working once the email is confirmed."""

    key_salt = "accounts.email-confirmation"

    def _make_hash_value(self, user, timestamp):
        return (
            f"{user.pk}{user.email}{user.password}"
            f"{user.email_confirmed}{user.is_active}{timestamp}"
        )


email_confirmation_token = EmailConfirmationTokenGenerator()
