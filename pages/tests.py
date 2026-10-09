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
        "WEBAUTHN_RP_ID",
        "WEBAUTHN_ORIGIN",
        "WEBAUTHN_RP_NAME",
        "ALLOWED_HOSTS",
        "CSRF_TRUSTED_ORIGINS",
        "DATABASE_URL",
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
    allowed, origins, rp_id, origin = result.stdout.splitlines()
    return {
        "allowed": allowed.split("|") if allowed else [],
        "origins": origins.split("|") if origins else [],
        "rp_id": rp_id,
        "origin": origin,
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


class LandingPageTests(TestCase):
    def test_signed_out_visitor_sees_the_landing_page(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rabbit Herd")
        self.assertContains(response, "private record keeper")
