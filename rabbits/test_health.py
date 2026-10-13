import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import HealthNote, Rabbit, Task
from .test_contacts import user


class HealthTests(TestCase):
    def setUp(self):
        self.owner = user("health@example.com")
        self.client.force_login(self.owner)
        self.rabbit = Rabbit.objects.create(owner=self.owner, name="Hazel", sex="doe", breed="Rex", color="Black",
                                            birth_date=datetime.date(2024, 1, 1))
        self.today = timezone.localdate()
        self.url = reverse("rabbit_health_add", args=[self.rabbit.pk])

    def test_note_with_follow_up_makes_a_task(self):
        follow = self.today + datetime.timedelta(days=7)
        self.client.post(self.url, {"health_date": self.today.isoformat(), "health_kind": "treatment", "notes": "Ivermectin, 0.2 ml",
                                    "health_follow_up": follow.isoformat()})
        note = HealthNote.objects.get()
        self.assertEqual(note.task.due_on, follow)
        self.assertEqual(note.task.title, "Follow up: treatment (Hazel)")
        detail = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk]))
        self.assertContains(detail, "Ivermectin, 0.2 ml")
        self.assertContains(detail, "on your tasks")
        self.assertContains(self.client.get(reverse("task_list")), "Follow up: treatment (Hazel)")
        self.client.post(reverse("rabbit_health_delete", args=[note.pk]))
        self.assertFalse(HealthNote.objects.exists())
        self.assertFalse(Task.objects.exists())

    def test_note_without_follow_up_and_bad_input(self):
        self.client.post(self.url, {"health_date": self.today.isoformat(), "health_kind": "checkup"})
        self.assertEqual(HealthNote.objects.get().task, None)
        for data, msg in (
            ({"health_date": "", "health_kind": "checkup"}, "Please enter the date"),
            ({"health_date": (self.today + datetime.timedelta(days=1)).isoformat(), "health_kind": "checkup"}, "in the future"),
            ({"health_date": self.today.isoformat(), "health_kind": "spa"}, "Please choose a type"),
            ({"health_date": self.today.isoformat(), "health_kind": "injury", "health_follow_up": "2000-01-01"}, "before the note"),
        ):
            self.assertContains(self.client.post(self.url, data, follow=True), msg)
        self.assertEqual(HealthNote.objects.count(), 1)

    def test_owner_scope(self):
        note = HealthNote.objects.create(rabbit=self.rabbit, date=self.today, kind="other")
        self.client.force_login(user("x@example.com"))
        self.assertEqual(self.client.post(self.url, {"health_date": self.today.isoformat(), "health_kind": "other"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("rabbit_health_delete", args=[note.pk])).status_code, 404)
