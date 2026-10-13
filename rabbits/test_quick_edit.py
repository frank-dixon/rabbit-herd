"""One-card edits from the rabbit page: each fact links to its card, and saving
it updates the rabbit at once (in place with JS, as a plain form without)."""

from django.test import TestCase
from django.urls import reverse

from .test_flow_rules import FlowTestMixin


class QuickEditTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.rabbit = self.juniper
        self.detail = reverse("rabbit_detail", args=[self.rabbit.pk])

    def url(self, slug):
        return reverse("rabbit_quick_edit", args=[self.rabbit.pk, slug])

    def test_detail_rows_link_to_their_card_and_mark_inline_fields(self):
        page = self.client.get(self.detail).content.decode()
        facts = page[page.index("data-facts"):page.index("</dl>", page.index("data-facts"))]
        for slug in ("sex", "breed", "color", "line", "birth-date", "status"):
            self.assertIn(f'href="{self.url(slug)}"', facts, slug)
        for name in ("line", "birth_date", "tattoo"):
            self.assertIn(f'data-inline-name="{name}"', facts)
        self.assertIn('href="#location"', facts)

    def test_card_has_save_and_cancel(self):
        page = self.client.get(self.url("line"))
        self.assertContains(page, ">Save<")
        self.assertContains(page, ">Cancel<")
        self.assertContains(page, f'action="{self.url("line")}"')

    def test_plain_post_saves_and_returns_to_the_page(self):
        response = self.client.post(self.url("line"), {"line": "Whitmore", "action": "next"})
        self.assertRedirects(response, self.detail + "#facts", fetch_redirect_response=False)
        self.rabbit.refresh_from_db()
        self.assertEqual(self.rabbit.line, "Whitmore")

    def test_inline_post_saves_one_field_and_keeps_the_rest(self):
        name = self.rabbit.name
        response = self.client.post(self.url("name"), {"tattoo": "NZ-014", "action": "next"},
                                    headers={"X-Requested-With": "fetch"})
        self.assertEqual(response.json(), {"saved": True})
        self.rabbit.refresh_from_db()
        self.assertEqual((self.rabbit.name, self.rabbit.tattoo), (name, "NZ-014"))

    def test_inline_errors_come_back_as_json_and_nothing_saves(self):
        before = self.rabbit.birth_date
        response = self.client.post(self.url("birth-date"), {"birth_date": "2999-01-01", "action": "next"},
                                    headers={"X-Requested-With": "fetch"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("birth_date", response.json()["errors"])
        self.rabbit.refresh_from_db()
        self.assertEqual(self.rabbit.birth_date, before)

    def test_cancel_saves_nothing(self):
        response = self.client.post(self.url("line"), {"line": "Nope", "action": "back"})
        self.assertRedirects(response, self.detail + "#facts", fetch_redirect_response=False)
        self.rabbit.refresh_from_db()
        self.assertNotEqual(self.rabbit.line, "Nope")

    def test_other_owners_cannot_open_it(self):
        from django.contrib.auth import get_user_model
        other = get_user_model().objects.create_user(email="other-q@example.com", password="x-strong-Pass-1")
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url("line")).status_code, 404)
        self.assertEqual(self.client.post(self.url("line"), {"line": "x"}).status_code, 404)

    def test_an_older_rabbit_with_missing_answers_can_still_fix_one_row(self):
        from .models import Rabbit
        old = Rabbit.objects.create(owner=self.user, name="Oldie", sex="doe", breed="Rex", birth_date="2024-02-02")
        response = self.client.post(reverse("rabbit_quick_edit", args=[old.pk, "line"]), {"line": "Hale", "action": "next"},
                                    headers={"X-Requested-With": "fetch"})
        self.assertEqual(response.json(), {"saved": True})
        old.refresh_from_db()
        self.assertEqual(old.line, "Hale")
