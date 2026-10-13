import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import BreedingSchedule, Breed, Litter, Pairing, Rabbit
from .test_contacts import user


class ScheduleTests(TestCase):
    def setUp(self):
        self.owner = user("sched@example.com")
        self.client.force_login(self.owner)
        rex = Breed.objects.get(name="Rex")
        mk = lambda name, sex: Rabbit.objects.create(owner=self.owner, name=name, sex=sex, breed="Rex", breed_type="purebred",
                                                     purebred=rex, color="Black", birth_date=datetime.date(2024, 1, 1))
        self.doe, self.buck = mk("Hazel", "doe"), mk("Basil", "buck")
        self.pairing = Pairing.objects.create(owner=self.owner, doe=self.doe, buck=self.buck)
        self.today = timezone.localdate()

    def add(self, name="Slow", **over):
        data = {"name": name, "gestation_days": 32, "palpate_day": 14, "nest_box_day": 27, "wean_age": 42,
                "process_age": 84, "rebreed_days": 56, **over}
        return self.client.post(reverse("schedule_add"), data)

    def start(self):
        self.client.post(reverse("litter_create", args=[self.pairing.pk]), {"bred_on": (self.today - datetime.timedelta(days=3)).isoformat()})
        return Litter.objects.latest("pk")

    def test_add_and_edit_share_one_form_and_new_starts_from_standard(self):
        page = self.client.get(reverse("schedule_add"))
        self.assertContains(page, 'value="31"')
        self.assertRedirects(self.add(), reverse("account") + "#schedule", fetch_redirect_response=False)
        slow = BreedingSchedule.objects.get(name="Slow")
        edit = self.client.get(reverse("schedule_edit", args=[slow.pk]))
        self.assertTemplateUsed(edit, "rabbits/schedule_form.html")
        self.assertContains(edit, "Move open litters")
        self.assertContains(self.client.get(reverse("account")), "Slow")

    def test_name_standard_and_duplicates_refused(self):
        self.assertEqual(self.add("standard").status_code, 400)
        self.add("Slow")
        self.assertEqual(self.add("slow").status_code, 400)
        self.assertEqual(self.add("Odd", nest_box_day=33).status_code, 400)

    def test_default_is_standard(self):
        litter = self.start()
        self.assertIsNone(litter.breeding_schedule)
        self.assertEqual(litter.schedule_name, "Standard")
        self.assertEqual(litter.due_on - litter.bred_on, datetime.timedelta(days=31))

    def test_doe_schedule_used_by_new_litters_and_old_ones_only_on_request(self):
        old = self.start()
        self.add()
        slow = BreedingSchedule.objects.get()
        self.client.post(reverse("doe_schedule", args=[self.doe.pk]), {"schedule": slow.pk})
        old.refresh_from_db()
        self.assertIsNone(old.breeding_schedule)
        new = self.start()
        self.assertEqual(new.breeding_schedule, slow)
        self.assertEqual(new.due_on - new.bred_on, datetime.timedelta(days=32))
        self.client.post(reverse("doe_schedule", args=[self.doe.pk]), {"schedule": slow.pk, "recalculate": "1"})
        old.refresh_from_db()
        self.assertEqual(old.breeding_schedule, slow)

    def test_pairing_override_beats_doe(self):
        self.add()
        slow = BreedingSchedule.objects.get()
        self.client.post(reverse("doe_schedule", args=[self.doe.pk]), {"schedule": slow.pk})
        self.client.post(reverse("pairing_schedule", args=[self.pairing.pk]), {"schedule": "standard"})
        self.assertIsNone(self.start().breeding_schedule)
        self.client.post(reverse("pairing_schedule", args=[self.pairing.pk]), {"schedule": "doe"})
        self.assertEqual(self.start().breeding_schedule, slow)
        page = self.client.get(reverse("pairing_detail", args=[self.pairing.pk]))
        self.assertContains(page, "Hazel&#x27;s schedule (Slow)")

    def test_weaned_litters_not_recalculated_and_delete_falls_back(self):
        self.add()
        slow = BreedingSchedule.objects.get()
        done = self.start()
        Litter.objects.filter(pk=done.pk).update(weaned=True)
        self.client.post(reverse("pairing_schedule", args=[self.pairing.pk]), {"schedule": slow.pk, "recalculate": "1"})
        done.refresh_from_db()
        self.assertIsNone(done.breeding_schedule)
        self.client.post(reverse("schedule_delete", args=[slow.pk]))
        self.pairing.refresh_from_db()
        self.assertIsNone(self.pairing.breeding_schedule)

    def test_other_keepers_schedule_refused(self):
        other = BreedingSchedule.objects.create(owner=user("x@example.com"), name="Theirs")
        self.client.post(reverse("doe_schedule", args=[self.doe.pk]), {"schedule": other.pk})
        self.doe.refresh_from_db()
        self.assertIsNone(self.doe.breeding_schedule)
        self.assertEqual(self.client.get(reverse("schedule_edit", args=[other.pk])).status_code, 404)
