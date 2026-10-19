"""Guest and demo herds (specs/guest-mode.md; Frank 2026-10-18).

Start my own herd: a guest that keeps its herd, saved in place on signup and
merged into an existing account on sign-in. See a demo herd: a private copy
of an admin-editable sample herd that can never be saved, signed up, merged
or converted, and is deleted a day after last use."""

import datetime
import os
import tempfile
from unittest import mock

from django.apps import apps
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts import demo, guest
from accounts.models import DemoBaseline, User
from rabbits.herd_ops import HERD_MODELS, has_herd_data
from rabbits.models import Litter, Location, Pairing, Rabbit, RabbitPhoto, Task, Weight

PASSWORD = "a-Long-test-pass-4417"
TODAY = timezone.localdate()


def rabbit(owner, name, sex, **extra):
    extra.setdefault("birth_date", TODAY - datetime.timedelta(days=400))
    return Rabbit.objects.create(owner=owner, name=name, sex=sex, breed="Rex", color="Black", **extra)


def make_baseline(as_of_days_ago=10):
    owner = User.objects.create_user(email="demo-baseline@demo.invalid", is_active=False)
    as_of = TODAY - datetime.timedelta(days=as_of_days_ago)
    loc = Location.objects.create(owner=owner, name="Cage D1")
    doe = rabbit(owner, "Hazel", "doe", tattoo="H1", location=loc, birth_date=as_of - datetime.timedelta(days=300))
    buck = rabbit(owner, "Alder", "buck", tattoo="A1", birth_date=as_of - datetime.timedelta(days=320))
    pairing = Pairing.objects.create(owner=owner, doe=doe, buck=buck)
    litter = Litter.objects.create(owner=owner, pairing=pairing, bred_on=as_of - datetime.timedelta(days=40),
                                   kindled_on=as_of - datetime.timedelta(days=9), born_alive=6)
    kit = rabbit(owner, "Hazel kit 1", "doe", birth_date=litter.kindled_on, litter=litter)
    Weight.objects.create(rabbit=doe, date=as_of, grams=4200)
    later = Task.objects.create(owner=owner, title="Wean", due_on=as_of + datetime.timedelta(days=20))
    Task.objects.create(owner=owner, title="Check nest", due_on=as_of, next_occurrence=later)
    name = default_storage.save(f"rabbit-photos/{owner.pk}/hazel.jpg", ContentFile(b"jpeg-bytes"))
    RabbitPhoto.objects.create(rabbit=doe, image=name, is_main=True)
    base = DemoBaseline.objects.create(owner=owner, as_of=as_of)
    return base, {"doe": doe, "kit": kit, "photo": name}


class MediaMixin:
    def setUp(self):
        super().setUp()
        self._media = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        self._media.enable()

    def tearDown(self):
        self._media.disable()
        super().tearDown()


class RegistryTests(TestCase):
    def test_every_herd_model_is_listed(self):
        """A new model that belongs to an account must be added to HERD_MODELS,
        or a merge would leave it behind and a demo copy would miss it."""
        listed = {name for name, _ in HERD_MODELS}
        for model in apps.get_app_config("rabbits").get_models():
            if model.__name__ == "Breed":  # shared reference data
                continue
            self.assertIn(model.__name__, listed, f"{model.__name__} is missing from rabbits.herd_ops.HERD_MODELS")


