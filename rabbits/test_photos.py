"""Rabbit photos: the model, the move from Rabbit.photo, and owner-only serving."""

import datetime
import shutil
import tempfile
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import User
from rabbits.models import Rabbit, RabbitPhoto

MEDIA_ROOT = Path(tempfile.mkdtemp())


def make_user(email):
    return User.objects.create_user(email=email, password="Rabbit-Herd-Pass-1", is_active=True, email_confirmed=True)


def image_bytes(fmt="PNG", size=(8, 8), color="white", **save_kwargs):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt, **save_kwargs)
    return buffer.getvalue()


def make_rabbit(owner, name="Clover"):
    return Rabbit.objects.create(
        owner=owner, name=name, sex="doe", breed="Dutch", color="Black", birth_date=datetime.date(2024, 3, 1)
    )


def add_photo(rabbit, is_main=False, notes="", name="phone-upload.png"):
    photo = RabbitPhoto(rabbit=rabbit, is_main=is_main, notes=notes)
    photo.image.save(name, ContentFile(image_bytes()), save=False)
    photo.save()
    return photo


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PhotoTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.owner = make_user("keeper@example.com")
        self.stranger = make_user("stranger@example.com")
        self.rabbit = make_rabbit(self.owner)
        self.client.force_login(self.owner)


class RabbitPhotoModelTests(PhotoTestCase):
    def test_files_get_a_random_name_under_the_owner(self):
        photo = add_photo(self.rabbit, name="IMG_2041 Grandmas farm.PNG")
        path = Path(photo.image.name)
        self.assertEqual(path.parent.as_posix(), f"rabbit-photos/{self.owner.pk}")
        self.assertNotIn("IMG_2041", path.name)
        self.assertRegex(path.name, r"^[0-9a-f]{32}\.png$")

    def test_only_one_main_photo_per_rabbit(self):
        add_photo(self.rabbit, is_main=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            add_photo(self.rabbit, is_main=True)

    def test_main_photo_comes_first(self):
        first = add_photo(self.rabbit)
        main = add_photo(self.rabbit, is_main=True)
        self.assertEqual(self.rabbit.main_photo, main)
        self.assertEqual(list(self.rabbit.photos.all()), [main, first])

    def test_no_main_photo(self):
        add_photo(self.rabbit)
        self.assertIsNone(self.rabbit.main_photo)


class PhotoServingTests(PhotoTestCase):
    def test_the_owner_sees_the_photo(self):
        photo = add_photo(self.rabbit, is_main=True)
        response = self.client.get(reverse("rabbit_photo_file", args=[photo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Cache-Control"], "private, max-age=3600")
        self.assertEqual(b"".join(response.streaming_content)[:8], b"\x89PNG\r\n\x1a\n")

    def test_anyone_else_gets_nothing(self):
        photo = add_photo(self.rabbit)
        url = reverse("rabbit_photo_file", args=[photo.pk])
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_there_is_no_public_media_url(self):
        photo = add_photo(self.rabbit)
        with override_settings(DEBUG=True):
            self.assertEqual(self.client.get("/media/" + photo.image.name).status_code, 404)

    def test_a_missing_file_is_a_404(self):
        photo = add_photo(self.rabbit)
        photo.image.storage.delete(photo.image.name)
        self.assertEqual(self.client.get(reverse("rabbit_photo_file", args=[photo.pk])).status_code, 404)

    def test_detail_shows_the_main_photo(self):
        add_photo(self.rabbit)
        detail = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk]))
        self.assertNotContains(detail, "main photo")
        main = add_photo(self.rabbit, is_main=True)
        detail = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk]))
        self.assertContains(detail, f'src="{reverse("rabbit_photo_file", args=[main.pk])}?v=')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PhotoMigrationTests(TransactionTestCase):
    """0009 turns each Rabbit.photo into a main RabbitPhoto, and back."""

    before = [("rabbits", "0008_rabbit_color_is_standard")]
    after = [("rabbits", "0009_rabbit_photos")]

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        # Keep every other app at its latest state, so their models match the tables.
        others = [node for node in executor.loader.graph.leaf_nodes() if node[0] != "rabbits"]
        executor.migrate(target + others)
        return executor.loader.project_state(target + others).apps

    def tearDown(self):
        self.migrate(executor_latest())

    def test_existing_photos_become_main_photos_and_back(self):
        apps = self.migrate(self.before)
        OldUser = apps.get_model("accounts", "User")
        OldRabbit = apps.get_model("rabbits", "Rabbit")
        owner = OldUser.objects.create(email="old@example.com", is_active=True, email_confirmed=True, password="!")
        fields = dict(owner=owner, sex="doe", breed="Dutch", color="Black", birth_date=datetime.date(2024, 3, 1))
        with_photo = OldRabbit.objects.create(name="Pictured", photo="rabbits/1/abc.png", **fields)
        OldRabbit.objects.create(name="Plain", **fields)

        apps = self.migrate(self.after)
        NewPhoto = apps.get_model("rabbits", "RabbitPhoto")
        photos = list(NewPhoto.objects.all())
        self.assertEqual(len(photos), 1)
        self.assertEqual((photos[0].rabbit_id, photos[0].image.name, photos[0].is_main), (with_photo.pk, "rabbits/1/abc.png", True))

        apps = self.migrate(self.before)
        self.assertEqual(apps.get_model("rabbits", "Rabbit").objects.get(pk=with_photo.pk).photo.name, "rabbits/1/abc.png")


