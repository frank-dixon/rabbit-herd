from unittest import mock

from django.core.cache import caches
from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse

from accounts import ratelimit


class RateLimitTests(TestCase):
    def setUp(self):
        caches["ratelimit"].clear()

    def post(self, name, data=None, ip="203.0.113.5"):
        return self.client.post(reverse(name), data or {}, HTTP_X_FORWARDED_FOR=ip)

    def test_login_per_account(self):
        for _ in range(10):
            self.assertNotEqual(self.post("login", {"username": "a@example.com", "password": "x"}).status_code, 429)
        r = self.post("login", {"username": "A@example.com ", "password": "x"}, ip="198.51.100.9")  # other IP, same account
        self.assertContains(r, "Too many sign-in attempts", status_code=429)
        self.assertContains(r, "Go to homepage", status_code=429)
        self.assertNotEqual(self.post("login", {"username": "b@example.com", "password": "x"}).status_code, 429)

    def test_login_per_ip(self):
        for i in range(30):
            self.post("login", {"username": f"u{i}@example.com", "password": "x"})
        self.assertEqual(self.post("login", {"username": "new@example.com", "password": "x"}).status_code, 429)
        self.assertNotEqual(self.post("login", {"username": "new@example.com", "password": "x"}, ip="198.51.100.1").status_code, 429)

    def test_guest_signup_reset_and_admin(self):
        for _ in range(10):
            self.post("guest")
            self.client.logout()
        self.assertContains(self.post("guest"), "guest sessions", status_code=429)
        for _ in range(3):
            self.post("password_reset", {"email": "c@example.com"})
        self.assertEqual(self.post("password_reset", {"email": "c@example.com"}).status_code, 429)
        for i in range(5):
            self.post("signup", {"email": "d@example.com", "password1": "x", "password2": "x"}, ip=f"192.0.2.{i}")
        self.assertEqual(self.post("signup", {"email": "d@example.com"}, ip="192.0.2.99").status_code, 429)
        for _ in range(5):
            self.post("admin:login", {"username": "boss@example.com", "password": "x"})
        self.assertEqual(self.post("admin:login", {"username": "boss@example.com", "password": "x"}).status_code, 429)

    def test_get_is_never_limited(self):
        for _ in range(40):
            self.client.get(reverse("login"))
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)

    def test_fails_open_when_the_table_is_missing(self):
        with mock.patch.object(ratelimit, "hit", side_effect=DatabaseError):
            for _ in range(40):
                self.assertNotEqual(self.post("guest").status_code, 429)
                self.client.logout()
