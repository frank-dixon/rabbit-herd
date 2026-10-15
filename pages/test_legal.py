from django.test import TestCase, override_settings
from django.urls import reverse


class LegalPagesTests(TestCase):
    @override_settings(SUPPORT_EMAIL="help@example.com")
    def test_pages_are_public_and_name_the_contact(self):
        for name, heading in (("privacy", "Privacy policy"), ("terms", "Terms of use")):
            r = self.client.get(reverse(name))
            self.assertContains(r, heading)
            self.assertContains(r, "mailto:help@example.com")
            self.assertNotContains(r, "DRAFT")  # the draft note lives in a template comment only

    def test_linked_from_signup_and_marketing(self):
        for url in (reverse("signup"), reverse("index")):
            r = self.client.get(url)
            self.assertContains(r, reverse("privacy"))
            self.assertContains(r, reverse("terms"))