def executor_latest():
    executor = MigrationExecutor(connection)
    return executor.loader.graph.leaf_nodes()


from django.core.exceptions import ValidationError  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client  # noqa: E402

from rabbits import photo_processing  # noqa: E402


def jpeg_with_location(size=(40, 20)):
    """A JPEG carrying a GPS position, a camera name and a 'rotate' flag."""
    exif = Image.Exif()
    exif[0x010F] = "SecretCam"  # camera make
    exif[0x0112] = 6  # orientation: rotate 90 degrees to show upright
    gps = exif.get_ifd(0x8825)
    gps.update({1: "N", 2: (40.0, 26.0, 46.0), 3: "W", 4: (79.0, 58.0, 56.0)})
    return image_bytes("JPEG", size=size, exif=exif.tobytes())


def upload(data, name="photo.jpg", content_type="image/jpeg"):
    return SimpleUploadedFile(name, data, content_type=content_type)


class PhotoProcessingTests(TestCase):
    def cleaned(self, data, name="photo.jpg"):
        return photo_processing.clean_photo(upload(data, name))

    def test_location_and_camera_details_are_removed(self):
        original = jpeg_with_location()
        self.assertIn(b"SecretCam", original)
        self.assertEqual(Image.open(BytesIO(original)).getexif().get_ifd(0x8825)[1], "N")
        cleaned = self.cleaned(original).read()
        self.assertNotIn(b"SecretCam", cleaned)
        self.assertNotIn(b"Exif", cleaned)
        result = Image.open(BytesIO(cleaned))
        self.assertEqual(result.format, "JPEG")
        self.assertEqual(dict(result.getexif()), {})

    def test_the_picture_is_turned_upright_first(self):
        result = Image.open(BytesIO(self.cleaned(jpeg_with_location(size=(40, 20))).read()))
        self.assertEqual(result.size, (20, 40))

    def test_png_text_and_webp_metadata_are_dropped(self):
        from PIL import PngImagePlugin

        info = PngImagePlugin.PngInfo()
        info.add_text("Location", "Grandma's farm")
        buffer = BytesIO()
        Image.new("RGB", (8, 8), "white").save(buffer, format="PNG", pnginfo=info)
        cleaned = self.cleaned(buffer.getvalue(), "photo.png")
        self.assertEqual(cleaned.name, "photo.png")
        self.assertNotIn(b"Grandma", cleaned.read())
        exif = Image.Exif()
        exif[0x010F] = "SecretCam"
        webp = self.cleaned(image_bytes("WEBP", exif=exif.tobytes()), "photo.webp")
        self.assertEqual(webp.name, "photo.webp")
        self.assertNotIn(b"SecretCam", webp.read())

    def test_big_pictures_are_shrunk(self):
        result = Image.open(BytesIO(self.cleaned(image_bytes("JPEG", size=(4000, 1000))).read()))
        self.assertEqual(result.size, (2560, 640))

    def test_other_types_are_refused(self):
        for fmt in ("BMP", "GIF", "TIFF"):
            with self.subTest(fmt=fmt), self.assertRaisesMessage(ValidationError, photo_processing.WRONG_TYPE):
                self.cleaned(image_bytes(fmt), "photo.jpg")

    def test_a_file_that_is_not_an_image_is_refused(self):
        with self.assertRaisesMessage(ValidationError, photo_processing.UNREADABLE):
            self.cleaned(b"<?php echo 'hi'; ?>", "photo.jpg")
        truncated = image_bytes("JPEG", size=(64, 64))[:200]
        with self.assertRaisesMessage(ValidationError, photo_processing.UNREADABLE):
            self.cleaned(truncated)

    def test_size_limits(self):
        big = upload(image_bytes("PNG"))
        big.size = photo_processing.MAX_UPLOAD_BYTES + 1
        with self.assertRaisesMessage(ValidationError, photo_processing.TOO_BIG):
            photo_processing.clean_photo(big)
        with self.assertRaisesMessage(ValidationError, photo_processing.TOO_MANY_PIXELS):
            self.cleaned(image_bytes("PNG", size=(8000, 7000), color="black"), "photo.png")


