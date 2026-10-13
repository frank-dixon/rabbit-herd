from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Rabbit


class FlowLayoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("f@example.com", "pw-12345678")
        self.client.force_login(self.user)

    def row(self, page):
        body = page.content.decode()
        return body[body.index("data-action-row"):]

    def test_add_card_uses_wide_page_and_puts_next_first(self):
        page = self.client.get(reverse("rabbit_flow_step", args=["name"]), follow=True)
        self.assertContains(page, "max-w-6xl")
        self.assertContains(page, "max-w-2xl")
        row = self.row(page)
        self.assertIn('value="next"', row)
        self.assertNotIn('value="back"', row[: row.index('value="next"')])

    def test_edit_summary_header_and_save_first(self):
        rabbit = Rabbit.objects.create(
            owner=self.user, name="Hazel", sex="doe", breed="Rex", color="Black", birth_date=date(2025, 1, 1)
        )
        page = self.client.get(reverse("rabbit_edit", args=[rabbit.pk]))
        self.assertContains(page, "max-w-6xl")
        self.assertContains(page, "data-back-link")
        self.assertContains(page, "Hazel\n    </a>")
        row = self.row(page)
        self.assertLess(row.index('value="save"'), row.index('value="discard"'))