class FirstScreenTests(MediaMixin, TestCase):
    def test_offers_demo_and_own_herd_with_the_final_wording(self):
        make_baseline()
        for url in (reverse("index"),):  # right on Welcome (Frank, 2026-10-18); /start/ redirects there (Critic v6 M7)
            body = self.client.get(url).content.decode()
            self.assertIn("See a demo herd", body)
            self.assertIn("Look around with sample rabbits. Nothing is saved.", body)
            self.assertIn("Start my own herd", body)
            self.assertIn("Add your own rabbits. Saved on this device.", body)
            self.assertIn(f'action="{reverse("start_demo")}"', body)
            self.assertIn(f'action="{reverse("guest")}"', body)
            self.assertIn("csrfmiddlewaretoken", body)

    def test_welcome_choice_starts_a_guest_herd(self):
        page = self.client.get("/")
        self.assertNotIn("Start free", page.content.decode())
        response = self.client.post(reverse("guest"))
        self.assertRedirects(response, reverse("index"), fetch_redirect_response=False)

    def test_start_redirects_to_welcome(self):
        self.assertRedirects(self.client.get(reverse("start")), reverse("index"))

    def test_without_a_baseline_only_own_herd_is_offered(self):
        body = self.client.get(reverse("index")).content.decode()
        self.assertNotIn("See a demo herd", body)
        self.assertIn("Start my own herd", body)
        response = self.client.post(reverse("start_demo"), follow=True)
        self.assertContains(response, "The demo herd isn&#x27;t available right now. Try again soon.")

    def test_final_copy_strings(self):
        from pathlib import Path

        from django.conf import settings

        from accounts.ratelimit import MESSAGES
        from rabbits.sync import QUEUE_FAILED

        self.assertEqual(MESSAGES["demo"], "Too many demo herds started. Try again later.")  # the limit is per hour
        self.assertEqual(QUEUE_FAILED, "This change didn't sync. Open it and save again.")
        app_js = (Path(settings.BASE_DIR) / "assets" / "app.js").read_text()
        self.assertIn('"Passkey added. Use it next time you sign in."', app_js)
        page = self.client.get(reverse("pwa_offline"))
        self.assertContains(page, "<h1 class=\"text-[1.75rem] leading-tight font-semibold md:text-[2.25rem]\">You're offline</h1>")
        self.assertContains(page, "Pages you've already opened still work. Daily tasks save on this device and sync when you're back online. Photos need a connection.")


