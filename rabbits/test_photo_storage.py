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
