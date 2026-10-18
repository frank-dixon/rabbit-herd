"""Row targets (Critic v2 item 6): rows open on a tap, and one 44px row menu replaces the 20px
pencil and trash icons. Weights can be edited from their row."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from rabbits.models import Expense, Rabbit, Weight


class RowMenuTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("rows@example.com", "pw-12345678")
        self.client.force_login(self.user)
        self.rabbit = Rabbit.objects.create(owner=self.user, name="Willow", sex="doe", breed="Rex", birth_date=datetime.date(2024, 1, 1))
        self.weight = Weight.objects.create(rabbit=self.rabbit, date=datetime.date(2026, 10, 1), grams=Decimal("3401.94"), unit="lb_oz", note="")

    def test_detail_weight_rows_open_and_carry_one_menu(self):
        body = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk])).content.decode()
        row = body[body.index("data-weight-list"):]
        row = row[:row.index("</ul>")]
        self.assertIn("data-row-tap", row)
        self.assertIn('class="row-menu-btn"', row)
        self.assertIn(f'href="?weight={self.weight.pk}#weights" data-modal="weights" data-row-open', row)
        self.assertNotIn("icon-btn", row)

    def test_no_template_uses_the_small_icon_buttons(self):
        from pathlib import Path
        for path in (Path(__file__).resolve().parents[1] / "templates").rglob("*.html"):
            self.assertNotIn('class="icon-btn', path.read_text(), path.name)

    def test_row_menu_targets_are_44px(self):
        from pathlib import Path
        css = (Path(__file__).resolve().parents[1] / "assets" / "components.css").read_text()
        self.assertRegex(css, r"\.row-menu-btn \{[^}]*width: 44px; height: 44px;")
        self.assertRegex(css, r"\.row-menu-item \{[^}]*min-height: 44px;")

    def test_edit_prefills_and_saves_a_weight(self):
        page = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk]) + f"?weight={self.weight.pk}")
        self.assertEqual(page.context["weight_values"]["lb"], "7")
        self.assertEqual(page.context["weight_values"]["oz"], "8")
        body = page.content.decode()
        self.assertIn(reverse("rabbit_weight_edit", args=[self.weight.pk]), body)
        self.assertIn("Edit weight", body)
        response = self.client.post(reverse("rabbit_weight_edit", args=[self.weight.pk]), {"date": "2026-10-02", "lb": "8", "oz": "0", "note": "After show"})
        self.assertRedirects(response, f"/rabbits/{self.rabbit.pk}/#weights", fetch_redirect_response=False)
        self.weight.refresh_from_db()
        self.assertEqual((self.weight.date, round(float(self.weight.grams)), self.weight.note), (datetime.date(2026, 10, 2), 3629, "After show"))
        toast = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertEqual(len(toast), 1)
        self.assertRegex(toast[0], r"^\S.* saved for Oct 2\.$")

    def test_a_bad_edit_keeps_the_form_on_that_weight(self):
        response = self.client.post(reverse("rabbit_weight_edit", args=[self.weight.pk]), {"date": "", "lb": "8"})
        self.assertRedirects(response, f"/rabbits/{self.rabbit.pk}/?weight={self.weight.pk}#weights", fetch_redirect_response=False)
        page = self.client.get(response["Location"].split("#")[0])
        self.assertEqual(page.context["weight_editing"], self.weight)
        self.assertTrue(page.context["weight_errors"])

    def test_someone_elses_weight_is_not_found(self):
        other = get_user_model().objects.create_user("other@example.com", "pw-12345678")
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse("rabbit_weight_edit", args=[self.weight.pk]), {"date": "2026-10-02", "lb": "1"}).status_code, 404)

    def test_cost_rows_open_and_use_the_menu(self):
        Expense.objects.create(owner=self.user, date=datetime.date(2026, 10, 1), description="Hay", amount=Decimal("12.00"))
        body = self.client.get(reverse("cost_list")).content.decode()
        self.assertIn('data-row data-row-tap', body)
        self.assertIn("row-menu-btn", body)
