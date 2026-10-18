"""The signup line that tells a guest their herd comes along (Copyrighter, 2026-10-18)."""
import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.guest import carry_line, carry_line_for, create_guest
from rabbits.models import Litter, Pairing, Rabbit


class CarryLineTests(SimpleTestCase):
    def test_both_parts_always_move(self):
        self.assertEqual(carry_line(12, 3), "Your 12 rabbits and 3 litters move into your new account.")
        self.assertEqual(carry_line(1, 1), "Your 1 rabbit and 1 litter move into your new account.")
        self.assertEqual(carry_line(1, 3), "Your 1 rabbit and 3 litters move into your new account.")
        self.assertEqual(carry_line(12, 1), "Your 12 rabbits and 1 litter move into your new account.")

    def test_rabbits_only(self):
        self.assertEqual(carry_line(1, 0), "Your 1 rabbit moves into your new account.")
        self.assertEqual(carry_line(12, 0), "Your 12 rabbits move into your new account.")

    def test_litters_only(self):
        self.assertEqual(carry_line(0, 1), "Your 1 litter moves into your new account.")
        self.assertEqual(carry_line(0, 3), "Your 3 litters move into your new account.")

    def test_nothing_yet(self):
        self.assertEqual(carry_line(0, 0), "Everything you've added so far moves into your new account.")

    def test_no_exclamation_or_apology(self):
        for args in ((0, 0), (1, 0), (0, 1), (2, 2)):
            line = carry_line(*args)
            self.assertNotIn("!", line)
            self.assertNotIn("sorry", line.lower())


class CarryLineSignupTests(TestCase):
    def herd(self, owner, rabbits, litters, samples=0):
        made = [Rabbit.objects.create(owner=owner, name=f"R{i}", sex="doe" if i % 2 else "buck", breed="Rex", birth_date=datetime.date(2024, 1, 1))
                for i in range(max(rabbits, 2 if litters else 0))]
        Rabbit.objects.filter(pk__in=[r.pk for r in made[rabbits:]]).update(is_sample=True)
        for _ in range(samples):
            Rabbit.objects.create(owner=owner, name="Sample", sex="doe", breed="Rex", birth_date=datetime.date(2024, 1, 1), is_sample=True)
        for _ in range(litters):
            pairing = Pairing.objects.create(owner=owner, doe=made[1], buck=made[0])
            Litter.objects.create(owner=owner, pairing=pairing, bred_on=datetime.date(2026, 9, 1))

    def signup_line(self):
        body = self.client.get(reverse("signup")).content.decode()
        if "data-guest-carry" not in body:
            return None
        start = body.index(">", body.index("data-guest-carry")) + 1
        return body[start:body.index("</p>", start)].replace("&#x27;", "'")

    def test_guest_sees_their_counts_without_samples(self):
        guest = create_guest()
        self.herd(guest, rabbits=12, litters=3, samples=4)
        self.client.force_login(guest)
        self.assertEqual(self.signup_line(), "Your 12 rabbits and 3 litters move into your new account.")

    def test_guest_with_one_rabbit(self):
        guest = create_guest()
        self.herd(guest, rabbits=1, litters=0)
        self.client.force_login(guest)
        self.assertEqual(self.signup_line(), "Your 1 rabbit moves into your new account.")

    def test_empty_guest_gets_the_general_line(self):
        guest = create_guest()
        self.client.force_login(guest)
        self.assertEqual(self.signup_line(), "Everything you've added so far moves into your new account.")

    def test_demo_accounts_never_see_it(self):
        demo = get_user_model().objects.create_user("demo-x@demo.invalid", None, is_guest=True, is_demo=True)
        self.herd(demo, rabbits=3, litters=1)
        self.assertIsNone(carry_line_for(demo))
        self.client.force_login(demo)
        self.assertIsNone(self.signup_line())

    def test_signed_out_visitors_never_see_it(self):
        self.assertIsNone(self.signup_line())


class GuestDeviceWordingTests(TestCase):
    """Copyrighter, 2026-10-18: the guest rail and the signup's second line."""

    def test_guest_rail_says_saved_on_this_device_only(self):
        from pages.copy import RAIL

        self.assertEqual(RAIL["guest"], {"text": "Saved on this device only.", "action": "Create free account"})
        self.client.force_login(create_guest())
        body = self.client.get(reverse("rabbit_list")).content.decode()
        self.assertIn("Saved on this device only.", body)
        self.assertIn("Create free account", body)

    def test_signup_adds_any_device_line_for_guests_only(self):
        line = "Then you can open it on any device."
        self.assertNotIn(line, self.client.get(reverse("signup")).content.decode())
        demo = get_user_model().objects.create_user("demo-y@demo.invalid", None, is_guest=True, is_demo=True)
        self.client.force_login(demo)
        self.assertNotIn(line, self.client.get(reverse("signup")).content.decode())
        self.client.force_login(create_guest())
        body = self.client.get(reverse("signup")).content.decode()
        self.assertIn(line, body)
        self.assertLess(body.index("data-guest-carry"), body.index(line))


class GuestSessionTests(TestCase):
    """Frank, 2026-10-18: a guest herd stays on the device as long as its cookies do; the session
    cookie lasts about a year and slides forward with use."""

    def test_starting_a_guest_herd_sets_a_year_long_cookie(self):
        from accounts.guest import GUEST_SESSION_AGE

        response = self.client.post(reverse("guest"))
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(int(cookie["max-age"]), GUEST_SESSION_AGE)
        self.assertEqual(GUEST_SESSION_AGE, 365 * 24 * 60 * 60)

    def test_the_cookie_slides_forward_with_use(self):
        from accounts.guest import GUEST_SESSION_AGE

        self.client.post(reverse("guest"))
        session = self.client.session
        session["seen_at"] = 0  # last seen long ago
        session.set_expiry(60)  # as if nearly expired
        session.save()
        response = self.client.get(reverse("index"))
        self.assertEqual(int(response.cookies[settings.SESSION_COOKIE_NAME]["max-age"]), GUEST_SESSION_AGE)

    def test_demo_sessions_do_not_slide_to_a_year(self):
        from accounts.guest import GUEST_SESSION_AGE

        demo = get_user_model().objects.create_user("demo-z@demo.invalid", None, is_guest=True, is_demo=True)
        self.client.force_login(demo)
        response = self.client.get(reverse("index"))
        cookie = response.cookies.get(settings.SESSION_COOKIE_NAME)
        self.assertTrue(cookie is None or cookie["max-age"] != GUEST_SESSION_AGE)
