"""Photos on a health note are checked like any photo and shown with the note."""
import datetime
import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from .models import Rabbit, RabbitPhoto

MEDIA = tempfile.mkdtemp()


def jpeg(name="hock.jpg"):
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "tan").save(buf, "JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=MEDIA)
class HealthPhotoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def test_photos_attach_to_the_note_without_becoming_main(self):
        user = get_user_model().objects.create_user("h@example.com")
        self.client.force_login(user)
        rabbit = Rabbit.objects.create(owner=user, name="Hazel", sex="doe", breed="Rex", birth_date=datetime.date(2025, 1, 1))
        day = timezone.localdate().isoformat()
        self.client.post(f"/rabbits/{rabbit.pk}/health/", {"health_date": day, "health_kind": "injury", "notes": "Sore hock",
                                                            "health_photos": [jpeg(), jpeg("b.jpg")]})
        note = rabbit.health_notes.get()
        self.assertEqual(note.photos.count(), 2)
        self.assertFalse(RabbitPhoto.objects.filter(is_main=True).exists())
        self.assertContains(self.client.get(f"/rabbits/{rabbit.pk}/"), "Health photo 2")

    def test_a_bad_file_saves_nothing(self):
        user = get_user_model().objects.create_user("h2@example.com")
        self.client.force_login(user)
        rabbit = Rabbit.objects.create(owner=user, name="Hazel", sex="doe", breed="Rex", birth_date=datetime.date(2025, 1, 1))
        bad = SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg")
        self.client.post(f"/rabbits/{rabbit.pk}/health/", {"health_date": timezone.localdate().isoformat(),
                                                            "health_kind": "injury", "health_photos": [bad]})
        self.assertFalse(rabbit.health_notes.exists())
