"""Queued writes are idempotent (op_id) and queued form errors come back as 422.

Regression tests for the offline-queue duplicate bug (a retry or a second tab
posting the same entry made two rows) and the silent-loss bug (a form error
re-rendered with 200, which the queue took as success and dropped)."""
import datetime
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import HealthNote, Rabbit, SyncOp, Weight

Q = {"HTTP_X_BB_QUEUE": "1"}


class SyncTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("s@example.com")
        self.client.force_login(self.user)
        self.rabbit = Rabbit.objects.create(owner=self.user, name="Clover", sex="doe", breed="Rex",
                                            birth_date=datetime.date(2025, 1, 1))
        self.day = timezone.localdate().isoformat()

    def weight(self, op, extra=Q, **fields):
        data = {"date": self.day, "lb": "4", "oz": "6", "op_id": op, **fields}
        return self.client.post(f"/rabbits/{self.rabbit.pk}/weights/", data, **extra)

    def health(self, op, extra=Q, **fields):
        data = {"health_date": self.day, "health_kind": "checkup", "notes": "ok", "op_id": op, **fields}
        return self.client.post(f"/rabbits/{self.rabbit.pk}/health/", data, **extra)

    def test_same_weight_op_posted_three_times_makes_one_row(self):
        op = str(uuid.uuid4())
        codes = [self.weight(op).status_code for _ in range(3)]
        self.assertEqual(codes, [201, 200, 200])
        self.assertEqual(Weight.objects.filter(rabbit=self.rabbit).count(), 1)
        self.assertTrue(self.weight(op).json()["duplicate"])

    def test_same_health_op_posted_twice_makes_one_note(self):
        op = str(uuid.uuid4())
        self.assertEqual(self.health(op).status_code, 201)
        self.assertEqual(self.health(op).status_code, 200)
        self.assertEqual(HealthNote.objects.filter(rabbit=self.rabbit).count(), 1)

    def test_plain_double_submit_is_deduped_too(self):
        op = str(uuid.uuid4())
        self.assertEqual(self.weight(op, extra={}).status_code, 302)
        self.assertEqual(self.weight(op, extra={}).status_code, 302)
        self.assertEqual(Weight.objects.filter(rabbit=self.rabbit).count(), 1)

    def test_distinct_ops_each_apply(self):
        self.weight(str(uuid.uuid4()))
        self.weight(str(uuid.uuid4()))
        self.assertEqual(Weight.objects.filter(rabbit=self.rabbit).count(), 2)

    def test_queued_weight_form_error_is_422_with_message_and_claims_nothing(self):
        op = str(uuid.uuid4())
        response = self.weight(op, date="")
        self.assertEqual(response.status_code, 422)
        self.assertIn("needs a date", response.json()["error"])
        self.assertFalse(SyncOp.objects.exists())
        # The kept entry, once fixed, still applies under the same op_id.
        self.assertEqual(self.weight(op).status_code, 201)

    def test_queued_health_form_error_is_422(self):
        response = self.health(str(uuid.uuid4()), health_kind="nope")
        self.assertEqual(response.status_code, 422)
        self.assertIn("Choose a type", response.json()["error"])
        self.assertFalse(HealthNote.objects.exists())

    def test_unqueued_form_error_still_redirects(self):
        self.assertEqual(self.weight(str(uuid.uuid4()), extra={}, date="").status_code, 302)

    def test_post_without_op_id_still_works(self):
        self.assertEqual(self.weight("").status_code, 201)
        self.assertEqual(self.weight("").status_code, 201)
        self.assertEqual(Weight.objects.count(), 2)
