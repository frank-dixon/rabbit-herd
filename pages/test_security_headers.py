import re

from django.contrib.auth import get_user_model
from django.test import TestCase

INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)(?![^>]*type=\"application/(?:json|ld\+json)\")[^>]*>", re.I)
INLINE_HANDLER = re.compile(r"<[^>]+\son[a-z]+=\"", re.I)


class SecurityHeaderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="h@example.com", password="x-strong-Pass-1")

    def test_strict_csp_and_friends_on_app_pages(self):
        r = self.client.get("/login/")
        csp = r["Content-Security-Policy"]
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("unsafe-inline' ; script", csp)
        self.assertNotRegex(csp.split("script-src")[1].split(";")[0], "unsafe")
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("publickey-credentials-get=(self)", r["Permissions-Policy"])
        self.assertEqual(r["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(r["Referrer-Policy"], "same-origin")
        self.assertIn("private", r["Cache-Control"])
        self.assertEqual(self.client_class().get("/")["Cache-Control"], "private, no-cache")

    def test_signed_in_html_is_never_stored(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/")["Cache-Control"], "private, no-store")

    def test_admin_gets_its_own_policy(self):
        r = self.client.get("/admin/login/")
        self.assertIn("'unsafe-eval'", r["Content-Security-Policy"])

    def test_no_inline_scripts_or_handlers_on_main_pages(self):
        self.client.force_login(self.user)
        for url in ["/", "/rabbits/", "/litters/", "/pairings/", "/tasks/", "/weights/", "/settings/",
                    "/health/", "/programs/", "/rabbits/new/", "/nope-404/"]:
            html = self.client.get(url, follow=True).content.decode()
            self.assertIsNone(INLINE_SCRIPT.search(html), url)
            self.assertIsNone(INLINE_HANDLER.search(html), url)
        self.client.logout()
        for url in ["/", "/login/", "/signup/"]:
            html = self.client.get(url).content.decode()
            self.assertIsNone(INLINE_SCRIPT.search(html), url)
