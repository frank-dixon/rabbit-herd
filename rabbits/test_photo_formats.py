"""Uploads as phones and Macs really send them: HEIC named .jpeg, MPO
(iPhone multi-picture JPEG), large files, and a post built from the
rendered form itself."""

import os
from html.parser import HTMLParser
from io import BytesIO

from django.test import Client
from django.urls import reverse
from PIL import Image

from rabbits.models import RabbitPhoto
from rabbits.test_photos import PhotoTestCase, upload


def heic_bytes(size=(64, 48), color="white"):
    import pillow_heif

    buffer = BytesIO()
    pillow_heif.from_pillow(Image.new("RGB", size, color)).save(buffer, quality=60)
    return buffer.getvalue()


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


class _FormFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms, self._current = [], None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self._current = {"attrs": attrs, "inputs": []}
            self.forms.append(self._current)
        elif self._current is not None and tag in ("input", "textarea"):
            self._current["inputs"].append((tag, attrs))

    def handle_endtag(self, tag):
        if tag == "form":
            self._current = None


class PhotoFormatTests(PhotoTestCase):
    def page(self):
        return reverse("rabbit_photos", args=[self.rabbit.pk])

    def send(self, data, name, content_type="image/jpeg"):
        return self.client.post(self.page(), {"image": upload(data, name, content_type)})

    def stored_format(self):
        with RabbitPhoto.objects.get().image.open("rb") as handle:
            return Image.open(BytesIO(handle.read())).format

    def test_heic_named_jpeg_is_saved_as_jpeg(self):
        response = self.send(heic_bytes(), "IMG_2299.jpeg")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.stored_format(), "JPEG")
        self.assertTrue(RabbitPhoto.objects.get().image.name.endswith(".jpg"))

    def test_heic_with_its_own_name_and_type_is_saved_as_jpeg(self):
        self.assertEqual(self.send(heic_bytes(), "IMG_2299.HEIC", "image/heic").status_code, 302)
        self.assertEqual(self.stored_format(), "JPEG")

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

    def test_the_rendered_form_posts_the_file(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.owner)
        page = self.client.get(self.page())
        finder = _FormFinder()
        finder.feed(page.content.decode())
        upload_forms = [f for f in finder.forms if any(a.get("type") == "file" for _, a in f["inputs"])]
        self.assertEqual(len(upload_forms), 1)
        form = upload_forms[0]
        self.assertEqual(form["attrs"].get("enctype"), "multipart/form-data")
        self.assertEqual(form["attrs"].get("method"), "post")
        action = form["attrs"].get("action") or self.page()
        fields = {}
        for tag, attrs in form["inputs"]:
            if attrs.get("type") == "file":
                fields[attrs["name"]] = upload(heic_bytes(), "IMG_2299.jpeg")
            elif attrs.get("name"):
                fields[attrs["name"]] = attrs.get("value", "")
        self.assertIn("csrfmiddlewaretoken", fields)
        response = self.client.post(action, fields)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.stored_format(), "JPEG")

    def test_the_picker_offers_heic(self):
        self.assertContains(self.client.get(self.page()), "image/heic")
