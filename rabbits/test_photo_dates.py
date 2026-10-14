"""Photo dates: only the taken date is kept from metadata, checked, and shown as a badge."""

import datetime
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from . import photo_processing
from .models import RabbitPhoto, valid_taken_date
from .test_photos import PhotoTestCase, add_photo, make_rabbit, make_user


def with_exif(fmt="JPEG", original=None, digitized=None, main=None, gps=False):
    image = Image.new("RGB", (40, 30), "white")
    exif = Image.Exif()
    if main:
        exif[0x0132] = main
    inner = exif.get_ifd(0x8769)
    if original:
        inner[36867] = original
    if digitized:
        inner[36868] = digitized
    if gps:
        exif.get_ifd(0x8825)[2] = (40.0, 26.0, 46.0)
    buffer = BytesIO()
    image.save(buffer, format=fmt, exif=exif.tobytes())
    return buffer.getvalue()


def png_screenshot():
    buffer = BytesIO()
    Image.new("RGB", (60, 120), "gray").save(buffer, format="PNG")
    return buffer.getvalue()


class ReadTakenDateTests(PhotoTestCase):
    def read(self, data, name="a.jpg"):
        return photo_processing.read_taken_date(SimpleUploadedFile(name, data))

    def test_original_then_digitized_then_main(self):
        self.assertEqual(self.read(with_exif(original="2026:03:03 10:00:00", main="2025:01:01 00:00:00")), datetime.date(2026, 3, 3))
        self.assertEqual(self.read(with_exif(digitized="2026:02:02 10:00:00")), datetime.date(2026, 2, 2))
        self.assertEqual(self.read(with_exif(main="2026:01:05 10:00:00")), datetime.date(2026, 1, 5))

    def test_no_date_png_and_garbage(self):
        self.assertIsNone(self.read(with_exif()))
        self.assertIsNone(self.read(png_screenshot(), "shot.png"))
        self.assertIsNone(self.read(b"not an image"))
        self.assertIsNone(self.read(with_exif(original="0000:00:00 00:00:00")))

    def test_heic_date_is_read(self):
        import pillow_heif  # noqa: F401  (registers the opener)

        buffer = BytesIO()
        exif = Image.Exif()
        exif.get_ifd(0x8769)[36867] = "2026:04:01 09:30:00"
        Image.new("RGB", (40, 30), "white").save(buffer, format="HEIF", exif=exif.tobytes())
        self.assertEqual(self.read(buffer.getvalue(), "IMG_0001.jpeg"), datetime.date(2026, 4, 1))

    def test_validity_window(self):
        born = datetime.date(2025, 1, 1)
        today = datetime.date(2026, 10, 12)
        self.assertIsNone(valid_taken_date(datetime.date(2024, 12, 31), born, today))
        self.assertIsNone(valid_taken_date(datetime.date(2026, 10, 13), born, today))
        self.assertEqual(valid_taken_date(datetime.date(2026, 3, 3), born, today), datetime.date(2026, 3, 3))


class UploadDateTests(PhotoTestCase):
    def setUp(self):
        self.owner = make_user("dates@example.com")
        self.client.force_login(self.owner)
        self.rabbit = make_rabbit(self.owner)  # born 2024-03-01
        self.url = reverse("rabbit_photos", args=[self.rabbit.pk])

    def upload(self, data, name="a.jpg", **extra):
        self.client.post(self.url, {"image": SimpleUploadedFile(name, data, content_type="image/jpeg"), "back_to": "detail", **extra})
        return RabbitPhoto.objects.filter(rabbit=self.rabbit).latest("pk")

    def test_exif_date_is_kept_and_everything_else_stripped(self):
        photo = self.upload(with_exif(original="2026:03:03 10:00:00", gps=True))
        self.assertEqual((photo.taken_at, photo.taken_from_metadata), (datetime.date(2026, 3, 3), True))
        self.assertEqual(photo.date_badge, "Taken Mar 3, 2026")
        with photo.image.open("rb") as handle, Image.open(handle) as stored:
            self.assertEqual(len(stored.getexif()), 0)

    def test_date_before_birth_is_ignored_and_falls_back_to_added(self):
        photo = self.upload(with_exif(original="2020:01:01 10:00:00"))
        self.assertIsNone(photo.taken_at)
        self.assertTrue(photo.date_badge.startswith("Added "))

    def test_no_exif_and_png_fall_back_to_added(self):
        self.assertTrue(self.upload(with_exif()).date_badge.startswith("Added "))
        self.assertTrue(self.upload(png_screenshot(), "shot.png").date_badge.startswith("Added "))

    def test_browser_hint_is_used_when_the_file_has_no_date(self):
        photo = self.upload(with_exif(), taken_hint="2026-02-14")
        self.assertEqual(photo.taken_at, datetime.date(2026, 2, 14))

    def test_existing_photos_show_added(self):
        self.assertTrue(add_photo(self.rabbit).date_badge.startswith("Added "))

    def test_detail_shows_badge_and_metadata_note(self):
        self.upload(with_exif(original="2026:03:03 10:00:00"))
        page = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk]))
        self.assertContains(page, "Taken Mar 3, 2026")
        self.assertContains(page, "This date was read from the photo's data. You can change it if it's wrong.")
        self.assertContains(page, 'value="2026-03-03"')

    def test_correcting_and_clearing_the_date(self):
        photo = self.upload(with_exif(original="2026:03:03 10:00:00"))
        url = reverse("rabbit_photo_date", args=[photo.pk])
        self.client.post(url, {"taken_at": "2026-03-05", "back_to": "detail"})
        photo.refresh_from_db()
        self.assertEqual((photo.taken_at, photo.taken_from_metadata), (datetime.date(2026, 3, 5), False))
        page = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk]))
        self.assertNotContains(page, "read from the photo")
        self.client.post(url, {"taken_at": "2023-01-01"})
        photo.refresh_from_db()
        self.assertEqual(photo.taken_at, datetime.date(2026, 3, 5))
        self.client.post(url, {"taken_at": ""})
        photo.refresh_from_db()
        self.assertIsNone(photo.taken_at)

    def test_only_the_owner_can_set_a_date(self):
        photo = add_photo(self.rabbit)
        self.client.force_login(make_user("nosy@example.com"))
        self.assertEqual(self.client.post(reverse("rabbit_photo_date", args=[photo.pk]), {"taken_at": "2026-03-05"}).status_code, 404)

    def test_demo_notes_are_credit_not_keeper_notes(self):
        photo = self.upload(with_exif())
        photo.notes = "Demo photo: Mia Kesterson, CC BY-SA 4.0, via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:x.jpg)."
        photo.save()
        self.assertTrue(photo.is_credit)
        self.assertEqual(photo.keeper_notes, "")
        photo.notes = "At the show"
        photo.save()
        self.assertFalse(photo.is_credit)
        self.assertEqual(photo.keeper_notes, "At the show")
