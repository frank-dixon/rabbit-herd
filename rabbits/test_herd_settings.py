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


class UnitsAppliedTests(TestCase):
    def setUp(self):
        import datetime
        from .models import Rabbit, Weight
        self.owner = user("units@example.com")
        self.client.force_login(self.owner)
        self.rabbit = Rabbit.objects.create(owner=self.owner, name="Thistle", sex="doe", breed="Rex", color="Black",
                                            birth_date=datetime.date(2025, 1, 1))
        Weight.objects.create(rabbit=self.rabbit, date=datetime.date(2025, 6, 1), grams=1985, unit="lb")

    def test_pounds_by_default(self):
        page = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk]))
        self.assertContains(page, "4 lb 6 oz")
        self.assertContains(page, 'data-weight-unit="lb"')
        self.assertNotContains(page, 'name="kg"')

    def test_kilograms_when_chosen(self):
        HerdSettings.objects.create(user=self.owner, weight_unit="kg")
        page = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk]))
        self.assertContains(page, "1.98 kg")
        self.assertNotContains(page, "4 lb 6 oz")
        self.assertContains(page, 'name="kg"')
        self.assertNotContains(page, 'name="lb"')
        self.assertContains(self.client.get(reverse("export_csv", args=["weights"])), "1.98 kg")
        response = self.client.post(reverse("rabbit_weight_add", args=[self.rabbit.pk]),
                                    {"date": "2025-07-01", "kg": "2.2"}, follow=True)
        self.assertContains(response, "2.2 kg on Jul 1 was added")


class ScheduleAppliedTests(TestCase):
    def setUp(self):
        import datetime
        from django.utils import timezone
        from .models import Litter, Pairing, Rabbit
        self.owner = user("schedule@example.com")
        self.client.force_login(self.owner)
        today = timezone.localdate()
        mk = lambda name, sex, born: Rabbit.objects.create(owner=self.owner, name=name, sex=sex, breed="Rex",
                                                           color="Black", birth_date=born)
        self.doe = mk("Clover", "doe", today - datetime.timedelta(days=400))
        self.buck = mk("Sprout", "buck", today - datetime.timedelta(days=100))
        self.pairing = Pairing.objects.create(owner=self.owner, doe=self.doe, buck=self.buck)
        self.today = today
        self.litter = Litter.objects.create(owner=self.owner, pairing=self.pairing, bred_on=today)

    def test_litter_dates_follow_settings(self):
        import datetime
        HerdSettings.objects.create(user=self.owner, gestation_days=32, palpate_day=14, nest_box_day=27,
                                    wean_age=42, process_age=84, rebreed_days=35)
        from .models import Litter
        litter = Litter.objects.get(pk=self.litter.pk)
        tasks = {t["key"]: t for t in litter.tasks()}
        self.assertEqual(tasks["palpate"]["day"], 14)
        self.assertEqual(tasks["nest_box"]["day"], 27)
        self.assertEqual(litter.due_on, self.today + datetime.timedelta(days=32))
        litter.kindled_on = self.today
        tasks = {t["key"]: t for t in litter.tasks()}
        self.assertEqual(tasks["wean"]["date"], self.today + datetime.timedelta(days=42))
        self.assertEqual(tasks["process"]["age"], 84)
        self.assertEqual(tasks["rebreed"]["date"], self.today + datetime.timedelta(days=35))
        page = self.client.get(reverse("task_list"))
        self.assertContains(page, "Palpate: Clover (day 14)")

    def test_mark_rebred(self):
        self.litter.kindled_on = self.today
        self.litter.save()
        self.client.post(reverse("litter_task", args=[self.litter.pk]), {"task": "rebreed", "done": "1"})
        self.litter.refresh_from_db()
        self.assertTrue(self.litter.rebred)

    def test_young_rabbit_warning_uses_breeding_age(self):
        page = self.client.get(reverse("pairing_detail", args=[self.pairing.pk]))
        self.assertContains(page, "Sprout is 3 months old; your breeding age is 6 months.")
        self.assertNotContains(page, "Clover is")
        HerdSettings.objects.create(user=self.owner, breeding_age_months=3)
        self.assertNotContains(self.client.get(reverse("pairing_detail", args=[self.pairing.pk])), "data-age-warnings")
