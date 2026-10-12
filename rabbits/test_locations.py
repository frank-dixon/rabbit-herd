import datetime

from django.test import TestCase
from django.urls import reverse

from .models import Location, Rabbit
from .test_contacts import user


class LocationTests(TestCase):
    def setUp(self):
        self.owner = user("loc@example.com")
        self.client.force_login(self.owner)
        make = lambda name: Rabbit.objects.create(owner=self.owner, name=name, sex="doe", birth_date=datetime.date(2025, 1, 1))
        self.hazel, self.fern = make("Hazel"), make("Fern")

    def test_add_rename_and_remove_locations(self):
        self.client.post(reverse("location_list"), {"name": "  Hutch   3 ", "notes": "Top row"})
        hutch = Location.objects.get()
        self.assertEqual((hutch.owner, hutch.name, hutch.notes), (self.owner, "Hutch 3", "Top row"))
        dup = self.client.post(reverse("location_list"), {"name": "hutch 3"}, follow=True)
        self.assertContains(dup, "You already have a location called hutch 3.")
        self.assertContains(self.client.post(reverse("location_list"), {"name": " "}, follow=True), "A location needs a name")
        self.client.post(reverse("location_edit", args=[hutch.pk]), {"name": "Hutch 4", "action": "save"})
        hutch.refresh_from_db()
        self.assertEqual(hutch.name, "Hutch 4")
        self.hazel.location = hutch
        self.hazel.save()
        self.client.post(reverse("location_edit", args=[hutch.pk]), {"action": "delete"})
        self.hazel.refresh_from_db()
        self.assertIsNone(self.hazel.location)
        self.assertTrue(Rabbit.objects.filter(pk=self.hazel.pk).exists())

    def test_assign_on_the_rabbit_including_a_new_location(self):
        hutch = Location.objects.create(owner=self.owner, name="Hutch 1")
        url = reverse("rabbit_location", args=[self.hazel.pk])
        self.client.post(url, {"location": hutch.pk})
        self.hazel.refresh_from_db()
        self.assertEqual(self.hazel.location, hutch)
        page = self.client.get(reverse("rabbit_detail", args=[self.hazel.pk]))
        self.assertContains(page, "data-location>Hutch 1")
        self.client.post(url, {"location": "", "new_location": "Barn row A"})
        self.hazel.refresh_from_db()
        self.assertEqual(self.hazel.location.name, "Barn row A")
        self.client.post(url, {"location": ""})
        self.hazel.refresh_from_db()
        self.assertIsNone(self.hazel.location)

    def test_the_list_filters_by_location(self):
        hutch = Location.objects.create(owner=self.owner, name="Hutch 1")
        self.hazel.location = hutch
        self.hazel.save()
        names = lambda **p: sorted(r.name for r in self.client.get(reverse("rabbit_list"), p).context["rabbits"])
        self.assertEqual(names(location=hutch.pk), ["Hazel"])
        self.assertEqual(names(location="none"), ["Fern"])
        self.assertEqual(names(location="junk"), ["Fern", "Hazel"])
        self.assertContains(self.client.get(reverse("rabbit_list")), '<option value="none">No location</option>', html=True)
        self.assertContains(self.client.get(reverse("location_list")), "1 rabbit")

    def test_other_owners_locations_are_off_limits(self):
        theirs = Location.objects.create(owner=user("other@example.com"), name="Theirs")
        self.client.post(reverse("rabbit_location", args=[self.hazel.pk]), {"location": theirs.pk})
        self.hazel.refresh_from_db()
        self.assertIsNone(self.hazel.location)
        self.assertEqual(self.client.post(reverse("location_edit", args=[theirs.pk]), {"action": "delete"}).status_code, 404)
        self.assertNotContains(self.client.get(reverse("location_list")), "Theirs")

    def test_locations_are_in_the_nav_and_under_more_on_phones(self):
        page = self.client.get(reverse("location_list")).content.decode()
        self.assertRegex(page, r'href="/locations/"[^>]*aria-current="page"')
        more = self.client.get(reverse("account"))
        self.assertContains(more, 'aria-label="More sections"')
        self.assertContains(more, 'href="/locations/"')
