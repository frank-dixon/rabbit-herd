import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from rabbits.models import Litter, Pairing, Rabbit


class SignInNextOwnershipTests(TestCase):
    """A `next` URL that names another account's record goes to that section's
    list instead of a 404 (the demo herd's /litters/431/ after signing in as
    yourself)."""

    def make_user(self, email):
        return get_user_model().objects.create_user(
            email=email, password="pw-12345678", is_active=True,
            email_confirmed=True, email_confirmed_at=timezone.now(),
        )

    def setUp(self):
        self.demo = self.make_user("demo@example.com")
        self.frank = self.make_user("frank@example.com")
        born = datetime.date(2025, 1, 1)
        doe = Rabbit.objects.create(owner=self.demo, name="Doe", sex="doe", breed="New Zealand", color="White", birth_date=born)
        buck = Rabbit.objects.create(owner=self.demo, name="Buck", sex="buck", breed="New Zealand", color="White", birth_date=born)
        pairing = Pairing.objects.create(owner=self.demo, doe=doe, buck=buck)
        self.litter = Litter.objects.create(owner=self.demo, pairing=pairing, bred_on=datetime.date(2026, 9, 1))
        self.doe = doe

    def sign_in(self, email, next_url):
        return self.client.post("/login/", {"username": email, "password": "pw-12345678", "next": next_url})

    def test_another_accounts_litter_goes_to_the_litters_list(self):
        response = self.sign_in("frank@example.com", f"/litters/{self.litter.pk}/")
        self.assertRedirects(response, "/litters/", fetch_redirect_response=False)

    def test_another_accounts_rabbit_goes_to_the_rabbits_list(self):
        response = self.sign_in("frank@example.com", f"/rabbits/{self.doe.pk}/pedigree/")
        self.assertRedirects(response, "/rabbits/", fetch_redirect_response=False)

    def test_own_litter_is_kept(self):
        response = self.sign_in("demo@example.com", f"/litters/{self.litter.pk}/")
        self.assertRedirects(response, f"/litters/{self.litter.pk}/", fetch_redirect_response=False)

    def test_missing_litter_goes_to_the_list(self):
        response = self.sign_in("demo@example.com", "/litters/999999/")
        self.assertRedirects(response, "/litters/", fetch_redirect_response=False)

    def test_other_next_values_are_unchanged(self):
        response = self.sign_in("frank@example.com", "/weights/?range=all")
        self.assertRedirects(response, "/weights/?range=all", fetch_redirect_response=False)
