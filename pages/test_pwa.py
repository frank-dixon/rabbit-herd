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
        self.assertEqual({icon["sizes"] for icon in data["icons"]}, {"any", "192x192", "512x512"})
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


class IconAndSplashTests(TestCase):
    def test_launch_screens_exist_for_light_and_dark(self):
        user = get_user_model().objects.create_user(email="s@example.com", password="x-strong-Pass-1")
        self.client.force_login(user)
        html = self.client.get("/").content.decode()
        import re
        hrefs = re.findall(r'rel="apple-touch-startup-image" media="[^"]*prefers-color-scheme: (light|dark)\)" href="/static/([^"]+)"', html)
        self.assertGreaterEqual(len(hrefs), 16)
        self.assertEqual({mode for mode, _ in hrefs}, {"light", "dark"})
        for _, path in hrefs:
            self.assertTrue(finders.find(path.removeprefix("static/")), path)
        self.assertIn('rel="icon" type="image/svg+xml"', html)

    def test_manifest_background_matches_c1_canvas(self):
        data = self.client.get("/manifest.webmanifest").json()
        self.assertEqual(data["background_color"], "#F5F6F5")
        self.assertEqual(data["theme_color"], "#F5F6F5")
