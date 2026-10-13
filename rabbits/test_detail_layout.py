from datetime import date

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Rabbit


class AgeTextTests(SimpleTestCase):
    def age(self, born, today):
        return Rabbit(birth_date=born).age_text(today=today)

    def test_years_and_months(self):
        self.assertEqual(self.age(date(2025, 1, 15), date(2026, 10, 12)), "1 yr 8 mo")
        self.assertEqual(self.age(date(2025, 1, 15), date(2026, 10, 15)), "1 yr 9 mo")

    def test_months_only_whole_years_and_newborns(self):
        self.assertEqual(self.age(date(2026, 6, 1), date(2026, 10, 12)), "4 mo")
        self.assertEqual(self.age(date(2024, 10, 12), date(2026, 10, 12)), "2 yr")
        self.assertEqual(self.age(date(2026, 10, 1), date(2026, 10, 12)), "under 1 mo")


class DetailLayoutTests(TestCase):
    def test_header_details_list_and_short_empty_states(self):
        user = get_user_model().objects.create_user("d@example.com", "pw-12345678")
        self.client.force_login(user)
        rabbit = Rabbit.objects.create(
            owner=user, name="Speedwell", sex="buck", breed="Creme d'Argent", color="Creme",
            status="sold", birth_date=date(2025, 1, 15),
        )
        page = self.client.get(reverse("rabbit_detail", args=[rabbit.pk]))
        body = page.content.decode()
        self.assertContains(page, "max-w-6xl")
        self.assertContains(page, '<h1 class="break-words text-[1.75rem] leading-tight font-semibold md:text-[2.25rem]">Speedwell</h1>')
        # Shared header: a small back link above the title, the thumbnail beside it, Edit last.
        self.assertLess(body.index("data-back-link"), body.index("<h1"))
        self.assertIn("data-page-thumb", body[body.index("data-page-header"):body.index("<h1")])
        self.assertLess(body.index(">Archive<"), body.index(">Edit<"))
        self.assertNotIn(">Back to rabbits<", body)
        for label in ("Sex", "Breed", "Color", "Line", "Born", "Status"):
            self.assertRegex(body, rf'<dt class="[^"]*">{label}</dt>')
        self.assertContains(page, '<span class="num">Jan 15, 2025</span>')
        self.assertContains(page, "No photos yet.")
        self.assertContains(page, "No parents recorded.")
        self.assertContains(page, "No genes recorded.")
        self.assertContains(page, 'href="' + reverse("rabbit_genes", args=[rabbit.pk]) + '"')
        self.assertNotContains(page, "Buck. Creme d&#x27;Argent. Creme. Born")


class FoldTests(TestCase):
    def test_empty_sections_start_closed_and_ones_with_data_open(self):
        from .models import HealthNote
        user = get_user_model().objects.create_user("f@example.com", "pw-12345678")
        self.client.force_login(user)
        rabbit = Rabbit.objects.create(owner=user, name="Fern", sex="doe", breed="Rex", birth_date=date(2025, 1, 1))
        HealthNote.objects.create(rabbit=rabbit, date=date(2026, 1, 2), kind="checkup")
        body = self.client.get(reverse("rabbit_detail", args=[rabbit.pk])).content.decode()
        tag = lambda key: body[body.index(f'id="{key}"') - 60:body.index(f'id="{key}"') + 40]
        self.assertIn("open", tag("health"))
        self.assertNotIn("open", tag("shows"))
        self.assertIn("1 note", body)
        self.assertIn("None yet", body)
        # Add forms sit behind an Add button even when the section is open.
        self.assertIn('data-add-fold>', body)
        self.assertIn(">Add a health note</summary>", body.replace("</svg>", ">").replace(">>", ">"))
