"""The photos card on the add-a-rabbit flow, and the breed sample photos."""

import json
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings

from . import breed_samples, flow, flow_photos
from .models import Breed, Rabbit, RabbitPhoto
from .test_flow_rules import FlowTestMixin
from .test_photos import image_bytes, upload

MEDIA_ROOT = Path(tempfile.mkdtemp())


class StepOrderTests(TestCase):
    def test_photos_follow_the_breed_and_relatives_come_just_before_the_review(self):
        self.assertEqual(flow.SLUGS, ["name", "sex", "birth-date", "status", "breed-type", "breed", "photos",
                                      "color", "genes", "relatives", "review"])
        self.assertNotIn("photos", flow.EDIT_SLUGS)
        self.assertEqual(flow.EDIT_SLUGS[-2:], ["relatives", "line"])


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class FlowPhotoTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        session = self.client.session
        session[flow.SESSION_KEY] = self.draft(color="", step="photos")
        session.save()

    def tearDown(self):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def files(self, *names):
        return [upload(image_bytes("JPEG", (30 + i, 20)), name=n) for i, n in enumerate(names)]

    def stored(self):
        return flow.load_draft(self.client.session)["photos"]

    def test_picked_files_keep_their_order_and_the_first_is_main(self):
        response = self.client.post("/rabbits/new/photos/", {"action": "upload", "photos": self.files("a.jpg", "b.jpg", "c.jpg")})
        self.assertRedirects(response, "/rabbits/new/photos/#photos", fetch_redirect_response=False)
        self.assertEqual([p["label"] for p in self.stored()], ["a.jpg", "b.jpg", "c.jpg"])
        page = self.client.get("/rabbits/new/photos/").content.decode()
        self.assertEqual(page.count(">Main<"), 1)
        self.assertIn('value="photo-main-1"', page)
        self.assertNotIn("data-breed-sample", page)
        thumb = self.client.get("/rabbits/new/photo/0/")
        self.assertEqual(thumb.status_code, 200)
        self.assertEqual(self.client.get("/rabbits/new/photo/9/").status_code, 404)

    def test_set_main_reorder_and_remove(self):
        self.client.post("/rabbits/new/photos/", {"action": "upload", "photos": self.files("a.jpg", "b.jpg", "c.jpg")})
        self.client.post("/rabbits/new/photos/", {"action": "photo-main-2"})
        self.assertEqual([p["label"] for p in self.stored()], ["c.jpg", "a.jpg", "b.jpg"])
        self.client.post("/rabbits/new/photos/", {"action": "photo-down-1"})
        self.assertEqual([p["label"] for p in self.stored()], ["c.jpg", "b.jpg", "a.jpg"])
        self.client.post("/rabbits/new/photos/", {"action": "order", "order": "2,0,1"}, HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual([p["label"] for p in self.stored()], ["a.jpg", "c.jpg", "b.jpg"])
        gone = self.stored()[0]["name"]
        self.client.post("/rabbits/new/photos/", {"action": "photo-remove-0"})
        self.assertEqual([p["label"] for p in self.stored()], ["c.jpg", "b.jpg"])
        self.assertFalse(default_storage.exists(gone))

    def test_next_with_files_uploads_them_without_js_and_bad_files_are_named(self):
        bad = upload(b"not an image", name="notes.txt", content_type="text/plain")
        response = self.client.post("/rabbits/new/photos/", {"action": "next", "photos": [*self.files("a.jpg"), bad]})
        self.assertRedirects(response, "/rabbits/new/photos/#photos", fetch_redirect_response=False)
        self.assertEqual(len(self.stored()), 1)
        page = self.client.get("/rabbits/new/photos/")
        self.assertContains(page, "notes.txt:")
        response = self.client.post("/rabbits/new/photos/", {"action": "next", "photos": self.files("b.jpg")})
        self.assertRedirects(response, "/rabbits/new/color/", fetch_redirect_response=False)
        self.assertEqual(len(self.stored()), 2)

    def test_skipping_is_fine(self):
        response = self.client.post("/rabbits/new/photos/", {"action": "next"})
        self.assertRedirects(response, "/rabbits/new/color/", fetch_redirect_response=False)

    def test_saving_the_rabbit_attaches_them_in_order_with_the_first_as_main(self):
        self.client.post("/rabbits/new/photos/", {"action": "upload", "photos": self.files("a.jpg", "b.jpg")})
        draft = flow.load_draft(self.client.session)
        draft["color"] = "Black"
        pending = [p["name"] for p in draft["photos"]]
        rabbit = flow.save_rabbit(draft, self.user)
        photos = list(RabbitPhoto.objects.filter(rabbit=rabbit).order_by("uploaded_at", "pk"))
        self.assertEqual(len(photos), 2)
        self.assertEqual([p.is_main for p in photos], [True, False])
        self.assertFalse(any(default_storage.exists(name) for name in pending))
        self.assertFalse(any("breeds/" in p.image.name for p in photos))

    def test_starting_over_removes_pending_files(self):
        self.client.post("/rabbits/new/photos/", {"action": "upload", "photos": self.files("a.jpg")})
        name = self.stored()[0]["name"]
        self.client.post("/rabbits/new/restart/")
        self.assertFalse(default_storage.exists(name))

    def test_draft_rows_outside_the_pending_folder_are_dropped(self):
        rows = [{"name": "rabbit-photos/1/x.jpg"}, {"name": "flow-pending/1/../../x.jpg"}, {"name": "flow-pending/1/ok.jpg", "label": "ok"}]
        self.assertEqual([r["name"] for r in flow_photos.clean_photos(rows)], ["flow-pending/1/ok.jpg"])


class BreedSampleTests(TestCase):
    def test_manifest_lists_only_open_licenses_with_credit_and_existing_files(self):
        data = json.loads(breed_samples.MANIFEST.read_text())
        self.assertGreaterEqual(len(data), 15)
        static = Path(settings.BASE_DIR) / "static"
        for name, row in data.items():
            self.assertRegex(row["license"], breed_samples.ALLOWED_LICENSE, name)
            self.assertNotIn("SA", row["license"], name)
            self.assertTrue(row["source"].startswith("https://commons.wikimedia.org/wiki/File:"), name)
            self.assertTrue(row["author"], name)
            self.assertTrue(row["file"].endswith(".webp"), name)
            self.assertTrue((static / row["file"]).exists(), name)

    def test_sample_for_a_breed_with_a_photo_and_a_silhouette_otherwise(self):
        cal, _ = Breed.objects.get_or_create(name="Californian", defaults={"registry": "arba"})
        sample = breed_samples.sample_for(cal)
        self.assertTrue(sample["is_photo"])
        self.assertIn("Wikimedia Commons", sample["credit"])
        odd, _ = Breed.objects.get_or_create(name="Thrianta", defaults={"registry": "arba"})
        self.assertEqual(breed_samples.sample_for(odd), {"file": breed_samples.SILHOUETTE, "is_photo": False, "breed": "Thrianta"})
        self.assertFalse(breed_samples.sample_for(None)["is_photo"])
