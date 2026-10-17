import shutil
import tempfile
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from PIL import Image

from . import litter_kits as K
from .litter_photos import placeholder_key
from .models import Litter
from .test_litter_convert import ConvertTests

MEDIA_ROOT = Path(tempfile.mkdtemp())


class PlaceholderPickTests(TestCase):
    def test_broken_wins_then_shared_or_known_coat_then_doe_then_empty_nest(self):
        cases = [
            (("Broken black", "Castor"), "broken"),
            (("Black", "Charlie"), "broken"),
            (("Black", "Chocolate"), "dark"),
            (("Ruby-eyed white", "Castor"), "pink"),
            (("Chestnut agouti", "Lilac"), "blue"),
            (("Fawn", "Black"), "red"),
            (("Castor", "Opal"), "default"),
            (("", ""), "default"),
        ]
        for (doe, buck), want in cases:
            with self.subTest(doe=doe, buck=buck):
                self.assertEqual(placeholder_key(doe, buck), want)


def jpeg():
    out = BytesIO()
    Image.new("RGB", (8, 8), "red").save(out, "JPEG")
    return ContentFile(out.getvalue(), name="p.jpg")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ArchiveOnConvertTests(ConvertTests):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_convert_archives_litter_and_kits_keep_their_photo(self):
        slots = self.slots("doe", "buck", "doe")
        self.litter.photo.save("l.jpg", jpeg())
        slots[0].photo.save("k.jpg", jpeg())
        K.convert(self.litter.pk, self.owner)
        own, inherited = (Litter.objects.get(pk=self.litter.pk).slots.get(number=n).rabbit for n in (1, 2))
        self.assertEqual(own.photos.get(is_main=True).image.read(), slots[0].photo.open("rb").read())
        self.assertTrue(inherited.photos.filter(is_main=True).exists())
        self.client.force_login(self.owner)
        # A converted litter is a past litter: it sits in the Past table, and ?archived=1 lands there.
        page = self.client.get("/litters/")
        self.assertContains(page, f'data-past-litter="{self.litter.pk}"')
        self.assertRedirects(self.client.get("/litters/?archived=1"), "/litters/#past", fetch_redirect_response=False)
        page = self.client.get(f"/litters/{self.litter.pk}/")
        self.assertContains(page, "archived and read-only")
        self.assertContains(page, "Kits at conversion")
        self.assertNotContains(page, "Change photo")
