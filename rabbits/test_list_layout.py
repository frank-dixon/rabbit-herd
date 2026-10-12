from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Rabbit


class RabbitListLayoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("keeper@example.com", "pw-12345678")
        self.client.force_login(self.user)
        Rabbit.objects.create(
            owner=self.user, name="Blackberry", sex="buck", color="Black",
            breed="Cross: 50% Creme d'Argent, 25% Flemish Giant, 25% New Zealand",
            birth_date=date(2025, 3, 1),
        )

    def test_grid_is_the_default_with_short_breed_full_name_status_and_letter(self):
        page = self.client.get(reverse("rabbit_list"))
        self.assertEqual(page.context["view"], "grid")
        self.assertContains(page, 'data-view="grid"')
        self.assertNotContains(page, 'data-view="list"')
        self.assertContains(page, "Cross · Creme d&#x27;Argent 50% +2 more")
        self.assertContains(page, "Blackberry")
        self.assertNotContains(page, "truncate")
        self.assertContains(page, "Breeding")
        self.assertContains(page, "1 active rabbit in your herd")
        self.assertContains(page, "max-w-6xl")

    def test_view_param_switches_to_list_and_is_remembered(self):
        page = self.client.get(reverse("rabbit_list"), {"view": "list"})
        self.assertContains(page, 'data-view="list"')
        self.assertContains(page, 'href="?view=grid"')
        again = self.client.get(reverse("rabbit_list"))
        self.assertEqual(again.context["view"], "list")
        # The grid is still in the page for phones and tablets, hidden on desktop.
        self.assertContains(again, "lg:grid-cols-4 lg:hidden")
        back = self.client.get(reverse("rabbit_list"), {"view": "grid"})
        self.assertNotContains(back, 'data-view="list"')

    def test_unknown_view_value_is_ignored(self):
        page = self.client.get(reverse("rabbit_list"), {"view": "table"})
        self.assertEqual(page.context["view"], "grid")


class ArchivedLayoutTests(TestCase):
    def test_archived_page_uses_wide_header_and_rows(self):
        from django.utils import timezone

        user = get_user_model().objects.create_user("old@example.com", "pw-12345678")
        self.client.force_login(user)
        Rabbit.objects.create(
            owner=user, name="Clover", sex="doe", color="Black", breed="Rex",
            birth_date=date(2024, 1, 1), archived_at=timezone.now(),
        )
        page = self.client.get(reverse("rabbit_archived"))
        self.assertContains(page, "max-w-6xl")
        self.assertContains(page, "Archived rabbits")
        self.assertContains(page, "Restore<span class=\"sr-only\"> Clover</span>")
