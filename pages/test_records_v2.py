"""Records (Critic v2 item 8): Health gets a pinned Add note and stacked rows on phones; Costs
gets a pinned New cost."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rabbits.models import HealthNote, Rabbit, Task


class RecordsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("records@example.com", "pw-12345678")
        self.client.force_login(self.user)
        self.rabbit = Rabbit.objects.create(owner=self.user, name="Willow", sex="doe", breed="Rex", birth_date=datetime.date(2024, 1, 1))
        Rabbit.objects.create(owner=self.user, name="Gone", sex="doe", breed="Rex", birth_date=datetime.date(2024, 1, 1), status="sold")

    def pinned(self, body, label):
        self.assertEqual(body.count("pin-main"), 1)
        tag = body[body.rindex("<", 0, body.index("pin-main")):]
        self.assertIn(label, tag[:tag.index("</a>")])

    def test_health_pins_add_a_note(self):
        body = self.client.get(reverse("health_list")).content.decode()
        self.pinned(body, "Add note")
        self.assertIn(f'href="{reverse("health_new")}" data-modal', body)

    def test_costs_pins_new_cost(self):
        from decimal import Decimal
        from rabbits.models import Expense
        Expense.objects.create(owner=self.user, date=datetime.date(2026, 10, 1), description="Hay", amount=Decimal("12.00"))
        self.pinned(self.client.get(reverse("cost_list")).content.decode(), "New cost")

    def test_health_list_stacks_on_phones(self):
        HealthNote.objects.create(rabbit=self.rabbit, date=timezone.localdate(), kind="illness", notes="Sneezing")
        body = self.client.get(reverse("health_list")).content.decode()
        self.assertIn('class="wt-card it-rows max-md:hidden"', body)
        stack = body[body.index('class="wt-card it-stack md:hidden"'):]
        self.assertIn("Sneezing", stack[:stack.index("</ul>")])

    def test_new_note_form_lists_herd_rabbits_only(self):
        page = self.client.get(reverse("health_new"))
        self.assertEqual(page.context["rabbit_options"], [(str(self.rabbit.pk), "Willow")])

    def test_new_note_saves_and_returns_to_health(self):
        day = timezone.localdate()
        response = self.client.post(reverse("health_new"), {"rabbit": self.rabbit.pk, "health_date": day.isoformat(), "health_kind": "illness",
                                                            "notes": "Sneezing", "health_follow_up": (day + datetime.timedelta(days=3)).isoformat()})
        self.assertRedirects(response, reverse("health_list"), fetch_redirect_response=False)
        note = HealthNote.objects.get(rabbit=self.rabbit)
        self.assertEqual((note.kind, note.notes), ("illness", "Sneezing"))
        self.assertTrue(Task.objects.filter(pk=note.task_id).exists())

    def test_new_note_needs_a_rabbit_and_valid_fields(self):
        response = self.client.post(reverse("health_new"), {"health_date": timezone.localdate().isoformat(), "health_kind": "illness"}, follow=True)
        self.assertContains(response, "Choose the rabbit this note is for.")
        response = self.client.post(reverse("health_new"), {"rabbit": self.rabbit.pk, "health_date": "", "health_kind": "illness"})
        self.assertRedirects(response, reverse("health_new"), fetch_redirect_response=False)
        self.assertFalse(HealthNote.objects.exists())

    def test_someone_elses_rabbit_is_refused(self):
        other = get_user_model().objects.create_user("o@example.com", "pw-12345678")
        theirs = Rabbit.objects.create(owner=other, name="Theirs", sex="doe", breed="Rex", birth_date=datetime.date(2024, 1, 1))
        self.client.post(reverse("health_new"), {"rabbit": theirs.pk, "health_date": timezone.localdate().isoformat(), "health_kind": "illness"})
        self.assertFalse(HealthNote.objects.exists())

    def test_health_strings(self):
        HealthNote.objects.all().delete()
        body = self.client.get(reverse("health_list")).content.decode()
        self.assertIn("Add a note here or from a rabbit's page. Set a follow-up date to see it on Today.", body)
        self.assertIn(">Add note<", body.replace("</svg>", ">").replace(">>", ">"))
        body = self.client.get(reverse("health_new")).content.decode()
        self.assertIn("Add health note", body)
        self.assertIn(">Choose a rabbit</option>", body)
        self.assertNotIn("Choose a rabbit…", body)
        Rabbit.objects.filter(owner=self.user).delete()
        body = self.client.get(reverse("health_new")).content.decode()
        self.assertIn("Add a rabbit first. Each health note belongs to a rabbit.", body)

    def test_rabbit_page_says_add_health_note(self):
        body = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk])).content.decode()
        self.assertIn("Add health note", body)
        self.assertNotIn("Add a health note", body)
