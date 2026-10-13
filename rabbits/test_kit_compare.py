import datetime

from django.urls import reverse

from .models import Litter, Pairing, Rabbit
from .test_contacts import user
from .test_photos import PhotoTestCase, add_photo


class KitCompareTests(PhotoTestCase):
    def setUp(self):
        self.owner = user("kits@example.com")
        self.client.force_login(self.owner)
        born = datetime.date(2026, 6, 1)
        base = {"owner": self.owner, "breed": "Dutch", "color": "Black"}
        doe = Rabbit.objects.create(name="Mom", sex="doe", birth_date=datetime.date(2024, 1, 1), **base)
        buck = Rabbit.objects.create(name="Dad", sex="buck", birth_date=datetime.date(2024, 1, 1), **base)
        self.litter = Litter.objects.create(owner=self.owner, pairing=Pairing.objects.create(owner=self.owner, doe=doe, buck=buck),
                                            bred_on=datetime.date(2026, 5, 1), kindled_on=born, born_alive=3)
        self.ash = Rabbit.objects.create(name="Ash", sex="doe", birth_date=born, litter=self.litter, **base)
        self.birch = Rabbit.objects.create(name="Birch", sex="buck", birth_date=born, litter=self.litter, **base)
        self.url = reverse("litter_compare", args=[self.litter.pk])

    def photo(self, kit, day):
        photo = add_photo(kit)
        photo.taken_at = day
        photo.save()
        return photo

    def test_rows_by_age_and_date(self):
        a3 = self.photo(self.ash, datetime.date(2026, 6, 22))       # 3 weeks
        b3 = self.photo(self.birch, datetime.date(2026, 6, 24))     # 3 weeks
        b3_later = self.photo(self.birch, datetime.date(2026, 6, 25))
        a8 = self.photo(self.ash, datetime.date(2026, 7, 28))       # 8 weeks
        page = self.client.get(self.url)
        rows = page.context["rows"]
        self.assertEqual([label for label, _ in rows], ["3 weeks", "8 weeks"])
        self.assertEqual(rows[0][1], [[a3], [b3_later, b3]])
        self.assertEqual(rows[1][1], [[a8], []])
        self.assertContains(page, "1 more")
        self.assertContains(page, "No photo")
        by_date = self.client.get(self.url + "?by=date").context["rows"]
        self.assertEqual([label for label, _ in by_date], ["Jun 22, 2026", "Jun 24, 2026", "Jun 25, 2026", "Jul 28, 2026"])

    def test_link_and_empty_states(self):
        self.assertContains(self.client.get(reverse("litter_detail", args=[self.litter.pk])), "Compare kit photos")
        self.assertContains(self.client.get(self.url), "No kit photos yet")
        Rabbit.objects.filter(litter=self.litter).update(litter=None)
        self.assertContains(self.client.get(self.url), "No kits from this litter")

    def test_owner_only(self):
        self.client.force_login(user("other@example.com"))
        self.assertEqual(self.client.get(self.url).status_code, 404)
