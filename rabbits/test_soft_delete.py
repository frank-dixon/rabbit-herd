import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import purge
from .models import HerdSettings, Rabbit, Weight

User = get_user_model()


class SoftDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="frank@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        self.rabbit = Rabbit.objects.create(owner=self.user, name="Hazel", sex="doe", breed="Mini Rex", color="Black",
                                            tattoo="HC01", birth_date=datetime.date(2025, 3, 1))
        Weight.objects.create(rabbit=self.rabbit, date=datetime.date(2026, 9, 1), grams=1900)

    def test_delete_hides_restore_brings_back(self):
        self.client.post(reverse("rabbit_delete", args=[self.rabbit.pk]))
        self.assertFalse(Rabbit.objects.filter(pk=self.rabbit.pk).exists())
        self.assertEqual(self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk])).status_code, 404)
        self.assertContains(self.client.get(reverse("rabbit_trash")), "Hazel")
        # Its tattoo is free again while it's deleted.
        Rabbit.objects.create(owner=self.user, name="Pip", sex="buck", breed="Mini Rex", color="Black", tattoo="HC01",
                              birth_date=datetime.date(2025, 3, 1))
        self.client.post(reverse("rabbit_undelete", args=[self.rabbit.pk]))
        self.assertFalse(Rabbit.objects.filter(pk=self.rabbit.pk).exists())  # blocked: tattoo taken
        Rabbit.objects.filter(name="Pip").update(tattoo="HC02")
        self.client.post(reverse("rabbit_undelete", args=[self.rabbit.pk]))
        self.assertEqual(Rabbit.objects.get(pk=self.rabbit.pk).weights.count(), 1)

    def test_purge_respects_each_keepers_retention(self):
        HerdSettings.objects.create(user=self.user, deleted_retention_days=7)
        Rabbit.objects.filter(pk=self.rabbit.pk).update(deleted_at=timezone.now() - datetime.timedelta(days=8))
        self.assertEqual(purge.purge_rabbits(), 1)
        self.assertFalse(Rabbit.all_objects.filter(pk=self.rabbit.pk).exists())

    def test_purge_keeps_rabbits_inside_the_window_and_remove_needs_the_phrase(self):
        Rabbit.objects.filter(pk=self.rabbit.pk).update(deleted_at=timezone.now() - datetime.timedelta(days=8))
        self.assertEqual(purge.purge_rabbits(), 0)  # default 30 days
        url = reverse("rabbit_delete_forever", args=[self.rabbit.pk])
        self.assertEqual(self.client.post(url, {"confirm": "nope"}).status_code, 400)
        self.client.post(url, {"confirm": "delete Hazel"})
        self.assertFalse(Rabbit.all_objects.filter(pk=self.rabbit.pk).exists())


class PendingPurgeTests(TestCase):
    def test_only_old_pending_uploads_are_removed(self):
        import os
        import tempfile

        from django.core.files.base import ContentFile
        from django.core.files.storage import FileSystemStorage

        storage = FileSystemStorage(location=tempfile.mkdtemp())
        old = storage.save("flow-pending/7/old.jpg", ContentFile(b"x"))
        new = storage.save("flow-pending/7/new.jpg", ContentFile(b"x"))
        keep = storage.save("rabbits/7/photo.jpg", ContentFile(b"x"))
        stamp = (timezone.now() - datetime.timedelta(days=3)).timestamp()
        os.utime(storage.path(old), (stamp, stamp))
        self.assertEqual(purge.purge_pending(storage=storage), 1)
        self.assertEqual([storage.exists(n) for n in (old, new, keep)], [False, True, True])
