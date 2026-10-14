from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .models import OutsideRabbit, PedigreeEntry, Relative
from .test_photos import PhotoTestCase, image_bytes, make_rabbit, make_user


class AncestorThumbTests(PhotoTestCase):
    def setUp(self):
        self.owner = make_user("anc@example.com")
        self.client.force_login(self.owner)
        self.kit = make_rabbit(self.owner, "Kit")
        self.out = OutsideRabbit.objects.create(owner=self.owner, name="Old Coal", details="Black buck · Kessler · KNZ1")
        Relative.objects.create(rabbit=self.kit, relationship="sire", outside=self.out)
        PedigreeEntry.objects.create(rabbit=self.kit, position="s", outside=self.out)

    def test_placeholder_is_coat_matched_and_tagged(self):
        page = self.client.get(reverse("rabbit_pedigree", args=[self.kit.pk]))
        self.assertContains(page, "placeholders/newborn-dark")
        self.assertContains(page, "data-placeholder-tag")
        self.assertContains(page, f'data-outside-photo="{self.out.pk}"')
        self.assertContains(self.client.get(reverse("rabbit_detail", args=[self.kit.pk])), "placeholders/newborn-dark")

    def test_set_photo_then_it_shows_and_others_cannot_see_it(self):
        upload = SimpleUploadedFile("coal.png", image_bytes(size=(64, 64)), content_type="image/png")
        back = reverse("rabbit_pedigree", args=[self.kit.pk])
        self.assertRedirects(self.client.post(reverse("outside_photo", args=[self.out.pk]), {"photo": upload, "next": back}),
                             back, fetch_redirect_response=False)
        self.out.refresh_from_db()
        self.assertTrue(self.out.photo)
        page = self.client.get(back)
        self.assertContains(page, reverse("outside_photo", args=[self.out.pk]) + "?w=")
        self.assertEqual(self.client.get(reverse("outside_photo", args=[self.out.pk])).status_code, 200)
        self.client.force_login(make_user("other@example.com"))
        self.assertEqual(self.client.get(reverse("outside_photo", args=[self.out.pk])).status_code, 404)
