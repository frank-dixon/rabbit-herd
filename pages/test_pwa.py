from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase


class PwaTests(TestCase):
    def test_manifest_names_the_app_and_its_icons(self):
        response = self.client.get("/manifest.webmanifest")
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        data = response.json()
        self.assertEqual(data["name"], "Bramble Burrow")
        self.assertEqual(data["display"], "standalone")
        self.assertEqual({icon["sizes"] for icon in data["icons"]}, {"192x192", "512x512"})
        self.assertTrue(any(icon.get("purpose") == "maskable" for icon in data["icons"]))
        for icon in data["icons"]:
            self.assertTrue(finders.find(icon["src"].removeprefix("/static/")))

    def test_service_worker_is_served_from_the_root_and_skips_private_routes(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("no-cache", response["Cache-Control"])
        body = response.content.decode()
        self.assertIn('"/offline/"', body)
        self.assertIn("accounts|admin", body)
        self.assertIn("/static/css/app", body)

    def test_offline_page_and_head_links(self):
        self.assertContains(self.client.get("/offline/"), "You're offline")
        user = get_user_model().objects.create_user(email="p@example.com", password="x-strong-Pass-1")
        self.client.force_login(user)
        page = self.client.get("/")
        self.assertContains(page, 'rel="manifest" href="/manifest.webmanifest"')
        self.assertContains(page, "data-connection-status")
        self.assertContains(page, "apple-touch-icon")
