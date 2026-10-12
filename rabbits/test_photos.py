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
        self.assertContains(detail, f'src="{reverse("rabbit_photo_file", args=[main.pk])}"')


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