class PhotoPageTests(PhotoTestCase):
    def page(self):
        return reverse("rabbit_photos", args=[self.rabbit.pk])

    def send(self, data=None, notes="", name="IMG_0001.JPG"):
        return self.client.post(self.page(), {"image": upload(data or jpeg_with_location(), name), "notes": notes})

    def test_the_page_offers_an_upload(self):
        page = self.client.get(self.page())
        self.assertContains(page, 'enctype="multipart/form-data"')
        self.assertContains(page, 'accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif"')
        self.assertContains(page, "No photos yet.")
        # The browser shrinks big photos before upload (Vercel caps requests near 4.5 MB).
        self.assertContains(page, "data-photo-upload")
        self.assertNotContains(page, "<textarea")
        self.assertContains(page, f"Photos of {self.rabbit.name}</h1>")
        self.assertContains(page, f'href="{reverse("rabbit_detail", args=[self.rabbit.pk])}"')
        self.assertContains(page, 'name="back_to" value="photos"')
        self.assertContains(self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk])), f'href="{self.page()}"')

    def test_the_first_upload_becomes_the_main_photo(self):
        response = self.send(notes="  At the spring show  ")
        first = RabbitPhoto.objects.get()
        self.assertRedirects(response, f"{self.page()}#photo-{first.pk}", fetch_redirect_response=False)
        self.assertTrue(first.is_main)
        self.assertEqual(first.notes, "At the spring show")
        self.assertRegex(first.image.name, rf"^rabbit-photos/{self.owner.pk}/[0-9a-f]{{32}}\.jpg$")
        with first.image.open("rb") as handle:
            self.assertNotIn(b"SecretCam", handle.read())
        page = self.client.get(self.page())
        self.assertContains(page, "main photo, since it&#x27;s the first one")
        self.send()
        self.assertEqual(RabbitPhoto.objects.filter(is_main=True).count(), 1)
        self.assertEqual(self.rabbit.photos.count(), 2)

    def test_problems_are_explained(self):
        missing = self.client.post(self.page(), {"notes": "x"}, follow=True)
        self.assertContains(missing, "An upload needs a photo. Please choose one from your device.")
        wrong = self.client.post(self.page(), {"image": SimpleUploadedFile("photo.gif", image_bytes("GIF"))}, follow=True)
        self.assertContains(wrong, "A photo needs to be a JPEG, PNG, WebP or HEIC image.")
        long_notes = self.send(notes="x" * 501)
        self.assertRedirects(long_notes, self.page(), fetch_redirect_response=False)
        self.assertFalse(RabbitPhoto.objects.exists())

    def test_notes_can_be_changed(self):
        photo = add_photo(self.rabbit, notes="Old")
        url = reverse("rabbit_photo_notes", args=[photo.pk])
        self.assertRedirects(self.client.post(url, {"notes": " New notes "}), f"{self.page()}#photo-{photo.pk}")
        photo.refresh_from_db()
        self.assertEqual(photo.notes, "New notes")
        response = self.client.post(url, {"notes": "x" * 501}, follow=True)
        self.assertContains(response, "Notes can be up to 500 characters.")
        photo.refresh_from_db()
        self.assertEqual(photo.notes, "New notes")
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_deleting_removes_the_file_and_keeps_a_main_photo(self):
        main = add_photo(self.rabbit, is_main=True)
        older = add_photo(self.rabbit)
        newer = add_photo(self.rabbit)
        storage, name = main.image.storage, main.image.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("rabbit_photo_delete", args=[main.pk]), follow=True)
        self.assertContains(response, "The oldest remaining photo is now the main photo.")
        self.assertFalse(storage.exists(name))
        older.refresh_from_db()
        newer.refresh_from_db()
        self.assertTrue(older.is_main)
        self.assertFalse(newer.is_main)
        self.client.post(reverse("rabbit_photo_delete", args=[newer.pk]))
        older.refresh_from_db()
        self.assertTrue(older.is_main)

    def test_only_the_owner_can_see_or_change_photos(self):
        photo = add_photo(self.rabbit, is_main=True, notes="Mine")
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.page()).status_code, 404)
        self.assertEqual(self.send().status_code, 404)
        self.assertEqual(self.client.post(reverse("rabbit_photo_notes", args=[photo.pk]), {"notes": "Theirs"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("rabbit_photo_delete", args=[photo.pk])).status_code, 404)
        photo.refresh_from_db()
        self.assertEqual(photo.notes, "Mine")
        self.assertEqual(RabbitPhoto.objects.count(), 1)

    def test_changes_need_a_csrf_token(self):
        photo = add_photo(self.rabbit)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(reverse("rabbit_photo_delete", args=[photo.pk])).status_code, 403)
        self.assertEqual(strict.post(self.page(), {"image": upload(jpeg_with_location())}).status_code, 403)
        self.assertTrue(RabbitPhoto.objects.filter(pk=photo.pk).exists())


