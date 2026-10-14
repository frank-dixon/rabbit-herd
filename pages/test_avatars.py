import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rabbits.models import HealthNote, Litter, Pairing, Rabbit, ShowEntry, Task


class AvatarEverywhereTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="av@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        mk = lambda name, sex, **kw: Rabbit.objects.create(owner=self.user, name=name, sex=sex, breed="Rex",
                                                           birth_date=datetime.date(2025, 1, 1), **kw)
        self.doe, self.buck = mk("Hazel", "doe"), mk("Basil", "buck")
        self.pairing = Pairing.objects.create(owner=self.user, doe=self.doe, buck=self.buck)
        self.litter = Litter.objects.create(owner=self.user, pairing=self.pairing, bred_on=datetime.date(2025, 6, 1))
        mk("Pip", "doe", litter=self.litter)
        HealthNote.objects.create(rabbit=self.doe, date=datetime.date(2025, 7, 1), kind="other", notes="ok")
        ShowEntry.objects.create(rabbit=self.doe, date=datetime.date(2025, 7, 1), show_name="Spring")
        Task.objects.create(owner=self.user, title="Brush", due_on=timezone.localdate(), rabbit=self.doe)

    def test_rabbit_rows_show_an_avatar(self):
        pages = {"pairing_list": [], "weights_hub": [], "health_list": [], "show_list": [], "task_list": [],
                 "litter_detail": [self.litter.pk]}
        for name, args in pages.items():
            body = self.client.get(reverse(name, args=args)).content.decode()
            main = body[body.index("<main"):]
            self.assertIn("data-avatar", main, name)
        self.assertIn("data-avatar", self.client.get("/").content.decode())
        pairings = self.client.get(reverse("pairing_list")).content.decode()
        self.assertEqual(pairings[pairings.index("it-thumbs"):].count("data-avatar", 0, 1500), 2)
