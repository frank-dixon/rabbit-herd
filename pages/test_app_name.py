from django.test import TestCase, override_settings
from django.urls import reverse


class AppNameTests(TestCase):
    def test_pages_use_bramble_burrow(self):
        page = self.client.get(reverse("login")).content.decode()
        self.assertIn("Bramble Burrow</title>", page)
        self.assertIn(">Bramble Burrow</a>", page)
        self.assertNotIn("Rabbit Herd", page)

    @override_settings(APP_NAME="Test Name")
    def test_the_name_comes_from_one_setting(self):
        self.assertContains(self.client.get(reverse("login")), "Sign in · Test Name</title>", html=False)
