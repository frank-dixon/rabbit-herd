from datetime import date
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import OutsideRabbit, Rabbit, RabbitPhoto, Relative

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class DeleteRabbitTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("o@example.com", "pw-12345678")
        self.client.force_login(self.user)
        self.rabbit = self.make(self.user, "Speedwell")
        self.url = reverse("rabbit_delete", args=[self.rabbit.pk])

    def make(self, user, name):
        return Rabbit.objects.create(owner=user, name=name, sex="buck", breed="Rex", color="Black", birth_date=date(2025, 1, 1))

    def test_detail_has_delete_link_and_dialog(self):
        page = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk]))
        self.assertContains(page, f'href="{self.url}" data-delete-open="delete-dialog"')
        self.assertContains(page, '<dialog id="delete-dialog"')
        self.assertContains(page, "Type 'delete Speedwell' to confirm")

    def test_confirm_page_works_without_js(self):
        page = self.client.get(self.url)
        self.assertContains(page, "Type 'delete Speedwell' to confirm")
        self.assertNotContains(page, "disabled")

    def test_wrong_text_is_refused_by_the_server(self):
        response = self.client.post(self.url, {"confirm": "delete Speed"})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Rabbit.objects.filter(pk=self.rabbit.pk).exists())

    def test_get_never_deletes(self):
        self.client.get(self.url, {"confirm": "delete Speedwell"})
        self.assertTrue(Rabbit.objects.filter(pk=self.rabbit.pk).exists())

    def test_other_owner_gets_404(self):
        other = get_user_model().objects.create_user("x@example.com", "pw-12345678")
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url, {"confirm": "delete Speedwell"}).status_code, 404)
        self.assertTrue(Rabbit.objects.filter(pk=self.rabbit.pk).exists())

    def test_matching_text_deletes_photos_and_relative_links(self):
        buf = BytesIO()
        Image.new("RGB", (20, 20), "white").save(buf, "JPEG")
        photo = RabbitPhoto(rabbit=self.rabbit, is_main=True)
        photo.image.save("a.jpg", ContentFile(buf.getvalue()), save=True)
        storage, name = photo.image.storage, photo.image.name
        kit = self.make(self.user, "Kit")
        Relative.objects.create(rabbit=kit, relationship="sire", herd_rabbit=self.rabbit)
        Relative.objects.create(
            rabbit=self.rabbit, relationship="dam", outside=OutsideRabbit.objects.create(owner=self.user, name="Snow")
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {"confirm": "  DELETE   speedwell "})
        self.assertRedirects(response, reverse("rabbit_list"), fetch_redirect_response=False)
        self.assertFalse(Rabbit.objects.filter(pk=self.rabbit.pk).exists())
        self.assertFalse(storage.exists(name))
        self.assertFalse(Relative.objects.filter(herd_rabbit_id=self.rabbit.pk).exists())
        self.assertTrue(Rabbit.objects.filter(pk=kit.pk).exists())
        self.assertContains(self.client.get(reverse("rabbit_list")), "Speedwell was deleted.")
