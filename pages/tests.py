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
            }
        )

        self.assertEqual(
            settings["allowed"],
            [
                "herd.example",
                "herd.vercel.app",
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
        self.assertContains(response, "Run your rabbitry from one place.")
        self.assertContains(response, 'href="/login/"')
        # Frank, 2026-10-18: Welcome offers the demo / own-herd choice itself (/start/ stays as an alias).
        from django.urls import reverse
        self.assertContains(response, f'action="{reverse("guest")}"')
        self.assertContains(response, "Start my own herd")
        # G7: one way in for returning users, the header "Sign in"; no inline "I have an account".
        self.assertContains(response, 'class="si" href="/login/">Sign in</a>')
        self.assertNotContains(response, "I have an account")

    def test_welcome_follows_dark_mode_with_the_app_dark_tokens(self):
        # Critic v6 W2: Welcome uses Evergreen night (dark-a) when the system is dark.
        response = self.client.get("/")
        self.assertContains(response, '<meta name="theme-color" content="#0F1512" media="(prefers-color-scheme: dark)">')
        css = (ROOT / "static" / "marketing" / "home.css").read_text()
        dark = css[css.index("@media (prefers-color-scheme: dark)"):]
        themes = (ROOT / "assets" / "themes.css").read_text()
        tokens = themes[themes.index('html[data-theme="dark-a"]'):]
        tokens = tokens[:tokens.index("}")]
        for name in ("--canvas", "--surface", "--ink", "--ink-2", "--accent", "--on-accent", "--field"):
            value = tokens.split(name + ":", 1)[1].split(";", 1)[0].strip()
            self.assertIn(value, dark, name)

    def test_welcome_previews_have_dark_screenshots(self):
        # Critic v6 W2: the app preview and feature screenshots switch to the dark app too (scripts/marketing_shots.py --theme dark-a).
        body = self.client.get("/").content.decode()
        for name in ("hero-390", "hero-1280", "tree", "weights", "litters", "pairing", "rabbit"):
            self.assertIn(f"marketing/{name}-dark-1x.webp", body)
            self.assertTrue((ROOT / "static" / "marketing" / f"{name}-dark.webp").exists(), name)
        self.assertEqual(body.count('<source media="(prefers-color-scheme: dark)"') + body.count('and (prefers-color-scheme: dark)"'), 7)

    def test_welcome_quiets_its_page_transitions(self):
        # /start/ now lands here (Critic v6 M7), so Welcome handles an aborted page transition itself.
        self.assertContains(self.client.get("/"), '<script src="/static/marketing/home.js"></script>')
        js = (ROOT / "static" / "marketing" / "home.js").read_text()
        self.assertIn('addEventListener("pageswap"', js)
        self.assertIn('addEventListener("pagereveal"', js)

    def test_signed_in_user_gets_the_app_at_root(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(email="m@example.com", password="x-Long-pass-123")
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertNotContains(response, "Run your rabbitry from one place.")
        self.assertContains(response, "Today")
