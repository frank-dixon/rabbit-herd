from django.test import TestCase
from django.urls import reverse

from .models import HerdSettings, prefs
from .test_contacts import user


class HerdSettingsPageTests(TestCase):
    def setUp(self):
        self.owner = user("settings@example.com")
        self.client.force_login(self.owner)

    def test_sections_show_on_settings_with_defaults(self):
        page = self.client.get(reverse("account"))
        for section in ("units", "schedule", "rabbitry", "reminders"):
            self.assertContains(page, f'data-settings-section="{section}"')
        self.assertContains(page, 'name="gestation_days"')
        self.assertContains(page, 'value="31"')
        self.assertFalse(HerdSettings.objects.exists())
        self.assertEqual(prefs(self.owner).wean_age, 28)

    def test_save_each_section(self):
        self.client.post(reverse("herd_settings_save", args=["units"]), {"weight_unit": "kg"})
        response = self.client.post(reverse("herd_settings_save", args=["schedule"]), {
            "gestation_days": 32, "palpate_day": 14, "nest_box_day": 27, "wean_age": 42,
            "process_age": 84, "rebreed_days": 35, "breeding_age_months": 7})
        self.assertRedirects(response, reverse("account") + "#schedule", fetch_redirect_response=False)
        self.client.post(reverse("herd_settings_save", args=["rabbitry"]),
                         {"rabbitry_name": "Bramble Hill", "prefix": "BH", "tattoo_format": "{prefix}{yy}{nn}"})
        self.client.post(reverse("herd_settings_save", args=["reminders"]),
                         {"remind_wean": "on", "daily_email": "on", "daily_email_time": "05:30"})
        saved = HerdSettings.objects.get(user=self.owner)
        self.assertEqual((saved.weight_unit, saved.gestation_days, saved.wean_age, saved.prefix),
                         ("kg", 32, 42, "BH"))
        self.assertTrue(saved.remind_wean and saved.daily_email)
        self.assertFalse(saved.remind_palpate)
        self.assertEqual(saved.daily_email_time.strftime("%H:%M"), "05:30")

    def test_invalid_values_explain(self):
        response = self.client.post(reverse("herd_settings_save", args=["schedule"]), {
            "gestation_days": 31, "palpate_day": 12, "nest_box_day": 33, "wean_age": 28,
            "process_age": 20, "rebreed_days": 42, "breeding_age_months": 6})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Enter a number from 24 to 31.", status_code=400)
        self.assertContains(response, "Enter a number from 42 to 200.", status_code=400)
        response = self.client.post(reverse("herd_settings_save", args=["rabbitry"]),
                                    {"tattoo_format": "{prefix}{month}"})
        self.assertContains(response, "Use only {prefix}", status_code=400)
        self.assertFalse(HerdSettings.objects.exists())

    def test_unknown_section_and_login(self):
        self.assertEqual(self.client.post(reverse("herd_settings_save", args=["nope"])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(reverse("herd_settings_save", args=["units"]), {"weight_unit": "kg"}).status_code, 302)
