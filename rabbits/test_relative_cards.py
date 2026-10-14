from datetime import date

from django.urls import reverse

from .models import OutsideRabbit, Relative
from .test_photos import PhotoTestCase, add_photo, make_rabbit, make_user


class RelativeCardTests(PhotoTestCase):
    def setUp(self):
        self.owner = make_user("rel@example.com")
        self.client.force_login(self.owner)
        self.kit = make_rabbit(self.owner, "Kit")
        self.sire = make_rabbit(self.owner, "Major")
        self.sire.sex = "buck"
        self.sire.breed = "Cross: 50% Creme d'Argent, 25% Rex, 25% Dutch"
        self.sire.save()
        self.photo = add_photo(self.sire, is_main=True)
        Relative.objects.create(rabbit=self.kit, relationship="sire", herd_rabbit=self.sire, color="Creme")
        Relative.objects.create(
            rabbit=self.kit, relationship="dam", outside=OutsideRabbit.objects.create(owner=self.owner, name="Snow"),
            breed="Florida White", line="Ridgeview",
        )

    def test_cards_show_breed_thumb_and_link(self):
        page = self.client.get(reverse("rabbit_detail", args=[self.kit.pk]))
        self.assertContains(page, "Cross · Creme d&#x27;Argent 50% +2 more")
        self.assertContains(page, "Florida White")
        self.assertContains(page, f'href="{reverse("rabbit_detail", args=[self.sire.pk])}"')
        self.assertContains(page, f'src="{reverse("rabbit_photo_file", args=[self.photo.pk])}?v=')
        self.assertContains(page, "data-placeholder-tag")  # Snow has no photo: stock placeholder

