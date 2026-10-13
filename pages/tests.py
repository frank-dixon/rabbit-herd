import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase, TestCase

ROOT = Path(__file__).resolve().parents[1]


def load_settings(extra):
    env = os.environ.copy()
    for key in (
        "APP_HOSTNAME",
        "RENDER_EXTERNAL_HOSTNAME",
        "VERCEL_URL",
        "VERCEL_PROJECT_PRODUCTION_URL",
        "WEBAUTHN_RP_ID",
        "WEBAUTHN_ORIGIN",
        "WEBAUTHN_RP_NAME",
        "ALLOWED_HOSTS",
        "CSRF_TRUSTED_ORIGINS",
        "DATABASE_URL",
        "SECRET_KEY_FALLBACKS",
    ):
        env.pop(key, None)
    env.update(extra)
    env["DJANGO_SETTINGS_MODULE"] = "rabbit_herd.settings"
    script = """
import django
django.setup()
from django.conf import settings
print("|".join(settings.ALLOWED_HOSTS))
print("|".join(settings.CSRF_TRUSTED_ORIGINS))
print(settings.WEBAUTHN_RP_ID)
print(settings.WEBAUTHN_ORIGIN)
print("|".join(settings.SECRET_KEY_FALLBACKS))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    allowed, origins, rp_id, origin, fallbacks = result.stdout.splitlines()
    return {
        "allowed": allowed.split("|") if allowed else [],
        "origins": origins.split("|") if origins else [],
        "rp_id": rp_id,
        "origin": origin,
        "fallbacks": fallbacks.split("|") if fallbacks else [],
    }


class HostnameSettingsTests(SimpleTestCase):
    def test_app_hostname_configures_hosts_csrf_and_webauthn(self):
        settings = load_settings(
            {
                "DEBUG": "false",
                "SECRET_KEY": "prod-check-" + ("a1b2c3d4" * 8),
                "APP_HOSTNAME": "herd.example",
            }
        )

        self.assertIn("herd.example", settings["allowed"])
        self.assertIn("https://herd.example", settings["origins"])
        self.assertEqual(settings["rp_id"], "herd.example")
        self.assertEqual(settings["origin"], "https://herd.example")

    def test_app_hostname_is_the_passkey_host_when_render_is_also_set(self):
        settings = load_settings(
            {
                "DEBUG": "false",
                "SECRET_KEY": "prod-check-" + ("a1b2c3d4" * 8),
                "APP_HOSTNAME": "app.example",
                "RENDER_EXTERNAL_HOSTNAME": "render.example",
            }
        )

        self.assertIn("app.example", settings["allowed"])
        self.assertIn("render.example", settings["allowed"])
        self.assertIn("https://app.example", settings["origins"])
        self.assertIn("https://render.example", settings["origins"])
        self.assertEqual(settings["rp_id"], "app.example")
        self.assertEqual(settings["origin"], "https://app.example")

    def test_vercel_production_url_is_the_passkey_host(self):
        settings = load_settings(
            {
                "DEBUG": "false",
                "SECRET_KEY": "prod-check-" + ("a1b2c3d4" * 8),
                "VERCEL_PROJECT_PRODUCTION_URL": "herd.vercel.app",
                "VERCEL_URL": "herd-git-main-frank.vercel.app",
            }
        )

        self.assertIn("herd.vercel.app", settings["allowed"])
        self.assertIn("herd-git-main-frank.vercel.app", settings["allowed"])
        self.assertIn("https://herd.vercel.app", settings["origins"])
        self.assertIn("https://herd-git-main-frank.vercel.app", settings["origins"])
        self.assertEqual(settings["rp_id"], "herd.vercel.app")
        self.assertEqual(settings["origin"], "https://herd.vercel.app")

    def test_app_hostname_is_the_passkey_host_when_vercel_is_also_set(self):
        settings = load_settings(
            {
                "DEBUG": "false",
                "SECRET_KEY": "prod-check-" + ("a1b2c3d4" * 8),
                "APP_HOSTNAME": "herd.example",
                "VERCEL_PROJECT_PRODUCTION_URL": "herd.vercel.app",
                "VERCEL_URL": "herd-abc123.vercel.app",
                "RENDER_EXTERNAL_HOSTNAME": "render.example",
            }
        )

        self.assertEqual(
            settings["allowed"],
            [
                "herd.example",
                "herd.vercel.app",
                "render.example",
                "herd-abc123.vercel.app",
            ],
        )
        self.assertEqual(settings["rp_id"], "herd.example")
        self.assertEqual(settings["origin"], "https://herd.example")

    def test_vercel_url_configures_passkeys_when_it_is_the_only_host(self):
        settings = load_settings(
            {
                "DEBUG": "false",
                "SECRET_KEY": "prod-check-" + ("a1b2c3d4" * 8),
                "VERCEL_URL": "https://herd-abc123.vercel.app/ignored",
            }
        )

        self.assertEqual(settings["allowed"], ["herd-abc123.vercel.app"])
        self.assertEqual(settings["origins"], ["https://herd-abc123.vercel.app"])
        self.assertEqual(settings["rp_id"], "herd-abc123.vercel.app")
        self.assertEqual(settings["origin"], "https://herd-abc123.vercel.app")

    def test_secret_key_fallbacks_are_split_from_the_environment(self):
        settings = load_settings(
            {
                "DEBUG": "false",
                "SECRET_KEY": "current-secret",
                "SECRET_KEY_FALLBACKS": "old-secret, older-secret,",
                "APP_HOSTNAME": "herd.example",
            }
        )

        self.assertEqual(settings["fallbacks"], ["old-secret", "older-secret"])


class LandingPageTests(TestCase):
    def test_signed_out_visitor_sees_the_landing_page(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bramble Burrow")
        self.assertContains(response, "Private records for your rabbitry")
