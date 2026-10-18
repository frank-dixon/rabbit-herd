from unittest import mock

from django.core.cache import caches
from django.db import DatabaseError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts import ratelimit


class RateLimitTests(TestCase):
    def setUp(self):
        caches["ratelimit"].clear()

    def post(self, name, data=None, ip="203.0.113.5"):
        return self.client.post(reverse(name), data or {}, REMOTE_ADDR=ip)

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


class CacheTableTests(TestCase):
    """The test runner creates cache tables itself, so check the migration directly."""

    def test_migration_creates_the_configured_table(self):
        import importlib

        from django.conf import settings
        from django.db import connection

        table = settings.CACHES["ratelimit"]["LOCATION"]
        from types import SimpleNamespace

        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE {connection.ops.quote_name(table)}")
        self.assertNotIn(table, connection.introspection.table_names())
        mod = importlib.import_module("accounts.migrations.0019_ratelimit_cache_table_name")
        editor = SimpleNamespace(connection=connection)
        mod.create_table(None, editor)
        self.assertIn(table, connection.introspection.table_names())
        mod.create_table(None, editor)  # existing table: still a no-op
        caches["ratelimit"].set("probe", 1)
        self.assertEqual(caches["ratelimit"].get("probe"), 1)


class ClientIpTests(TestCase):
    def req(self, remote, xff=None):
        extra = {"REMOTE_ADDR": remote}
        if xff:
            extra["HTTP_X_FORWARDED_FOR"] = xff
        return RequestFactory().post("/login/", **extra)

    @override_settings(TRUST_VERCEL_FORWARDED=False, TRUSTED_PROXIES=[])
    def test_forwarded_header_is_ignored_without_a_trusted_proxy(self):
        self.assertEqual(ratelimit.client_ip(self.req("192.168.0.9", "1.2.3.4")), "192.168.0.9")

    @override_settings(TRUST_VERCEL_FORWARDED=False, TRUSTED_PROXIES=["127.0.0.1"])
    def test_trusted_proxy_uses_the_last_untrusted_hop(self):
        self.assertEqual(ratelimit.client_ip(self.req("127.0.0.1", "6.6.6.6, 203.0.113.7")), "203.0.113.7")
        self.assertEqual(ratelimit.client_ip(self.req("10.0.0.2", "6.6.6.6")), "10.0.0.2")

    @override_settings(TRUST_VERCEL_FORWARDED=True)
    def test_vercel_uses_the_first_entry(self):
        self.assertEqual(ratelimit.client_ip(self.req("10.0.0.1", "203.0.113.8, 10.0.0.1")), "203.0.113.8")
