from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from rabbits.models import Contact, Litter, Pairing, PedigreeEntry, Rabbit, Task, Weight
from rabbits.samples import add_samples, clear_samples, sample_count, sample_models
from rabbits.samples.registry import EXEMPT_OWNER_MODELS, SAMPLE_OWNER_MODELS, owner_model_names


User = get_user_model()


class SampleRegistryTests(TestCase):
    def test_every_owner_model_is_listed(self):
        known = set(SAMPLE_OWNER_MODELS) | set(EXEMPT_OWNER_MODELS)
        # PasskeyCredential lives in accounts and uses user, not owner.
        found = [n for n in owner_model_names() if n != "PasskeyCredential"]
        self.assertEqual(set(found), known)


class SampleServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="s@example.com", password="x")
        self.today = date(2026, 10, 15)

    def test_add_is_idempotent_and_real_survives_clear(self):
        real = Rabbit.objects.create(
            owner=self.user, name="Clover", sex=Rabbit.Sex.DOE, breed="Californian",
            color="White", birth_date=self.today, status=Rabbit.Status.BREEDING)
        add_samples(self.user, "rabbits", today=self.today)
        add_samples(self.user, "rabbits", today=self.today)
        self.assertEqual(Rabbit.objects.filter(owner=self.user, is_sample=True).count(), 2)
        self.assertEqual(Rabbit.objects.filter(owner=self.user).real().count(), 1)
        add_samples(self.user, "litters", today=self.today)
        add_samples(self.user, "today", today=self.today)
        n = sample_count(self.user)
        self.assertGreater(n, 5)
        # Point the real rabbit at a sample location, then clear.
        loc = self.user.locations.filter(is_sample=True).get()
        real.location = loc
        real.save(update_fields=["location"])
        cleared = clear_samples(self.user)
        self.assertEqual(cleared, n)
        self.assertEqual(Rabbit.objects.filter(owner=self.user, is_sample=True).count(), 0)
        real.refresh_from_db()
        self.assertEqual(real.name, "Clover")
        self.assertIsNone(real.location_id)
        self.user.refresh_from_db()
        self.assertFalse(self.user.show_samples)

    def test_for_view_hides_when_off(self):
        add_samples(self.user, "rabbits", today=self.today)
        self.assertEqual(Rabbit.objects.filter(owner=self.user).for_view(self.user).count(), 2)
        self.user.show_samples = False
        self.assertEqual(Rabbit.objects.filter(owner=self.user).for_view(self.user).count(), 0)

    def test_sample_models_have_the_flag(self):
        for model in sample_models():
            self.assertTrue(hasattr(model, "is_sample"))
