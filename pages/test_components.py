from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class PageShellTests(TestCase):
    def test_public_and_auth_pages_use_the_shell(self):
        for url in ("/", reverse("login"), reverse("signup")):
            response = self.client.get(url)
            self.assertContains(response, "<header")
            self.assertContains(response, "<main")
            self.assertContains(response, "<footer")
            self.assertContains(response, 'href="/"')

    def test_signed_in_page_uses_the_shell(self):
        user = User.objects.create_user(
            email="frank@example.com",
            password="Rabbit-Herd-Pass-1",
            is_active=True,
            email_confirmed=True,
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertContains(response, "You're in.")
        self.assertContains(response, "<header")
        self.assertContains(response, "<footer")
