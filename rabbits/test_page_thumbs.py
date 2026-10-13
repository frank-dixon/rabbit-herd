"""Every page about one rabbit shows its main photo beside the title, or the
initial square when it has none."""

import re

from django.urls import reverse

from .test_photos import PhotoTestCase, add_photo, make_rabbit, make_user


class PageThumbTests(PhotoTestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_user("thumbs@example.com")
        self.client.force_login(self.owner)
        self.with_photo = make_rabbit(self.owner, "Clover")
        add_photo(self.with_photo, notes="not main")
        self.main = add_photo(self.with_photo, is_main=True)
        self.without = make_rabbit(self.owner, "Pepper")

    def pages(self, rabbit):
        return [
            reverse("rabbit_edit", args=[rabbit.pk]),
            reverse("rabbit_edit_step", args=[rabbit.pk, "name"]),
            reverse("rabbit_edit_step", args=[rabbit.pk, "line"]),
            reverse("rabbit_photos", args=[rabbit.pk]),
            reverse("rabbit_delete", args=[rabbit.pk]),
            reverse("rabbit_edit_step", args=[rabbit.pk, "genes"]),
        ]

    def thumb(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        found = re.search(r"data-page-thumb>\s*(<[^>]+>)", response.content.decode())
        self.assertIsNotNone(found, url)
        return found.group(1)

    def test_the_main_photo_shows_through_the_checked_photo_view(self):
        src = reverse("rabbit_photo_file", args=[self.main.pk])
        for url in self.pages(self.with_photo):
            tag = self.thumb(url)
            self.assertIn(f'src="{src}?v=', tag, url)
            self.assertIn("object-cover", tag, url)
            self.assertIn('alt=""', tag, url)

    def test_no_photo_shows_the_initial_square(self):
        for url in self.pages(self.without):
            tag = self.thumb(url)
            self.assertTrue(tag.startswith("<span"), url)
            self.assertIn('aria-hidden="true"', tag, url)
            self.assertContains(self.client.get(url), ">P</span>")

    def test_another_owner_gets_no_page_and_no_photo(self):
        self.client.force_login(make_user("other@example.com"))
        for url in self.pages(self.with_photo):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertEqual(self.client.get(reverse("rabbit_photo_file", args=[self.main.pk])).status_code, 404)
