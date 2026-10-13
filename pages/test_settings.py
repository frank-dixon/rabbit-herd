from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class SettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="set@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)

    def test_defaults_to_teal_and_coral_roomy_on_html(self):
        page = self.client.get(reverse("index"))
        self.assertContains(page, '<html lang="en" data-theme="c1" data-density="roomy">')

    def test_settings_lists_all_five_themes_with_swatches(self):
        page = self.client.get(reverse("account"))
        for label in ("Teal &amp; Coral", "Cobalt &amp; Saffron", "Forest &amp; Terracotta", "Plum &amp; Sage", "Red &amp; Slate"):
            self.assertContains(page, label)
        self.assertContains(page, "#0F5E63")
        self.assertContains(page, 'value="c1" checked')

    def test_saving_theme_and_density_applies_server_side(self):
        response = self.client.post(reverse("account"), {"ui_theme": "c4", "ui_density": "compact"})
        self.assertRedirects(response, reverse("account"))
        self.user.refresh_from_db()
        self.assertEqual((self.user.ui_theme, self.user.ui_density), ("c4", "compact"))
        page = self.client.get(reverse("rabbit_list"))
        self.assertContains(page, 'data-theme="c4" data-density="compact"')
        self.assertContains(page, '<meta name="theme-color" content="#F6F5F4" media="(prefers-color-scheme: light)">')

    def test_background_save_returns_no_content(self):
        response = self.client.post(reverse("account"), {"ui_theme": "c2", "ui_density": "roomy"}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(response.status_code, 204)
        self.user.refresh_from_db()
        self.assertEqual(self.user.ui_theme, "c2")

    def test_unknown_values_are_ignored(self):
        self.client.post(reverse("account"), {"ui_theme": "neon", "ui_density": "roomy"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.ui_theme, "c1")

    def test_old_account_url_redirects(self):
        self.assertRedirects(self.client.get("/account/"), reverse("account"))

    def test_logged_out_pages_use_the_default_theme(self):
        self.client.logout()
        self.assertContains(self.client.get(reverse("login")), 'data-theme="c1"')