class SetMainPhotoTests(PhotoTestCase):
    def set_main(self, photo):
        return self.client.post(reverse("rabbit_photo_set_main", args=[photo.pk]))

    def test_a_photo_can_become_the_main_photo(self):
        old_main = add_photo(self.rabbit, is_main=True)
        extra = add_photo(self.rabbit)
        page = reverse("rabbit_photos", args=[self.rabbit.pk])
        self.assertContains(self.client.get(page), f'action="{reverse("rabbit_photo_set_main", args=[extra.pk])}"')
        self.assertNotContains(self.client.get(page), f'action="{reverse("rabbit_photo_set_main", args=[old_main.pk])}"')
        response = self.set_main(extra)
        self.assertRedirects(response, f"{page}#photo-{extra.pk}", fetch_redirect_response=False)
        self.assertContains(self.client.get(page), "This is now Clover&#x27;s main photo.")
        old_main.refresh_from_db()
        extra.refresh_from_db()
        self.assertTrue(extra.is_main)
        self.assertFalse(old_main.is_main)
        self.assertEqual(self.rabbit.main_photo, extra)

    def test_without_a_main_photo_any_photo_can_become_it(self):
        photo = add_photo(self.rabbit)
        self.set_main(photo)
        photo.refresh_from_db()
        self.assertTrue(photo.is_main)
        self.set_main(photo)
        self.assertEqual(self.rabbit.photos.filter(is_main=True).count(), 1)

    def test_only_the_owner_with_a_post(self):
        main = add_photo(self.rabbit, is_main=True)
        extra = add_photo(self.rabbit)
        self.assertEqual(self.client.get(reverse("rabbit_photo_set_main", args=[extra.pk])).status_code, 405)
        self.client.force_login(self.stranger)
        self.assertEqual(self.set_main(extra).status_code, 404)
        main.refresh_from_db()
        self.assertTrue(main.is_main)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(reverse("rabbit_photo_set_main", args=[extra.pk])).status_code, 403)


class PhotoDisplayTests(PhotoTestCase):
    def detail(self):
        return self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk]))

    def src(self, photo):
        return f'src="{reverse("rabbit_photo_file", args=[photo.pk])}?v='

    def test_detail_photos_card_shows_tiles_with_main_first_and_notes(self):
        older = add_photo(self.rabbit, notes="Six weeks old")
        main = add_photo(self.rabbit, is_main=True, notes="Best of breed, spring show")
        newer = add_photo(self.rabbit)
        page = self.detail()
        body = page.content.decode()
        self.assertContains(page, "Best of breed, spring show")
        self.assertContains(page, "Six weeks old")
        card = body[body.index('id="gallery-heading"'):]
        tile = lambda photo: card.index(f'id="photo-{photo.pk}"')
        self.assertLess(card.index("Add photo"), tile(main))
        self.assertLess(tile(main), tile(older))
        self.assertLess(tile(older), tile(newer))
        self.assertEqual(card.count(">Main</span>"), 1)
        self.assertEqual(card.count("Make main"), 2)
        self.assertContains(page, 'name="back_to" value="detail"')

    def test_detail_empty_states(self):
        self.assertContains(self.detail(), "No photos yet.")
        add_photo(self.rabbit, is_main=True)
        self.assertNotContains(self.detail(), "No photos yet.")

    def test_list_cards_show_the_main_photo(self):
        main = add_photo(self.rabbit, is_main=True)
        add_photo(self.rabbit)
        plain = make_rabbit(self.owner, name="Basil")
        add_photo(plain)  # an extra only, so no thumbnail
        page = self.client.get(reverse("rabbit_list"))
        self.assertContains(page, self.src(main), count=1)
        self.assertContains(page, "Open </span>Clover")
        self.assertContains(page, "Open </span>Basil")
        self.assertContains(page, ">B</span>")

    def test_the_list_loads_photos_in_one_query(self):
        for number in range(5):
            rabbit = make_rabbit(self.owner, name=f"Rabbit {number}")
            add_photo(rabbit, is_main=True)
            add_photo(rabbit)
        self.client.get(reverse("rabbit_list"))  # warm the session
        with self.assertNumQueries(5):
            # session, user, rabbits, photos, and one for the tab counts and breed filter
            self.client.get(reverse("rabbit_list"))

    def test_another_keepers_list_shows_none_of_these_photos(self):
        main = add_photo(self.rabbit, is_main=True)
        self.client.force_login(self.stranger)
        self.assertNotContains(self.client.get(reverse("rabbit_list")), self.src(main))
