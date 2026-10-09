import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()
PASSWORD = "Rabbit-Herd-Pass-1"


class PasswordAccountTests(TestCase):
    def test_signup_then_signed_in_page(self):
        response = self.client.post(
            reverse("signup"),
            {
                "email": "Frank@Example.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("index"))
        user = User.objects.get()
        self.assertEqual(user.email, "frank@example.com")
        home = self.client.get(reverse("index"))
        self.assertContains(home, "You're in.")
        self.assertContains(home, "frank@example.com")

    def test_password_login_and_logout(self):
        User.objects.create_user(email="frank@example.com", password=PASSWORD)

        response = self.client.post(
            reverse("login"),
            {"username": "frank@example.com", "password": PASSWORD},
        )

        self.assertRedirects(response, reverse("index"))
        self.assertContains(self.client.get(reverse("index")), "You're in.")

        logged_out = self.client.post(reverse("logout"))
        self.assertRedirects(logged_out, reverse("index"))
        self.assertContains(self.client.get(reverse("index")), "Sign in")

    def test_login_rejects_an_open_redirect(self):
        User.objects.create_user(email="frank@example.com", password=PASSWORD)

        response = self.client.post(
            reverse("login"),
            {
                "username": "frank@example.com",
                "password": PASSWORD,
                "next": "https://evil.example/phish",
            },
        )

        self.assertRedirects(response, reverse("index"))

    def test_login_allows_a_same_site_path(self):
        User.objects.create_user(email="frank@example.com", password=PASSWORD)

        response = self.client.post(
            reverse("login"),
            {
                "username": "frank@example.com",
                "password": PASSWORD,
                "next": "/accounts/login/",
            },
        )

        self.assertRedirects(
            response, "/accounts/login/", fetch_redirect_response=False
        )

    def test_login_form_requires_csrf(self):
        User.objects.create_user(email="frank@example.com", password=PASSWORD)
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            reverse("login"),
            {"username": "frank@example.com", "password": PASSWORD},
        )

        self.assertEqual(response.status_code, 403)

    def test_wrong_password_does_not_sign_in(self):
        User.objects.create_user(email="frank@example.com", password=PASSWORD)

        response = self.client.post(
            reverse("login"),
            {"username": "frank@example.com", "password": "not-the-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email or password is incorrect.")
        self.assertNotContains(self.client.get(reverse("index")), "You're in.")


class PasskeyEndpointTests(TestCase):
    def test_register_options_require_an_email(self):
        response = self.client.post(
            reverse("passkey_register_options"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["error"].lower())

    def test_register_options_issue_a_challenge(self):
        response = self.client.post(
            reverse("passkey_register_options"),
            data=json.dumps({"email": "frank@example.com"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["challenge"])
        self.assertEqual(body["rp"]["name"], "Rabbit Herd")
        self.assertEqual(body["user"]["name"], "frank@example.com")
        self.assertIn("webauthn_register_challenge", self.client.session)

    def test_register_options_reject_a_duplicate_email(self):
        User.objects.create_user(email="frank@example.com", password=PASSWORD)

        response = self.client.post(
            reverse("passkey_register_options"),
            data=json.dumps({"email": "frank@example.com"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_login_options_issue_a_challenge(self):
        response = self.client.post(
            reverse("passkey_login_options"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["challenge"])
        self.assertIn("webauthn_auth_challenge", self.client.session)

    def test_verify_rejects_a_ceremony_that_never_started(self):
        response = self.client.post(
            reverse("passkey_login_verify"),
            data=json.dumps({"credential": {"id": "nope", "rawId": "nope"}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_signed_in_user_can_start_adding_a_passkey(self):
        user = User.objects.create_user(email="frank@example.com", password=PASSWORD)
        self.client.force_login(user)

        response = self.client.post(
            reverse("passkey_register_options"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["name"], "frank@example.com")
