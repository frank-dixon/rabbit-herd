from io import BytesIO

from django.core.files.base import ContentFile
from django.urls import reverse
from PIL import Image

from .models import RabbitPhoto
from .renditions import rendition_name
from .test_photos import PhotoTestCase, image_bytes


class RenditionTests(PhotoTestCase):
    def big_photo(self):
        photo = RabbitPhoto(rabbit=self.rabbit, is_main=True)
        photo.image.save("big.png", ContentFile(image_bytes(size=(2000, 1500))), save=False)
        photo.save()
        return photo

    def test_width_param_serves_a_smaller_webp_and_caches_it(self):
        photo = self.big_photo()
        url = reverse("rabbit_photo_file", args=[photo.pk])
        response = self.client.get(url, {"w": "320", "v": "x"})
        self.assertEqual(response["Content-Type"], "image/webp")
        self.assertIn("immutable", response["Cache-Control"])
        img = Image.open(BytesIO(b"".join(response.streaming_content)))
        self.assertEqual(img.size, (320, 240))
        self.assertTrue(photo.image.storage.exists(rendition_name(photo.image.name, 320)))

    def test_unknown_width_falls_back_to_original(self):
        photo = self.big_photo()
        response = self.client.get(reverse("rabbit_photo_file", args=[photo.pk]), {"w": "999"})
        self.assertEqual(response["Content-Type"], "image/png")

    def test_strangers_get_nothing(self):
        photo = self.big_photo()
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(reverse("rabbit_photo_file", args=[photo.pk]), {"w": "320"}).status_code, 404)

    def test_delete_removes_copies(self):
        photo = self.big_photo()
        self.client.get(reverse("rabbit_photo_file", args=[photo.pk]), {"w": "640"})
        name, storage = photo.image.name, photo.image.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("rabbit_photo_delete", args=[photo.pk]))
        self.assertFalse(storage.exists(rendition_name(name, 640)))

    def test_list_and_detail_use_srcset_and_lazy_loading(self):
        photo = self.big_photo()
        listing = self.client.get(reverse("rabbit_list")).content.decode()
        self.assertIn("&amp;w=320 320w", listing)
        self.assertIn('loading="lazy"', listing)
        detail = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk])).content.decode()
        self.assertIn('fetchpriority="high"', detail)
        self.assertIn(f"/photos/{photo.pk}/?v=", detail)


class PrefetchTests(PhotoTestCase):
    def test_prefetch_leaves_messages_for_the_real_visit(self):
        self.client.post(reverse("rabbit_archive", args=[self.rabbit.pk]))
        url = reverse("rabbit_list")
        self.client.get(url, headers={"Sec-Purpose": "prefetch"})
        real = self.client.get(url)
        self.assertTrue(list(real.context["messages"]))
        self.assertFalse(list(self.client.get(url).context["messages"]))
