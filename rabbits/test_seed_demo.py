import datetime
import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Litter, Rabbit, Task, Weight

User = get_user_model()
SECRET = "demo-Test-Pass-9431"


def seed(*args):
    import io
    out = io.StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


class SeedDemoTests(TestCase):
    def test_builds_the_herd_and_reads_the_password_from_env(self):
        with mock.patch.dict(os.environ, {"DEMO_PASSWORD": SECRET}):
            out = seed()
        self.assertNotIn(SECRET, out)
        user = User.objects.get(email="demo@bramble-burrow.app")
        self.assertTrue(user.check_password(SECRET))
        mine = Rabbit.objects.filter(owner=user)
        alive = mine.exclude(status__in=Rabbit.FORMER)
        # New Zealand herd: one buck per color (+ broken, juniors, archived), 3–4 does per color, Californian does.
        self.assertGreaterEqual(alive.filter(sex="buck").count(), 10)
        self.assertGreaterEqual(alive.filter(sex="doe").count(), 22)
        self.assertEqual(alive.filter(breed="Californian").count(), 3)
        self.assertTrue(alive.filter(color__startswith="Broken").exists())
        self.assertTrue(mine.filter(status="deceased").exists())
        # Frank's rule: no litter older than 42 days is left unconverted.
        cutoff = datetime.date.today() - datetime.timedelta(days=42)
        self.assertEqual(Litter.objects.filter(owner=user, kindled_on__lt=cutoff, converted_at__isnull=True).count(), 0)
        self.assertTrue(mine.filter(dressed_grams__isnull=False).exists())
        self.assertTrue(Rabbit.all_objects.filter(owner=user, archived_at__isnull=False).exists())
        self.assertTrue(Litter.objects.filter(owner=user, converted_at__isnull=False).exists())
        self.assertGreaterEqual(mine.filter(status="sold").count(), 3)
        self.assertTrue(Litter.objects.filter(owner=user).exists())
        self.assertTrue(Task.objects.filter(owner=user).exists())
        self.assertGreater(Weight.objects.filter(rabbit__owner=user).count(), 50)

    def test_rerun_updates_without_duplicating_and_leaves_others_alone(self):
        other = User.objects.create_user(email="keeper@example.com", password="x-strong-Pass-1")
        Rabbit.objects.create(owner=other, name="Keep", sex="doe", breed="Rex", color="Black", birth_date="2025-01-01")
        with mock.patch.dict(os.environ, {"DEMO_PASSWORD": SECRET}):
            seed()
            first = (User.objects.count(), Rabbit.objects.count(), Weight.objects.count(), Litter.objects.count())
        with mock.patch.dict(os.environ, {"DEMO_PASSWORD": SECRET + "x"}):
            self.assertIn("Updated", seed())
        self.assertEqual((User.objects.count(), Rabbit.objects.count(), Weight.objects.count(), Litter.objects.count()), first)
        self.assertTrue(User.objects.get(email="demo@bramble-burrow.app").check_password(SECRET + "x"))
        self.assertTrue(Rabbit.objects.filter(owner=other, name="Keep").exists())

    def test_missing_password_is_an_error_unless_no_password(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEMO_PASSWORD", None)
            with self.assertRaises(CommandError):
                seed()
            seed("--no-password")
        self.assertFalse(User.objects.get(email="demo@bramble-burrow.app").has_usable_password())


class SeedDemoPagesTests(TestCase):
    def test_every_list_page_renders_for_the_demo_herd(self):
        from django.urls import get_resolver, reverse, NoReverseMatch

        with mock.patch.dict(os.environ, {"DEMO_PASSWORD": SECRET}):
            seed()
        self.client.force_login(User.objects.get(email="demo@bramble-burrow.app"))
        names = [n for n in get_resolver().reverse_dict if isinstance(n, str)]
        checked = 0
        for name in sorted(names):
            try:
                url = reverse(name)
            except NoReverseMatch:
                continue
            if any(word in name for word in ("logout", "delete", "pwa", "export", "restart")):
                continue
            with self.subTest(name=name):
                self.assertLess(self.client.get(url).status_code, 500)
                checked += 1
        for qs in ("?tab=former", "?view=list", "?tab=archived"):
            self.assertEqual(self.client.get(reverse("rabbit_list") + qs).status_code, 200)
        self.assertGreater(checked, 10)
