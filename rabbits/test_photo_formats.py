"""Uploads as phones and Macs really send them: MPO (iPhone multi-picture
JPEG) and large files."""

import os
from io import BytesIO

from django.urls import reverse
from PIL import Image

from rabbits.models import RabbitPhoto
from rabbits.test_photos import PhotoTestCase, upload


def mpo_bytes(size=(64, 48)):
    buffer = BytesIO()
    first, second = Image.new("RGB", size, "white"), Image.new("RGB", size, "black")
    first.save(buffer, format="MPO", save_all=True, append_images=[second])
    return buffer.getvalue()

def noise_jpeg():
    picture = Image.frombytes("RGB", (2000, 1500), os.urandom(2000 * 1500 * 3))
    buffer = BytesIO()
    picture.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()

class PhotoFormatTests(PhotoTestCase):
    def page(self):
        return reverse("rabbit_photos", args=[self.rabbit.pk])

    def send(self, data, name, content_type="image/jpeg"):
        return self.client.post(self.page(), {"image": upload(data, name, content_type)})

    def stored_format(self):
        with RabbitPhoto.objects.get().image.open("rb") as handle:
            return Image.open(BytesIO(handle.read())).format

    def test_iphone_mpo_jpeg_is_saved_as_jpeg(self):
        data = mpo_bytes()
        self.assertEqual(Image.open(BytesIO(data)).format, "MPO")
        self.assertEqual(self.send(data, "IMG_2299.jpeg").status_code, 302)
        self.assertEqual(self.stored_format(), "JPEG")

    def test_a_large_upload_spooled_to_disk_is_saved(self):
        data = noise_jpeg()
        self.assertGreater(len(data), 2_621_440)
        self.assertEqual(self.send(data, "IMG_2299.jpeg").status_code, 302)
        self.assertEqual(self.stored_format(), "JPEG")
