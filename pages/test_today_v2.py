"""Today (Critic v2 item 9): pairings and litters in one list with one row shape, and a Tasks badge
that says what it counts."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rabbits.models import Litter, Pairing, Rabbit, Task


class TodayListTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("today2@example.com", "pw-12345678")
        self.client.force_login(self.user)
        mk = lambda name, sex: Rabbit.objects.create(owner=self.user, name=name, sex=sex, breed="Rex", birth_date=datetime.date(2024, 1, 1))
        doe, doe2, buck = mk("Willow", "doe"), mk("Fern", "doe"), mk("Jet", "buck")
        today = timezone.localdate()
        Litter.objects.create(owner=self.user, pairing=Pairing.objects.create(owner=self.user, doe=doe, buck=buck), bred_on=today - datetime.timedelta(days=12))
        Litter.objects.create(owner=self.user, pairing=Pairing.objects.create(owner=self.user, doe=doe2, buck=buck),
                              bred_on=today - datetime.timedelta(days=50), kindled_on=today - datetime.timedelta(days=19), born_alive=6)
        Task.objects.create(owner=self.user, title="Clean cages", due_on=today - datetime.timedelta(days=1))
        Task.objects.create(owner=self.user, title="Order hay", due_on=today)
        self.body = self.client.get(reverse("index")).content.decode()

    def test_pairings_and_litters_are_one_list(self):
        block = self.body[self.body.index("data-pairings-progress"):]
        block = block[:block.index("</section>")]
        self.assertEqual(block.count("<ul"), 1)
        self.assertEqual(block.count("<li>"), 2)
        self.assertIn("data-progress-row", block)
        self.assertIn('<span class="block">12</span><span class="block text-muted">of 31</span>', block)
        self.assertIn('<span class="sr-only">12 of 31 done</span>', block)
        self.assertIn("day 19", block)
        self.assertEqual(block.count('class="flex shrink-0"'), 2)  # both rows show the pair

    def test_tasks_badge_says_what_it_counts(self):
        badge = self.body[self.body.index("data-badge"):]
        badge = badge[:badge.index("</span></span>")]
        self.assertIn('title="Overdue or due today"', badge)
        self.assertRegex(badge, r">[0-9]+<")
        self.assertIn('<span class="sr-only"> overdue or due today', badge)

    def test_overdue_group_carries_the_badge_number(self):
        badge = self.body[self.body.index("data-badge"):]
        number = badge[badge.index(">") + 1:badge.index("<")]
        group = self.body[self.body.index("data-due-now-count"):]
        self.assertEqual(group[group.index(">") + 1:group.index("<")], number)
        self.assertIn('title="Overdue or due today" data-due-now-count', self.body)
