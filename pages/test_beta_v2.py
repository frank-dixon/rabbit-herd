"""Beta review v2 layout rules: past pairings fold away, one pinned main action per long
list page, and side-menu icons that hold still on hover."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rabbits.models import Litter, Pairing, Rabbit


class BetaV2LayoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("v2@example.com", "pw-12345678")
        self.client.force_login(self.user)
        mk = lambda name, sex: Rabbit.objects.create(owner=self.user, name=name, sex=sex, breed="Rex", birth_date=datetime.date(2024, 1, 1))
        self.doe, self.doe2, self.buck = mk("Willow", "doe"), mk("Fern", "doe"), mk("Jet", "buck")
        today = timezone.localdate()
        done = Pairing.objects.create(owner=self.user, doe=self.doe, buck=self.buck)
        Litter.objects.create(owner=self.user, pairing=done, bred_on=today - datetime.timedelta(days=120),
                              kindled_on=today - datetime.timedelta(days=89), converted_at=timezone.now())
        Pairing.objects.create(owner=self.user, doe=self.doe2, buck=self.buck)

    def test_finished_pairings_fold_into_past_pairings(self):
        page = self.client.get(reverse("pairing_list"))
        self.assertEqual([it["pill"]["label"] for it in page.context["items"]], ["Planned"])
        self.assertEqual(len(page.context["past"]), 1)
        body = page.content.decode()
        self.assertIn("Past pairings (1)", body)
        fold = body[body.index('id="past-pairings"'):]
        self.assertNotIn(" open", fold[:fold.index(">")])  # closed by default
        self.assertIn("Willow", fold)

    def test_one_pinned_main_action_on_long_list_pages(self):
        for name, label in (("rabbit_list", "Add"), ("pairing_list", "New pairing"), ("task_list", "New task"), ("weights_hub", "Weigh a group")):
            body = self.client.get(reverse(name)).content.decode()
            self.assertEqual(body.count("pin-main"), 1, name)
            tag = body[body.rindex("<", 0, body.index("pin-main")):]
            self.assertIn(label, tag[:tag.index("</")+600], name)

    def test_side_menu_icons_do_not_move_on_hover(self):
        body = self.client.get(reverse("index")).content.decode()
        self.assertIn("data-rail-key", body)
        self.assertNotIn("group-hover/rail:translate", body)

    def test_weights_page_carries_one_log_form_not_one_per_row(self):
        body = self.client.get(reverse("weights_hub")).content.decode()
        self.assertEqual(body.count("data-weight-log-template"), 1)
        self.assertEqual(body.count("<form class=\"popover wt-log-pop\""), 1)
        self.assertEqual(body.count("data-weight-log-panel"), body.count("data-weight-log-fallback"))
        self.assertGreaterEqual(body.count("data-weight-log-fallback"), 3)

    def test_no_template_comment_leaks_into_pages(self):
        for name in ("index", "rabbit_list", "pairing_list", "task_list", "weights_hub", "litter_list"):
            body = self.client.get(reverse(name)).content.decode()
            self.assertNotIn("{#", body, name)
            self.assertNotIn("#}", body, name)
