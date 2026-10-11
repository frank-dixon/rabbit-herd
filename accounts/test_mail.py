from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from rabbit_herd.email_config import (
    CONSOLE_BACKEND,
    RESEND_BACKEND,
    SMTP_BACKEND,
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
                "DEFAULT_FROM_EMAIL": "Rabbit Herd <onboarding@resend.dev>",
                "EMAIL_HOST": "smtp.example.com",
            }
        )

        self.assertEqual(chosen["EMAIL_BACKEND"], RESEND_BACKEND)
        self.assertEqual(chosen["ANYMAIL"], {"RESEND_API_KEY": "test-key"})
        self.assertNotIn("EMAIL_HOST", chosen)

    def test_resend_requires_a_key_and_a_from_address(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "RESEND_API_KEY"):
            email_settings(
                {
                    "EMAIL_PROVIDER": "resend",
                    "DEFAULT_FROM_EMAIL": "Rabbit Herd <onboarding@resend.dev>",
                }
            )
        with self.assertRaisesMessage(ImproperlyConfigured, "DEFAULT_FROM_EMAIL"):
            email_settings({"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": "test-key"})

    def test_an_unknown_provider_is_rejected(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "EMAIL_PROVIDER"):
            email_settings({"EMAIL_PROVIDER": "carrier-pigeon"})
