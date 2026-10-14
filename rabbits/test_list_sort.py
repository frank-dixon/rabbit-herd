from datetime import date

from django.urls import reverse

from .models import Rabbit
from .test_photos import PhotoTestCase, make_user


class AgeSortTests(PhotoTestCase):
    def setUp(self):
        self.owner = make_user("sort@example.com")
        self.client.force_login(self.owner)
        for name, born in (("Mid", date(2024, 5, 1)), ("Old", date(2021, 1, 1)), ("Young", date(2026, 8, 1))):
            Rabbit.objects.create(owner=self.owner, name=name, sex="doe", breed="Rex", color="Black", birth_date=born)

    def names(self, sort):
        page = self.client.get(reverse("rabbit_list"), {"sort": sort})
        return [r.name for r in page.context["rabbits"]], page

    def test_oldest_and_youngest_first(self):
        self.assertEqual(self.names("oldest")[0], ["Old", "Mid", "Young"])
        self.assertEqual(self.names("youngest")[0], ["Young", "Mid", "Old"])
        self.assertContains(self.names("oldest")[1], '<option value="oldest" selected>Oldest first</option>', html=True)

    def test_unknown_sort_is_ignored_and_unknown_birth_goes_last(self):
        from .views import sort_by_age
        r = [Rabbit(name="A", birth_date=None), Rabbit(name="B", birth_date=date(2020, 1, 1))]
        self.assertEqual([x.name for x in sort_by_age(r, "youngest")], ["B", "A"])
        self.assertEqual(self.client.get(reverse("rabbit_list"), {"sort": "bogus"}).status_code, 200)
