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
        self.assertContains(self.names("oldest")[1], '<option value="-age" selected>Oldest first</option>', html=True)
        self.assertEqual(self.names("-age")[0], ["Old", "Mid", "Young"])

    def test_list_headers_toggle_and_mark_the_active_column(self):
        page = self.client.get(reverse("rabbit_list"), {"sort": "-age", "view": "list"})
        body = page.content.decode()
        age = body[body.index('data-sort-key="age"') - 120:body.index('data-sort-key="age"') + 200]
        self.assertIn('aria-sort="descending"', age)
        self.assertIn('href="?sort=age"', age)  # click again: ascending
        self.assertIn("↓", age)
        self.assertEqual(self.names("name")[0], ["Mid", "Old", "Young"])

    def test_unknown_sort_is_ignored_and_unknown_birth_goes_last(self):
        from .views import sort_by_age
        r = [Rabbit(name="A", birth_date=None), Rabbit(name="B", birth_date=date(2020, 1, 1))]
        self.assertEqual([x.name for x in sort_by_age(r, "youngest")], ["B", "A"])
        self.assertEqual(self.client.get(reverse("rabbit_list"), {"sort": "bogus"}).status_code, 200)


class SortingHelperTests(PhotoTestCase):
    def test_parse_headers_and_none_last(self):
        from . import sorting
        self.assertEqual(sorting.parse("-age", {"age": 1}), ("age", True))
        self.assertEqual(sorting.parse("bogus", {"age": 1}, default="-age"), ("age", True))
        h = sorting.headers([("age", "Age"), ("name", "Name")], "age", True, {"q": "x"}, {"name"})
        self.assertEqual((h[0]["aria"], h[0]["href"]), ("descending", "?q=x&sort=age"))
        self.assertEqual((h[1]["aria"], h[1]["href"]), ("none", "?q=x&sort=-name"))
        rows = [{"v": None}, {"v": 2}, {"v": 1}]
        self.assertEqual([r["v"] for r in sorting.apply(rows, {"v": lambda r: r["v"]}, "v", True)], [2, 1, None])
        self.assertEqual([r["v"] for r in sorting.apply(rows, {"v": lambda r: r["v"]}, "v", False)], [1, 2, None])
