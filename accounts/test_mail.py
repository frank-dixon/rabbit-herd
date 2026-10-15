from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from rabbit_herd.email_config import (
    CONSOLE_BACKEND,
    RESEND_BACKEND,
    SMTP_BACKEND,
    default_from_email,
    email_settings,
)


class EmailConfigTests(SimpleTestCase):
    def test_console_is_the_default(self):
        chosen = email_settings({})

        self.assertEqual(chosen["EMAIL_BACKEND"], CONSOLE_BACKEND)
        self.assertNotIn("ANYMAIL", chosen)

    def test_console_provider_ignores_an_smtp_host(self):
        chosen = email_settings(
            {"EMAIL_PROVIDER": "console", "EMAIL_HOST": "smtp.example.com"}
        )

        self.assertEqual(chosen["EMAIL_BACKEND"], CONSOLE_BACKEND)

    def test_smtp_is_used_when_a_host_is_set(self):
        chosen = email_settings(
            {
                "EMAIL_HOST": "smtp.example.com",
                "EMAIL_PORT": "2525",
                "EMAIL_HOST_USER": "mailer",
                "EMAIL_HOST_PASSWORD": "smtp-secret",
                "EMAIL_USE_TLS": "false",
            }
        )

        self.assertEqual(chosen["EMAIL_BACKEND"], SMTP_BACKEND)
        self.assertEqual(chosen["EMAIL_HOST"], "smtp.example.com")
        self.assertEqual(chosen["EMAIL_PORT"], 2525)
        self.assertEqual(chosen["EMAIL_HOST_USER"], "mailer")
        self.assertEqual(chosen["EMAIL_HOST_PASSWORD"], "smtp-secret")
        self.assertFalse(chosen["EMAIL_USE_TLS"])
        self.assertFalse(chosen["EMAIL_USE_SSL"])

    def test_smtp_provider_requires_a_host(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "EMAIL_HOST"):
            email_settings({"EMAIL_PROVIDER": "smtp"})

    def test_resend_uses_the_api_key(self):
        chosen = email_settings(
            {
                "EMAIL_PROVIDER": "resend",
                "RESEND_API_KEY": "test-key",
                "DEFAULT_FROM_EMAIL": "Bramble Burrow <onboarding@resend.dev>",
                "EMAIL_HOST": "smtp.example.com",
            }
        )

        self.assertEqual(chosen["EMAIL_BACKEND"], RESEND_BACKEND)
        self.assertEqual(chosen["ANYMAIL"], {"RESEND_API_KEY": "test-key"})
        self.assertNotIn("EMAIL_HOST", chosen)

    def test_resend_requires_a_key(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "RESEND_API_KEY"):
            email_settings(
                {
                    "EMAIL_PROVIDER": "resend",
                    "DEFAULT_FROM_EMAIL": "Bramble Burrow <onboarding@resend.dev>",
                }
            )

    def test_a_resend_key_alone_picks_resend(self):
        self.assertEqual(email_settings({"RESEND_API_KEY": "test-key"})["EMAIL_BACKEND"], RESEND_BACKEND)

    def test_from_address(self):
        self.assertEqual(default_from_email({"RESEND_API_KEY": "k"}, "BB"), "BB <onboarding@resend.dev>")
        self.assertEqual(default_from_email({"RESEND_API_KEY": "k", "DEFAULT_FROM_EMAIL": "BB <hi@x.app>"}, "BB"), "BB <hi@x.app>")
        self.assertEqual(default_from_email({}, "BB"), "BB <noreply@localhost>")
        self.assertEqual(email_settings({})["EMAIL_BACKEND"], CONSOLE_BACKEND)


class SendTestEmailCommandTests(SimpleTestCase):
    def test_sends_one_mail(self):
        from io import StringIO
        from django.core import mail
        from django.core.management import call_command
        out = StringIO()
        call_command("send_test_email", "frank@example.com", stdout=out)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["frank@example.com"])
        self.assertIn("Sent", out.getvalue())

    def test_an_unknown_provider_is_rejected(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "EMAIL_PROVIDER"):
            email_settings({"EMAIL_PROVIDER": "carrier-pigeon"})
