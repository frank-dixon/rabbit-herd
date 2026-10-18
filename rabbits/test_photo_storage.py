"""Settings pick photo storage from PHOTO_STORAGE, and photos are streamed
through the owner-checked view whatever the backend is."""

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BASE = Path(__file__).resolve().parent.parent

PROBE = (
    "import django, json; django.setup();"
    "from django.conf import settings;"
    "from django.core.files.storage import default_storage as d;"
    "print(json.dumps([settings.STORAGES['default']['BACKEND'],"
    " getattr(d, 'addressing_style', None), getattr(d, 'default_acl', 'x'),"
    " getattr(d, 'bucket_name', None)]))"
)


def probe(**env):
    full = {k: v for k, v in os.environ.items() if not k.startswith(("PHOTO_", "VERCEL"))}
    full.setdefault("DEBUG", "1")
    full.update(env, DJANGO_SETTINGS_MODULE="rabbit_herd.settings")
    out = subprocess.run([sys.executable, "-c", PROBE], cwd=BASE, env=full,
                         capture_output=True, text=True, check=True)
    import json
    return json.loads(out.stdout.strip().splitlines()[-1])


class PhotoStorageSettingsTests(SimpleTestCase):
    def test_local_filesystem_by_default(self):
        backend, *_ = probe()
        self.assertEqual(backend, "django.core.files.storage.FileSystemStorage")

    def test_s3_when_asked_private_and_path_style(self):
        backend, style, acl, bucket = probe(
            PHOTO_STORAGE="s3", PHOTO_S3_BUCKET="rabbit-photos",
            PHOTO_S3_ENDPOINT_URL="https://example.invalid/storage/v1/s3",
            PHOTO_S3_ACCESS_KEY_ID="test-id", PHOTO_S3_SECRET_ACCESS_KEY="test-secret",
        )
        self.assertEqual(backend, "storages.backends.s3.S3Storage")
        self.assertEqual(style, "path")
        self.assertIsNone(acl)
        self.assertEqual(bucket, "rabbit-photos")


class SignedPhotoUrlTests(SimpleTestCase):
    """With S3, the owner-checked view answers with a short-lived signed link."""

    def test_signed_redirect_after_owner_check(self):
        from unittest import mock

        from django.test import RequestFactory, override_settings

        from rabbits import photo_delivery

        storage = mock.Mock()
        storage.url.return_value = "https://bucket.example/rabbit-photos/1/x.webp?X-Amz-Signature=abc"
        request = RequestFactory().get("/rabbits/photos/1/?w=320&v=1")
        with override_settings(PHOTO_SIGNED_URLS=True, PHOTO_SIGNED_URL_SECONDS=3600):
            response = photo_delivery.deliver(request, storage, "rabbit-photos/1/x.w320.webp")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://bucket.example/"))
        storage.url.assert_called_once_with(
            "rabbit-photos/1/x.w320.webp", parameters={"ResponseContentType": "image/webp"}, expire=3600)
        self.assertEqual(response["Cache-Control"], "private, max-age=3300")
        storage.open.assert_not_called()

    def test_local_files_still_stream(self):
        from unittest import mock

        from django.test import RequestFactory, override_settings

        from rabbits import photo_delivery

        storage = mock.Mock()
        storage.open.return_value = __import__("io").BytesIO(b"img")
        with override_settings(PHOTO_SIGNED_URLS=False):
            response = photo_delivery.deliver(RequestFactory().get("/x/?v=1"), storage, "a.jpg")
        self.assertEqual(response.status_code, 200)
        self.assertIn("immutable", response["Cache-Control"])
        storage.url.assert_not_called()
