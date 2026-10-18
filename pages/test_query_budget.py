"""Query budgets for the main pages. Each page stays under its budget, and the count
does not grow with the size of the herd (no per-row queries)."""
import datetime
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from rabbits.models import HealthNote, Litter, Pairing, Rabbit, Task, Weight

MEDIA = tempfile.mkdtemp()

# Measured on the 140-rabbit demo baseline (2026-10-18), plus a little headroom.
BUDGETS = {
    "index": 15,
    "rabbit_list": 30,
    "litter_list": 14,
    "pairing_list": 16,
    "weights_hub": 10,
    "task_list": 12,
    "health_list": 8,
}


def grow(user, n, start=0):
    today = timezone.localdate()
    bucks = []
    for i in range(start, start + n):
        sex = "buck" if i % 3 == 0 else "doe"
        r = Rabbit.objects.create(owner=user, name=f"R{i}", sex=sex, breed="Rex", color="Black", tattoo=f"T{i}",
                                  birth_date=today - datetime.timedelta(days=200 + i), status="breeding")
        for d in (30, 15, 2):
            Weight.objects.create(rabbit=r, date=today - datetime.timedelta(days=d + i % 5), grams=3000 + i * 10 + d)
        Task.objects.create(owner=user, title=f"Check R{i}", due_on=today - datetime.timedelta(days=i % 4), rabbit=r)
        HealthNote.objects.create(rabbit=r, date=today, kind=HealthNote._meta.get_field("kind").choices[0][0],
                                  notes="Ok", follow_up_on=today + datetime.timedelta(days=2))
        if sex == "buck":
            bucks.append(r)
        elif bucks:
            p = Pairing.objects.create(owner=user, doe=r, buck=bucks[-1])
            Litter.objects.create(owner=user, pairing=p, bred_on=today - datetime.timedelta(days=10 + i % 30),
                                  kindled_on=(today - datetime.timedelta(days=i % 9)) if i % 2 else None, born_alive=6 if i % 2 else None)


@override_settings(MEDIA_ROOT=MEDIA)
class QueryBudgetTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = get_user_model().objects.create_user("budget@example.com", "pw-12345678")
        self.client.force_login(self.user)

    def count(self, name):
        url = reverse(name)
        self.client.get(url)  # warm per-process caches
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, name)
        return len(ctx.captured_queries)

    def test_pages_stay_within_budget_and_do_not_grow_with_the_herd(self):
        grow(self.user, 8)
        small = {name: self.count(name) for name in BUDGETS}
        grow(self.user, 24, start=8)
        large = {name: self.count(name) for name in BUDGETS}
        for name, budget in BUDGETS.items():
            with self.subTest(page=name):
                self.assertLessEqual(large[name], budget, f"{name}: {large[name]} queries, budget {budget}")
                self.assertLessEqual(large[name], small[name] + 2, f"{name} grew with the herd: {small[name]} -> {large[name]}")
