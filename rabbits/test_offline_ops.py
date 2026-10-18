"""Offline queue for daily work: finished tasks, litter checks and kit counts, notes and
status changes. Each queued op applies once; a refused one keeps its error and frees
its op_id so it can be tried again."""
import datetime
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Litter, Pairing, Rabbit, SyncOp, Task
from .sync import QUEUE_FAILED

Q = {"HTTP_X_BB_QUEUE": "1"}


class OfflineOpsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("off@example.com", "pw-12345678")
        self.client.force_login(self.user)
        mk = lambda name, sex: Rabbit.objects.create(owner=self.user, name=name, sex=sex, breed="Rex", birth_date=datetime.date(2024, 1, 1))
        self.doe, self.buck = mk("Willow", "doe"), mk("Jet", "buck")
        self.today = timezone.localdate()
        self.litter = Litter.objects.create(owner=self.user, pairing=Pairing.objects.create(owner=self.user, doe=self.doe, buck=self.buck),
                                            bred_on=self.today - datetime.timedelta(days=40), kindled_on=self.today - datetime.timedelta(days=9),
                                            born_alive=6)
        self.task = Task.objects.create(owner=self.user, title="Trim nails", due_on=self.today)

    def post(self, url, data, op=None, **extra):
        return self.client.post(url, {**data, "op_id": str(op or uuid.uuid4())}, **extra)

    def test_a_queued_task_done_applies_once(self):
        op = uuid.uuid4()
        url = reverse("task_done", args=[self.task.pk])
        self.assertEqual(self.post(url, {}, op, **Q).status_code, 201)
        self.assertEqual(self.post(url, {}, op, **Q).status_code, 200)  # a retry: duplicate, no second toggle
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.done_at)
        # The toast the view queued is dropped, so it can't pop up on some later page.
        self.assertNotContains(self.client.get(reverse("task_list")), "Trim nails: done.")

    def test_a_queued_litter_check_with_a_kit_count_applies_once(self):
        op = uuid.uuid4()
        url = reverse("litter_check", args=[self.litter.pk])
        data = {"mode": "whole", "kit_count": "5", "note": "All nursing", "date": self.today.isoformat()}
        self.assertEqual(self.post(url, data, op, **Q).status_code, 201)
        self.assertEqual(self.post(url, data, op, **Q).status_code, 200)
        self.assertEqual(self.litter.checks.count(), 1)
        self.assertEqual(self.litter.checks.get().kit_count, 5)

    def test_a_refused_check_keeps_its_error_and_frees_the_op(self):
        op = uuid.uuid4()
        url = reverse("litter_check", args=[self.litter.pk])
        response = self.post(url, {"mode": "whole", "weight": "lots"}, op, **Q)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "Check the weight.")
        self.assertFalse(SyncOp.objects.filter(op_id=op).exists())
        self.assertEqual(self.post(url, {"mode": "whole", "kit_count": "6", "note": "Fine"}, op, **Q).status_code, 201)

    def test_a_queued_litter_note_applies_once(self):
        op = uuid.uuid4()
        url = reverse("litter_note_add", args=[self.litter.pk])
        for _ in range(2):
            self.post(url, {"text": "Nest box dry", "note": "Nest box dry"}, op, **Q)
        self.assertEqual(SyncOp.objects.filter(op_id=op).count(), 1)

    def test_a_queued_status_change_applies_and_a_bad_one_is_refused(self):
        url = reverse("rabbit_status", args=[self.buck.pk])
        self.assertEqual(self.post(url, {"status": "growing"}, **Q).status_code, 201)
        self.buck.refresh_from_db()
        self.assertEqual(self.buck.status, "growing")
        bad = self.post(url, {"status": "flying"}, **Q)
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(bad.json()["error"], QUEUE_FAILED)

    def test_daily_forms_are_marked_for_the_queue(self):
        self.assertContains(self.client.get(reverse("task_list")), 'data-offline-queue="Task"')
        page = self.client.get(reverse("litter_detail", args=[self.litter.pk]))
        self.assertContains(page, 'data-offline-queue="Litter check"')
        self.assertContains(self.client.get(reverse("rabbit_status", args=[self.buck.pk])), 'data-offline-queue="Status change"')
        self.assertContains(self.client.get(reverse("pwa_offline")), "Photos need a connection.")
