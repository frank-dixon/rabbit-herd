import tempfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.contrib.admin.sites import site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import User
from rabbits.forms import MAX_PHOTO_BYTES, RabbitForm
from rabbits.models import Rabbit

MEDIA_ROOT = Path(tempfile.mkdtemp())


def make_user(email):
    return User.objects.create_user(
        email=email,
        password="Rabbit-Herd-Pass-1",
        is_active=True,
        email_confirmed=True,
    )


def png_upload(name="rabbit.png", content_type="image/png"):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


def rabbit_fields(**overrides):
    data = {
        "name": "Clover",
        "sex": Rabbit.Sex.DOE,
        "breed": "Dutch",
        "color": "Black",
        "birth_date": "2024-03-01",
        "status": Rabbit.Status.BREEDING,
    }
    data.update(overrides)
    return data


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RabbitRecordTests(TestCase):
    def setUp(self):
        self.owner = make_user("frank@example.com")
        self.other = make_user("other@example.com")
        self.client.force_login(self.owner)

    def test_anonymous_visitor_is_sent_to_sign_in(self):
        self.client.logout()

        response = self.client.get(reverse("rabbit_list"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('rabbit_list')}",
        )

    def test_owner_can_add_and_edit_a_rabbit(self):
        created = self.client.post(reverse("rabbit_create"), rabbit_fields())
        rabbit = Rabbit.objects.get()
        self.assertRedirects(created, reverse("rabbit_detail", args=[rabbit.pk]))
        self.assertEqual(rabbit.owner, self.owner)
        self.assertEqual(rabbit.name, "Clover")

        edited = self.client.post(
            reverse("rabbit_edit", args=[rabbit.pk]),
            rabbit_fields(name="Clover 2", status=Rabbit.Status.SOLD),
        )
        self.assertRedirects(edited, reverse("rabbit_detail", args=[rabbit.pk]))
        rabbit.refresh_from_db()
        self.assertEqual(rabbit.name, "Clover 2")
        self.assertEqual(rabbit.status, Rabbit.Status.SOLD)

        detail = self.client.get(reverse("rabbit_detail", args=[rabbit.pk]))
        self.assertContains(detail, "Clover 2")
        self.assertContains(detail, "Sold")
        self.assertContains(detail, "Dutch")

    def test_users_only_see_their_own_rabbits(self):
        own = Rabbit.objects.create(
            owner=self.owner,
            name="Clover",
            sex=Rabbit.Sex.DOE,
            breed="Dutch",
            color="Black",
            birth_date="2024-03-01",
            status=Rabbit.Status.BREEDING,
        )
        hidden = Rabbit.objects.create(
            owner=self.other,
            name="Hidden",
            sex=Rabbit.Sex.BUCK,
            breed="Rex",
            color="White",
            birth_date="2024-04-01",
            status=Rabbit.Status.GROWING,
        )

        listing = self.client.get(reverse("rabbit_list"))
        self.assertContains(listing, "Clover")
        self.assertNotContains(listing, "Hidden")

        self.assertEqual(self.client.get(reverse("rabbit_detail", args=[hidden.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("rabbit_edit", args=[hidden.pk])).status_code, 404)
        self.assertEqual(
            self.client.post(reverse("rabbit_archive", args=[hidden.pk])).status_code,
            404,
        )
        hidden.refresh_from_db()
        self.assertIsNone(hidden.archived_at)

        self.client.force_login(self.other)
        other_list = self.client.get(reverse("rabbit_list"))
        self.assertContains(other_list, "Hidden")
        self.assertNotContains(other_list, "Clover")
        self.assertEqual(self.client.get(reverse("rabbit_detail", args=[own.pk])).status_code, 404)

    def test_archive_hides_the_rabbit_and_restore_brings_it_back(self):
        rabbit = Rabbit.objects.create(
            owner=self.owner,
            name="Clover",
            sex=Rabbit.Sex.DOE,
            breed="Dutch",
            color="Black",
            birth_date="2024-03-01",
            status=Rabbit.Status.CULLED,
        )

        archived = self.client.post(reverse("rabbit_archive", args=[rabbit.pk]))
        self.assertRedirects(archived, reverse("rabbit_list"))
        rabbit.refresh_from_db()
        self.assertIsNotNone(rabbit.archived_at)
        self.assertEqual(Rabbit.objects.count(), 1)

        active = self.client.get(reverse("rabbit_list"))
        self.assertNotContains(active, "Open Clover")
        self.assertContains(active, "No rabbits yet.")

        stored = self.client.get(reverse("rabbit_archived"))
        self.assertContains(stored, "Clover")
        self.assertContains(stored, "Culled")

        restored = self.client.post(reverse("rabbit_restore", args=[rabbit.pk]))
        self.assertRedirects(restored, reverse("rabbit_detail", args=[rabbit.pk]))
        rabbit.refresh_from_db()
        self.assertIsNone(rabbit.archived_at)
        self.assertContains(self.client.get(reverse("rabbit_list")), "Clover")
        self.assertContains(self.client.get(reverse("rabbit_archived")), "No archived rabbits.")

    def test_form_rejects_a_missing_name_and_a_future_birth_date(self):
        missing = self.client.post(reverse("rabbit_create"), rabbit_fields(name=""))
        self.assertContains(missing, "This field is required.")
        self.assertEqual(Rabbit.objects.count(), 0)

        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        future = self.client.post(reverse("rabbit_create"), rabbit_fields(birth_date=tomorrow))
        self.assertContains(future, "Birth date cannot be in the future.")
        self.assertEqual(Rabbit.objects.count(), 0)

    def test_form_rejects_a_non_image_and_an_oversized_photo(self):
        text = SimpleUploadedFile("notes.png", b"not an image", content_type="image/png")
        rejected = self.client.post(
            reverse("rabbit_create"),
            {**rabbit_fields(), "photo": text},
        )
        self.assertContains(rejected, "Upload a valid image.")
        self.assertEqual(Rabbit.objects.count(), 0)

        bitmap = BytesIO()
        Image.new("RGB", (8, 8), "white").save(bitmap, format="BMP")
        wrong_type = SimpleUploadedFile("rabbit.png", bitmap.getvalue(), content_type="image/bmp")
        typed = self.client.post(
            reverse("rabbit_create"),
            {**rabbit_fields(), "photo": wrong_type},
        )
        self.assertContains(typed, "JPEG, PNG, GIF, or WebP")
        self.assertEqual(Rabbit.objects.count(), 0)

        huge = png_upload()
        huge.size = MAX_PHOTO_BYTES + 1
        oversized = RabbitForm(data=rabbit_fields(), files={"photo": huge})
        self.assertFalse(oversized.is_valid())
        self.assertIn("5 MB or smaller", oversized.errors["photo"][0])
        self.assertEqual(Rabbit.objects.count(), 0)

    def test_a_valid_photo_is_stored_and_served_only_when_debug_is_on(self):
        upload = png_upload()
        response = self.client.post(
            reverse("rabbit_create"),
            {**rabbit_fields(), "photo": upload},
        )
        rabbit = Rabbit.objects.get()
        self.assertRedirects(response, reverse("rabbit_detail", args=[rabbit.pk]))
        self.assertTrue(rabbit.photo.name.startswith(f"rabbits/{self.owner.pk}/"))

        detail = self.client.get(reverse("rabbit_detail", args=[rabbit.pk]))
        self.assertContains(detail, rabbit.photo.url)

        hidden = self.client.get(rabbit.photo.url)
        self.assertEqual(hidden.status_code, 404)

        with override_settings(DEBUG=True):
            shown = self.client.get(rabbit.photo.url)
        self.assertEqual(shown.status_code, 200)
        self.assertIn(shown["Content-Type"], {"image/png", "image/jpeg"})

    def test_admin_cannot_delete_a_rabbit(self):
        self.assertFalse(site._registry[Rabbit].has_delete_permission(None))
