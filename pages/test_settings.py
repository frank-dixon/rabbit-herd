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


class TabBarTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="tabs@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)

    def bar(self):
        html = self.client.get(reverse("rabbit_list")).content.decode()
        tabs = html[html.index("data-tab-list"):html.index("data-tab-tray")]
        import re
        return re.findall(r'data-tab="([a-z]+)"', tabs)

    def test_default_is_n1(self):
        self.assertEqual(self.bar(), ["today", "rabbits", "litters", "weights", "tasks"])

    def test_saving_from_the_bar_renders_server_side(self):
        response = self.client.post(reverse("tab_bar"), {"tab": ["tasks", "today", "pairings"]}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(response.json(), {"ok": True, "tabs": ["tasks", "today", "pairings"]})
        self.assertEqual(self.bar(), ["tasks", "today", "pairings"])

    def test_three_to_five_unique_known_tabs(self):
        for bad in (["today", "rabbits"], ["today", "today", "rabbits"], ["today", "rabbits", "nope"],
                    ["today", "rabbits", "litters", "weights", "tasks", "health"]):
            response = self.client.post(reverse("tab_bar"), {"tab": bad}, HTTP_X_REQUESTED_WITH="fetch")
            self.assertEqual(response.status_code, 400, bad)
        self.assertEqual(self.bar(), ["today", "rabbits", "litters", "weights", "tasks"])

    def test_settings_form_without_js_and_reset(self):
        page = self.client.get(reverse("account"))
        self.assertContains(page, 'aria-label="Tab 5"')
        response = self.client.post(reverse("tab_bar"), {"tab": ["rabbits", "health", "shows", "", ""]})
        self.assertRedirects(response, reverse("account") + "#tabs", fetch_redirect_response=False)
        self.assertEqual(self.bar(), ["rabbits", "health", "shows"])
        self.client.post(reverse("tab_bar"), {"reset": "1"})
        self.assertEqual(self.bar(), ["today", "rabbits", "litters", "weights", "tasks"])

    def test_bar_carries_the_destinations_for_edit_mode(self):
        page = self.client.get(reverse("rabbit_list"))
        self.assertContains(page, 'id="tab-destinations"')
        self.assertContains(page, "data-tab-tray hidden")


class UndoToastTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="undo@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)

    def test_archive_toast_offers_undo_that_restores(self):
        from rabbits.models import Rabbit
        rabbit = Rabbit.objects.create(owner=self.user, name="Fern", sex="doe", birth_date="2025-01-01")
        page = self.client.post(reverse("rabbit_archive", args=[rabbit.pk]), follow=True)
        self.assertContains(page, "Fern was archived.")
        self.assertContains(page, f'action="{reverse("rabbit_restore", args=[rabbit.pk])}" data-toast-undo')
        self.client.post(reverse("rabbit_restore", args=[rabbit.pk]))
        rabbit.refresh_from_db()
        self.assertIsNone(rabbit.archived_at)

    def test_task_done_toast_undo_puts_it_back(self):
        import datetime
        from rabbits.models import Task
        task = Task.objects.create(owner=self.user, title="Trim nails", due_on=datetime.date.today())
        page = self.client.post(reverse("task_done", args=[task.pk]), {"next": "/tasks/"}, follow=True)
        self.assertContains(page, f'action="{reverse("task_done", args=[task.pk])}" data-toast-undo')
        self.client.post(reverse("task_done", args=[task.pk]), {"next": "/tasks/"})
        task.refresh_from_db()
        self.assertIsNone(task.done_at)

    def test_removes_use_undo_not_confirm(self):
        from pathlib import Path
        from django.conf import settings
        for path in Path(settings.BASE_DIR, "templates").rglob("*.html"):
            text = path.read_text()
            if "data-confirm" in text:
                self.assertIn("Start over", text, path)


class FlatThemeTests(TestCase):
    def setUp(self):
        from accounts.models import User
        self.user = User.objects.create_user(email="flat@example.com", password=None)
        self.client.force_login(self.user)

    def test_d_themes_are_offered_saved_and_styled(self):
        from pathlib import Path
        from django.conf import settings as dj
        page = self.client.get(reverse("account"))
        for key, name in [("d1", "Charcoal &amp; Ink Blue"), ("d3", "Soft Gray &amp; Dusty Teal"), ("d6", "Fawn &amp; Sage")]:
            self.assertContains(page, name)
            self.client.post(reverse("account"), {"ui_theme": key, "ui_density": "roomy"})
            self.user.refresh_from_db()
            self.assertEqual(self.user.ui_theme, key)
            self.assertContains(self.client.get(reverse("account")), f'data-theme="{key}"')
        css = (Path(dj.BASE_DIR) / "assets" / "themes.css").read_text()
        for key in ("d1", "d2", "d3", "d4", "d5", "d6"):
            self.assertEqual(css.count(f'html[data-theme="{key}"]'), 2, key)
        self.assertIn("--canvas: #DEDEDC;", css)
        self.assertIn("--surface: #E9E9E7;", css)

    def test_c1_stays_the_default(self):
        from accounts.models import User
        self.assertEqual(User._meta.get_field("ui_theme").default, "c1")
