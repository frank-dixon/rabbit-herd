"""Settings (Critic v2 item 7): one section at a time, and one save model, autosave with a
"Saved" status per section."""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

ROOT = Path(__file__).resolve().parents[1]


class SettingsSectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("settings@example.com", "pw-12345678")
        self.client.force_login(self.user)
        self.body = self.client.get(reverse("account")).content.decode()

    def test_one_section_shows_at_a_time(self):
        css = (ROOT / "assets" / "layout.css").read_text()
        block = css[css.index("Settings: one section at a time"):]
        self.assertIn(".settings-section:not(:has(:target)) { display: none; }", block)
        self.assertIn("[data-settings-panel]:not(:has(.settings-section :target)) { display: none; }", block)
        self.assertIn('id="settings-sections"', self.body)
        self.assertIn('href="#settings-sections"', self.body)  # All settings, back to the list on a phone

    def test_every_settings_form_autosaves_with_a_status(self):
        self.assertIn("Changes save automatically.", self.body)
        for section in ("rabbitry", "units", "schedule", "reminders"):
            form = self.body[self.body.index(f'id="{section}" method="post"'):]
            form = form[:form.index("</form>")]
            self.assertIn("data-autosave-status", form, section)
            self.assertIn("data-section-save", form, section)  # the no-JS Save
        tabs = self.body[self.body.index('id="tabs"'):]
        self.assertIn('data-autosave="tabs"', tabs[:tabs.index(">")])
        for status in ("data-appearance-status", "data-side-menu-status"):
            self.assertIn(status, self.body)

    def test_no_global_save_bar(self):
        js = (ROOT / "assets" / "settings-save.mjs").read_text()
        self.assertNotIn("save-bar", js)
        self.assertIn('export const SAVED = "Saved";', js)

    def test_a_repeated_tab_is_refused_with_the_final_wording(self):
        response = self.client.post(reverse("tab_bar"), {"tab": ["today", "today", "rabbits"]}, follow=True)
        self.assertIn("Choose 3 to 5 different tabs.", [str(m) for m in response.context["messages"]])
        self.assertIn('"Choose 3 to 5 different tabs."', (ROOT / "assets" / "settings-save.mjs").read_text())


class SamplesSwitchTests(TestCase):
    """Critic v6 W1: Show samples is a horizontal 44x24 switch with a 44px hit area."""

    def test_switch_is_horizontal_and_skips_the_submit_button_sizing(self):
        user = get_user_model().objects.create_user("switch@example.com", "pw-12345678")
        self.client.force_login(user)
        body = self.client.get(reverse("account")).content.decode()
        self.assertIn('role="switch" aria-checked="', body)
        css = (ROOT / "assets" / "components.css").read_text()
        rule = css[css.index(".switch {"):]
        rule = rule[:rule.index("}")]
        self.assertIn("width: 44px; height: 24px;", rule)
        self.assertIn("flex-shrink: 0", rule)
        self.assertIn('.switch::after { content: ""; position: absolute; inset: -10px 0; }', css)
        layout = (ROOT / "assets" / "layout.css").read_text()
        self.assertEqual(layout.count('main button[type="submit"]:not('), layout.count('[class*="underline"], .switch)'))
