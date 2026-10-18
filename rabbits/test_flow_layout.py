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

    def test_add_card_uses_wide_page_with_back_left_and_next_right(self):
        page = self.client.get(reverse("rabbit_flow_step", args=["name"]), follow=True)
        self.assertContains(page, "max-w-6xl")
        self.assertContains(page, "v2-card-wide")
        row = self.row(page)
        self.assertIn('value="next"', row)
        self.assertNotIn("flex-row-reverse", row[:300])
        page = self.client.post(reverse("rabbit_flow_step", args=["name"]), {"action": "next", "name": "Clover"}, follow=True)
        row = self.row(page)
        self.assertLess(row.index('value="back"'), row.index('value="next"'))  # Back left, Next right

    def test_two_tiles_with_hints_stack_on_phones(self):
        html = (__import__("pathlib").Path(__file__).resolve().parents[1] / "templates" / "components" / "choice_tiles.html").read_text()
        self.assertIn("{% elif tiles|length == 2 and not tiles.0.hint and not tiles.1.hint %}grid-cols-2{% else %}grid-cols-1 sm:grid-cols-2", html)

    def test_edit_summary_header_with_cancel_left_and_save_right(self):
        rabbit = Rabbit.objects.create(
            owner=self.user, name="Hazel", sex="doe", breed="Rex", color="Black", birth_date=date(2025, 1, 1)
        )
        page = self.client.get(reverse("rabbit_edit", args=[rabbit.pk]))
        self.assertContains(page, "max-w-6xl")
        self.assertContains(page, "data-back-link")
        self.assertContains(page, "Hazel\n    </a>")
        row = self.row(page)
        self.assertIn('value="save" class="sr-only"', row)  # Enter still saves
        self.assertLess(row.index('value="discard"'), row.rindex('value="save"'))