class DemoTests(MediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.base, self.rows = make_baseline(as_of_days_ago=10)

    def start(self):
        self.client.post(reverse("start_demo"))
        return User.objects.get(is_demo=True)

    def test_demo_is_a_private_copy_moved_to_today(self):
        user = self.start()
        mine = Rabbit.all_objects.filter(owner=user)
        self.assertEqual(mine.count(), 3)
        doe = mine.get(name="Hazel")
        self.assertNotEqual(doe.pk, self.rows["doe"].pk)
        self.assertEqual(doe.location.owner, user)
        self.assertEqual(Weight.objects.get(rabbit=doe).date, TODAY)  # as_of moved to today
        kit = mine.get(name="Hazel kit 1")
        self.assertEqual(kit.litter.owner, user)
        self.assertEqual(kit.litter.pairing.doe, doe)
        check = Task.objects.get(owner=user, title="Check nest")
        self.assertEqual(check.next_occurrence.owner, user)
        self.assertEqual(RabbitPhoto.objects.get(rabbit=doe).image.name, self.rows["photo"])
        # The baseline is untouched.
        self.assertEqual(Rabbit.all_objects.filter(owner=self.base.owner).count(), 3)

    def test_demo_shows_the_demo_rail_and_never_the_made_up_address(self):
        user = self.start()
        body = self.client.get(reverse("index")).content.decode()
        self.assertIn("This is a sample herd. It can&#x27;t be saved.", body)
        self.assertIn("Start my own herd", body)
        self.assertNotIn(user.email, body)

    def test_a_demo_herds_start_is_welcome(self):
        """Critic v7 O4: a demo herd's /start/ is Welcome, with both choices, not the old first screen."""
        self.start()
        response = self.client.get(reverse("start"))
        self.assertTemplateUsed(response, "marketing/home.html")
        self.assertTemplateNotUsed(response, "accounts/start.html")
        body = response.content.decode()
        self.assertIn(f'action="{reverse("start_demo")}"', body)
        self.assertIn(f'action="{reverse("guest")}"', body)

    def test_demo_cannot_be_merged(self):
        user = self.start()
        real = User.objects.create_user(email="keeper@example.com", password=PASSWORD, email_confirmed=True)
        with self.assertRaises(guest.CannotMerge):
            guest.merge_guest_into(user, real)

    def test_signing_in_from_a_demo_keeps_none_of_its_data(self):
        demo_user = self.start()
        real = User.objects.create_user(email="keeper@example.com", password=PASSWORD, email_confirmed=True)
        self.client.post(reverse("login"), {"username": "keeper@example.com", "password": PASSWORD})
        self.assertEqual(Rabbit.all_objects.filter(owner=real).count(), 0)
        self.assertFalse(User.objects.filter(pk=demo_user.pk).exists())

    def test_signing_up_from_a_demo_starts_fresh(self):
        demo_user = self.start()
        self.client.post(reverse("signup"), {"email": "new@example.com", "password1": PASSWORD})
        new = User.objects.get(email="new@example.com")
        self.assertFalse(new.is_demo)
        self.assertNotEqual(new.pk, demo_user.pk)
        self.assertEqual(Rabbit.all_objects.filter(owner=new, is_sample=False).count(), 0)
        self.assertFalse(User.objects.filter(pk=demo_user.pk).exists())

    def test_start_my_own_herd_from_a_demo_gives_an_empty_guest(self):
        demo_user = self.start()
        self.client.post(reverse("guest"))
        me = User.objects.get(pk=self.client.session["_auth_user_id"])
        self.assertTrue(me.is_guest)
        self.assertFalse(me.is_demo)
        self.assertFalse(has_herd_data(me))
        self.assertFalse(User.objects.filter(pk=demo_user.pk).exists())

    def test_demo_cannot_add_a_passkey(self):
        self.start()
        response = self.client.post(reverse("passkey_register_options"), "{}", content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_prune_deletes_demos_a_day_after_last_use_and_keeps_shared_files(self):
        old = self.start()
        User.objects.filter(pk=old.pk).update(last_seen_at=timezone.now() - datetime.timedelta(hours=25))
        own = default_storage.save(f"rabbit-photos/{old.pk}/mine.jpg", ContentFile(b"x"))
        RabbitPhoto.objects.create(rabbit=Rabbit.all_objects.get(owner=old, name="Alder"), image=own)
        recent = demo.create_demo_account()
        with self.captureOnCommitCallbacks(execute=True):
            out = mock.Mock()
            call_command("prune_demo_accounts", stdout=out)
        self.assertFalse(User.objects.filter(pk=old.pk).exists())
        self.assertTrue(User.objects.filter(pk=recent.pk).exists())
        self.assertFalse(default_storage.exists(own))
        self.assertTrue(default_storage.exists(self.rows["photo"]))
        self.assertEqual(Rabbit.all_objects.filter(owner=self.base.owner).count(), 3)

    def test_deleting_a_demo_photo_keeps_the_shared_file(self):
        self.start()
        default_storage.delete(self.rows["photo"])
        self.assertTrue(default_storage.exists(self.rows["photo"]))

    def test_logging_out_deletes_the_demo(self):
        user = self.start()
        self.client.post(reverse("logout"))
        self.assertFalse(User.objects.filter(pk=user.pk).exists())


class GuestTests(MediaMixin, TestCase):
    def start(self):
        self.client.post(reverse("guest"))
        return User.objects.get(pk=self.client.session["_auth_user_id"])

    def test_own_herd_starts_empty_with_the_guest_rail_and_no_task_badge(self):
        me = self.start()
        self.assertTrue(me.is_guest)
        self.assertFalse(has_herd_data(me))
        body = self.client.get(reverse("index")).content.decode()
        self.assertIn("Saved on this device only.", body)
        self.assertIn("Create free account", body)
        self.assertNotIn(me.email, body)
        self.assertNotIn("data-badge", body)

    def test_signup_keeps_the_herd_in_place(self):
        me = self.start()
        rabbit(me, "Clover", "doe")
        response = self.client.post(reverse("signup"), {"email": "me@example.com", "password1": PASSWORD})
        self.assertRedirects(response, reverse("index"), fetch_redirect_response=False)
        me.refresh_from_db()
        self.assertEqual(me.email, "me@example.com")
        self.assertFalse(me.is_guest)
        self.assertTrue(me.is_active)
        self.assertTrue(me.check_password(PASSWORD))
        self.assertEqual(me.passkey_offer, "pending")
        self.assertEqual(Rabbit.objects.filter(owner=me).count(), 1)
        self.assertEqual(int(self.client.session["_auth_user_id"]), me.pk)

    def test_signing_in_adds_the_guest_herd_to_the_account(self):
        me = self.start()
        rabbit(me, "Clover", "doe", tattoo="C1")
        Location.objects.create(owner=me, name="Hutch 1")
        real = User.objects.create_user(email="keeper@example.com", password=PASSWORD, email_confirmed=True)
        rabbit(real, "Old", "buck", tattoo="C1")
        Location.objects.create(owner=real, name="Hutch 1")
        response = self.client.post(reverse("login"), {"username": "keeper@example.com", "password": PASSWORD}, follow=True)
        self.assertContains(response, "Your guest herd is now in your account.")
        self.assertEqual(Rabbit.objects.filter(owner=real).count(), 2)
        self.assertEqual(sorted(Rabbit.objects.filter(owner=real).values_list("tattoo", flat=True)), ["C1", "C1 (guest)"])
        self.assertEqual(sorted(Location.objects.filter(owner=real).values_list("name", flat=True)), ["Hutch 1", "Hutch 1 (guest)"])
        me.refresh_from_db()
        self.assertFalse(me.is_active)
        self.assertEqual(me.merged_into, real)
        self.assertEqual(guest.merge_guest_into(me, real), 0)  # twice is harmless

    def test_empty_idle_guests_are_deactivated_and_can_be_reactivated(self):
        empty = guest.create_guest()
        kept = guest.create_guest()
        rabbit(kept, "Clover", "doe")
        fresh = guest.create_guest()
        long_ago = timezone.now() - datetime.timedelta(days=8)
        User.objects.filter(pk__in=[empty.pk, kept.pk]).update(last_seen_at=long_ago)
        call_command("deactivate_empty_guests", stdout=mock.Mock())
        empty.refresh_from_db(); kept.refresh_from_db(); fresh.refresh_from_db()
        self.assertFalse(empty.is_active)
        self.assertIsNotNone(empty.deactivated_at)
        self.assertTrue(kept.is_active)
        self.assertTrue(fresh.is_active)
        staff = User.objects.create_superuser(email="admin@example.com", password=PASSWORD)
        self.client.force_login(staff)
        self.client.post(reverse("admin:accounts_user_changelist"), {"action": "reactivate", "_selected_action": [empty.pk]})
        empty.refresh_from_db()
        self.assertTrue(empty.is_active)

    def test_signup_has_no_confirm_field_and_no_passkey_only_signup(self):
        self.client.logout()
        body = self.client.get(reverse("signup")).content.decode()
        self.assertNotIn("password2", body)
        self.assertNotIn("Create a passkey instead", body)
        response = self.client.post(reverse("passkey_register_options"), '{"email": "x@example.com"}', content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email="x@example.com").exists())


class PasskeyOfferTests(TestCase):
    def test_offered_once_after_signup_and_skip_is_final(self):
        user = User.objects.create_user(email="keeper@example.com", password=PASSWORD, email_confirmed=True, passkey_offer="pending")
        self.client.force_login(user)
        body = self.client.get(reverse("index")).content.decode()
        self.assertIn("Sign in faster next time with a passkey?", body)
        self.assertIn("Add passkey", body)
        self.client.post(reverse("passkey_offer_skip"), HTTP_X_REQUESTED_WITH="fetch")
        user.refresh_from_db()
        self.assertEqual(user.passkey_offer, "skipped")
        self.assertNotIn("Sign in faster next time", self.client.get(reverse("index")).content.decode())

    def test_confirming_email_turns_the_offer_on(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        from accounts.tokens import email_confirmation_token

        user = User.objects.create_user(email="new@example.com", password=PASSWORD, is_active=False)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        self.client.get(reverse("confirm_email", args=[uid, email_confirmation_token.make_token(user)]))
        user.refresh_from_db()
        self.assertEqual(user.passkey_offer, "pending")


class CronTests(TestCase):
    def test_needs_the_secret(self):
        self.assertEqual(self.client.get("/cron/daily/").status_code, 404)
        with mock.patch.dict(os.environ, {"CRON_SECRET": "s3cret-for-tests"}):
            self.assertEqual(self.client.get("/cron/daily/").status_code, 404)
            ok = self.client.get("/cron/daily/", HTTP_AUTHORIZATION="Bearer s3cret-for-tests")
        self.assertEqual(ok.status_code, 200)
        self.assertIn("demo accounts", ok.json())
