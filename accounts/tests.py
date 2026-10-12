import json
import re
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

User = get_user_model()
PASSWORD = "Rabbit-Herd-Pass-1"
NEW_PASSWORD = "Rabbit-Herd-Pass-2"


def make_user(email="frank@example.com", password=PASSWORD, **extra):
    user = User.objects.create_user(email=email, password=password, **extra)
    user.is_active = True
    user.email_confirmed = True
    user.email_confirmed_at = timezone.now()
    user.save()
    return user


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordAccountTests(TestCase):
    def test_signup_sends_a_confirmation_email_and_then_signs_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "email": "Frank@Example.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("signup_done"))
        user = User.objects.get()
        self.assertEqual(user.email, "frank@example.com")
        self.assertFalse(user.is_active)
        self.assertFalse(user.email_confirmed)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["frank@example.com"])
        self.assertIn("Confirm your email", mail.outbox[0].body)

        blocked = self.client.post(
            reverse("login"),
            {"username": "frank@example.com", "password": PASSWORD},
        )
        self.assertContains(blocked, "Confirm your email before signing in.")

        path = re.search(r"http://testserver(\S+)", mail.outbox[0].body).group(1)
        confirmed = self.client.get(path)
        self.assertRedirects(confirmed, reverse("index"))
        home = self.client.get(reverse("index"))
        self.assertContains(home, "Activity</h1>")
        self.assertContains(self.client.get(reverse("account")), "frank@example.com")
        user.refresh_from_db()
        self.assertTrue(user.email_confirmed)
        self.assertTrue(user.is_active)

        self.client.post(reverse("logout"))
        reused = self.client.get(path)
        self.assertEqual(reused.status_code, 400)

    @override_settings(
        APP_HOSTNAME="rabbit-herd.vercel.app",
        DEFAULT_FROM_EMAIL="Rabbit Herd <onboarding@resend.dev>",
    )
    def test_confirmation_link_uses_the_https_app_host(self):
        response = self.client.post(
            reverse("signup"),
            {
                "email": "frank@example.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("signup_done"))
        message = mail.outbox[0]
        self.assertEqual(message.from_email, "Rabbit Herd <onboarding@resend.dev>")
        self.assertEqual(message.to, ["frank@example.com"])
        self.assertIn(
            "https://rabbit-herd.vercel.app/accounts/confirm/",
            message.body,
        )
        self.assertNotIn("http://testserver", message.body)

    def test_password_login_and_logout(self):
        make_user()

        response = self.client.post(
            reverse("login"),
            {"username": "frank@example.com", "password": PASSWORD},
        )

        self.assertRedirects(response, reverse("index"))
        self.assertContains(self.client.get(reverse("index")), "Activity</h1>")

        logged_out = self.client.post(reverse("logout"))
        self.assertRedirects(logged_out, reverse("index"))
        self.assertContains(self.client.get(reverse("index")), "Sign in")

    def test_login_rejects_an_open_redirect(self):
        make_user()

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
        make_user()

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
        make_user()
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            reverse("login"),
            {"username": "frank@example.com", "password": PASSWORD},
        )

        self.assertEqual(response.status_code, 403)

    def test_wrong_password_does_not_sign_in(self):
        make_user()

        response = self.client.post(
            reverse("login"),
            {"username": "frank@example.com", "password": "not-the-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email or password is incorrect.")
        self.assertNotContains(self.client.get(reverse("index")), "Activity</h1>")


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
        self.assertEqual(body["rp"]["id"], settings.WEBAUTHN_RP_ID)
        self.assertEqual(body["user"]["name"], "frank@example.com")
        selection = body["authenticatorSelection"]
        self.assertEqual(selection["authenticatorAttachment"], "platform")
        self.assertEqual(selection["residentKey"], "required")
        self.assertIs(selection["requireResidentKey"], True)
        self.assertEqual(selection["userVerification"], "required")
        self.assertEqual(body["attestation"], "none")
        self.assertEqual(
            [item["alg"] for item in body["pubKeyCredParams"]],
            [-7, -257],
        )
        self.assertIn("webauthn_register_challenge", self.client.session)

    def test_register_options_reject_a_duplicate_email(self):
        make_user()

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
        body = response.json()
        self.assertTrue(body["challenge"])
        self.assertEqual(body["rpId"], settings.WEBAUTHN_RP_ID)
        self.assertEqual(body["userVerification"], "required")
        self.assertNotIn("allowCredentials", body)
        self.assertIn("webauthn_auth_challenge", self.client.session)

    def test_login_page_offers_a_saved_passkey_in_the_email_field(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, 'autocomplete="username webauthn"')
        self.assertContains(response, 'id="passkey-login"')

    def test_verify_rejects_a_ceremony_that_never_started(self):
        response = self.client.post(
            reverse("passkey_login_verify"),
            data=json.dumps({"credential": {"id": "nope", "rawId": "nope"}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_signed_in_user_can_start_adding_a_passkey(self):
        user = make_user()
        self.client.force_login(user)

        response = self.client.post(
            reverse("passkey_register_options"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["name"], "frank@example.com")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountManagementTests(TestCase):
    def test_password_change(self):
        user = make_user()
        self.client.force_login(user)

        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": PASSWORD,
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("password_change_done"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PASSWORD))
        self.assertContains(self.client.get(reverse("index")), "Activity</h1>")

    def test_password_reset(self):
        user = make_user()

        response = self.client.post(reverse("password_reset"), {"email": user.email})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        path = re.search(r"http://testserver(\S+)", mail.outbox[0].body).group(1)
        form_page = self.client.get(path, follow=True)
        self.assertContains(form_page, "Choose a new password")
        posted = self.client.post(
            form_page.request["PATH_INFO"],
            {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
        )
        self.assertRedirects(posted, reverse("password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PASSWORD))

    @override_settings(APP_HOSTNAME="rabbit-herd.vercel.app")
    def test_password_reset_link_uses_the_https_app_host(self):
        user = make_user()

        response = self.client.post(reverse("password_reset"), {"email": user.email})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "https://rabbit-herd.vercel.app/accounts/password/reset/",
            mail.outbox[0].body,
        )
        self.assertNotIn("http://testserver", mail.outbox[0].body)

    def test_password_reset_skips_unconfirmed_accounts(self):
        User.objects.create_user(
            email="frank@example.com",
            password=PASSWORD,
            is_active=False,
        )

        self.client.post(reverse("password_reset"), {"email": "frank@example.com"})

        self.assertEqual(len(mail.outbox), 0)

    def test_guest_mode(self):
        response = self.client.post(reverse("guest"))

        self.assertRedirects(response, reverse("index"))
        home = self.client.get(reverse("index"))
        self.assertContains(home, "Activity</h1>")
        self.assertContains(self.client.get(reverse("account")), "guest session")
        user = User.objects.get()
        self.assertTrue(user.is_guest)
        self.assertFalse(user.has_usable_password())
        change = self.client.get(reverse("password_change"))
        self.assertRedirects(change, reverse("index"))

    def test_ensure_demo_user_can_log_in_and_is_safe_to_repeat(self):
        with patch.dict(
            "os.environ",
            {"DEMO_EMAIL": "demo@example.com", "DEMO_PASSWORD": PASSWORD},
        ):
            call_command("ensure_demo_user")
            call_command("ensure_demo_user")

        self.assertEqual(User.objects.filter(email="demo@example.com").count(), 1)
        user = User.objects.get(email="demo@example.com")
        self.assertTrue(user.email_confirmed)
        self.assertTrue(user.is_active)
        response = self.client.post(
            reverse("login"),
            {"username": user.email, "password": PASSWORD},
        )
        self.assertRedirects(response, reverse("index"))
        self.assertContains(self.client.get(reverse("index")), "Activity</h1>")

    def test_account_mail_keeps_a_long_link_on_one_line(self):
        from accounts.emails import PlainEmailMessage

        url = "http://127.0.0.1:8000/accounts/password/reset/" + ("a" * 48) + "/"
        rendered = PlainEmailMessage(
            subject="Reset your Rabbit Herd password",
            body=f"Reset the password for your Rabbit Herd account:\n\n{url}\n",
            to=["frank@example.com"],
        ).message().as_string()

        self.assertIn(url, rendered)
        self.assertNotIn("quoted-printable", rendered)

    def test_ensure_demo_user_skips_when_unset(self):
        with patch.dict("os.environ", {"DEMO_EMAIL": "", "DEMO_PASSWORD": ""}):
            call_command("ensure_demo_user")

        self.assertEqual(User.objects.count(), 0)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RepeatSignupTests(TestCase):
    def signup(self, email="frank@example.com", password=PASSWORD):
        return self.client.post(
            reverse("signup"),
            {"email": email, "password1": password, "password2": password},
        )

    def test_repeat_signup_resends_the_link_for_an_unconfirmed_account(self):
        self.signup()
        user = User.objects.get()
        user.confirmation_sent_at = timezone.now() - timedelta(minutes=10)
        user.save(update_fields=["confirmation_sent_at"])
        mail.outbox.clear()

        response = self.signup(email="Frank@Example.com", password=NEW_PASSWORD)

        self.assertRedirects(response, reverse("signup_done"))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["frank@example.com"])
        self.assertIn("Confirm your email", mail.outbox[0].body)
        user.refresh_from_db()
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.check_password(NEW_PASSWORD))

        path = re.search(r"http://testserver(\S+)", mail.outbox[0].body).group(1)
        self.assertRedirects(self.client.get(path), reverse("index"))
        user.refresh_from_db()
        self.assertTrue(user.email_confirmed)

    def test_repeat_signup_is_rate_limited(self):
        self.signup()
        self.assertEqual(len(mail.outbox), 1)

        response = self.signup()

        self.assertRedirects(response, reverse("signup_done"))
        self.assertEqual(len(mail.outbox), 1)

        user = User.objects.get()
        user.confirmation_sent_at = timezone.now() - timedelta(minutes=6)
        user.save(update_fields=["confirmation_sent_at"])
        self.signup()
        self.assertEqual(len(mail.outbox), 2)

    def test_signup_with_a_confirmed_email_looks_the_same_and_sends_nothing(self):
        make_user()

        response = self.signup(password=NEW_PASSWORD)

        self.assertRedirects(response, reverse("signup_done"))
        self.assertEqual(len(mail.outbox), 0)
        user = User.objects.get()
        self.assertTrue(user.check_password(PASSWORD))

    def test_unknown_and_known_emails_get_the_same_page(self):
        make_user()
        known = self.client.post(
            reverse("signup"),
            {"email": "frank@example.com", "password1": PASSWORD, "password2": PASSWORD},
            follow=True,
        )
        unknown = self.client.post(
            reverse("signup"),
            {"email": "new@example.com", "password1": PASSWORD, "password2": PASSWORD},
            follow=True,
        )
        self.assertEqual(known.redirect_chain, unknown.redirect_chain)
        self.assertContains(known, "Check your email")
        self.assertContains(unknown, "Check your email")
