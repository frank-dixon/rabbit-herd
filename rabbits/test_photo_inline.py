"""Managing photos from the rabbit's page: back_to=detail and rotating."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from .test_photos import PhotoTestCase, add_photo, image_bytes, make_rabbit, make_user
from .models import RabbitPhoto


class InlinePhotoTests(PhotoTestCase):
    def setUp(self):
        self.owner = make_user("inline@example.com")
        self.client.force_login(self.owner)
        self.rabbit = make_rabbit(self.owner)
        self.detail = reverse("rabbit_detail", args=[self.rabbit.pk]) + "#photos"

    def test_upload_from_detail_goes_back_to_the_photos_card(self):
        response = self.client.post(
            reverse("rabbit_photos", args=[self.rabbit.pk]),
            {"image": SimpleUploadedFile("a.jpg", image_bytes("JPEG"), content_type="image/jpeg"), "back_to": "detail"},
        )
        self.assertRedirects(response, self.detail, fetch_redirect_response=False)
        self.assertTrue(self.rabbit.photos.get().is_main)

    def test_bad_upload_from_detail_shows_the_error_there(self):
        response = self.client.post(
            reverse("rabbit_photos", args=[self.rabbit.pk]),
            {"image": SimpleUploadedFile("a.jpg", b"not a photo", content_type="image/jpeg"), "back_to": "detail"},
            follow=True,
        )
        self.assertContains(response, "couldn&#x27;t be opened as a photo")
        self.assertFalse(self.rabbit.photos.exists())

    def test_other_back_to_values_keep_the_photos_page(self):
        photo = add_photo(self.rabbit)
        response = self.client.post(reverse("rabbit_photo_notes", args=[photo.pk]), {"notes": "x", "back_to": "https://evil.example"})
        self.assertRedirects(response, reverse("rabbit_photos", args=[self.rabbit.pk]) + f"#photo-{photo.pk}", fetch_redirect_response=False)

    def test_notes_main_and_remove_go_back_to_detail(self):
        first, second = add_photo(self.rabbit, is_main=True), add_photo(self.rabbit)
        for name, pk, data in [
            ("rabbit_photo_notes", second.pk, {"notes": "At the show"}),
            ("rabbit_photo_set_main", second.pk, {}),
            ("rabbit_photo_delete", first.pk, {}),
        ]:
            response = self.client.post(reverse(name, args=[pk]), {**data, "back_to": "detail"})
            self.assertRedirects(response, self.detail, fetch_redirect_response=False)
        second.refresh_from_db()
        self.assertEqual((second.notes, second.is_main), ("At the show", True))
        self.assertFalse(RabbitPhoto.objects.filter(pk=first.pk).exists())

    def test_rotate_turns_the_picture_and_replaces_the_file(self):
        photo = RabbitPhoto(rabbit=self.rabbit, is_main=True)
        from django.core.files.base import ContentFile

        photo.image.save("wide.jpg", ContentFile(image_bytes("JPEG", size=(40, 20))), save=True)
        old_name, storage = photo.image.name, photo.image.storage
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("rabbit_photo_rotate", args=[photo.pk]), {"direction": "left", "back_to": "detail"})
        self.assertRedirects(response, self.detail, fetch_redirect_response=False)
        photo.refresh_from_db()
        self.assertNotEqual(photo.image.name, old_name)
        self.assertFalse(storage.exists(old_name))
        with photo.image.open("rb") as handle, Image.open(handle) as turned:
            self.assertEqual(turned.size, (20, 40))
            self.assertEqual(turned.format, "JPEG")

    def test_rotate_needs_a_direction_and_the_owner(self):
        photo = add_photo(self.rabbit)
        name = photo.image.name
        self.client.post(reverse("rabbit_photo_rotate", args=[photo.pk]), {"direction": "up"})
        photo.refresh_from_db()
        self.assertEqual(photo.image.name, name)
        self.client.force_login(make_user("other@example.com"))
        self.assertEqual(self.client.post(reverse("rabbit_photo_rotate", args=[photo.pk]), {"direction": "left"}).status_code, 404)
        self.assertEqual(self.client.get(reverse("rabbit_photo_rotate", args=[photo.pk])).status_code, 405)
