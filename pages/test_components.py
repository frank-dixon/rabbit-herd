from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import User


class ButtonPartialTests(SimpleTestCase):
    def test_variants_render_as_buttons_and_links(self):
        primary = render_to_string(
            "components/button.html",
            {"label": "Save", "type": "submit", "variant": "primary"},
        )
        danger = render_to_string(
            "components/button.html",
            {"label": "Remove", "variant": "danger"},
        )
        link = render_to_string(
            "components/button.html",
            {"label": "Back", "href": "/back/", "variant": "secondary", "disabled": True},
        )

        self.assertIn("<button", primary)
        self.assertIn('type="submit"', primary)
        self.assertIn("bg-neutral-800", primary)
        self.assertIn("<button", danger)
        self.assertIn("bg-red-800", danger)
        self.assertIn("<a", link)
        self.assertNotIn("<button", link)
        self.assertIn('href="/back/"', link)
        self.assertIn('aria-disabled="true"', link)
        self.assertIn("opacity-50", link)

    def test_disabled_button_cannot_submit(self):
        html = render_to_string(
            "components/button.html",
            {"label": "Save", "type": "submit", "disabled": True},
        )

        self.assertIn("disabled", html)
        self.assertNotIn("<a", html)


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
