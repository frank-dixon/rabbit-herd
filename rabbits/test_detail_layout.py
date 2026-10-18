from datetime import date

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Rabbit


class AgeTextTests(SimpleTestCase):
    def age(self, born, today):
        return Rabbit(birth_date=born).age_text(today=today)

    def test_years_and_months(self):
        self.assertEqual(self.age(date(2025, 1, 15), date(2026, 10, 12)), "20 mo")
        self.assertEqual(self.age(date(2025, 1, 15), date(2026, 10, 15)), "21 mo")

    def test_months_only_whole_years_and_newborns(self):
        self.assertEqual(self.age(date(2026, 6, 1), date(2026, 10, 12)), "19 wk")
        self.assertEqual(self.age(date(2024, 10, 12), date(2026, 10, 12)), "2 yr")
        self.assertEqual(self.age(date(2026, 10, 1), date(2026, 10, 12)), "11 days")


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
        # Archive lives in the "…" menu (Critic v3 D6), after History.
        menu = body[body.index("data-more-menu"):body.index("</details>", body.index("data-more-menu"))]
        self.assertIn(f'action="{reverse("rabbit_archive", args=[rabbit.pk])}"', menu)
        self.assertRegex(menu, r'<button type="submit" role="menuitem"[^>]*>Archive</button>')
        self.assertNotIn('label="Archive"', body)
        self.assertEqual(body.count(">Archive</button>"), 1)
        # The phone summary doesn't repeat Sex, Breed and Color from the list below (D2).
        summary = body[body.index("data-fact-summary"):body.index("</dl>", body.index("data-fact-summary"))]
        for label in ("Sex", "Breed", "Color"):
            self.assertNotIn(f"<dt>{label}</dt>", summary)
        self.assertIn("<dt>Latest weight</dt>", summary)
        self.assertNotIn(">Back to rabbits<", body)
        for label in ("Sex", "Breed", "Color", "Line", "Born", "Status"):
            self.assertRegex(body, rf'<dt class="[^"]*">{label}</dt>')
        self.assertContains(page, 'Jan 15, 2025<span class="block text-sm text-muted"')
        self.assertContains(page, "No photos yet.")
        self.assertContains(page, "No parents recorded.")
        # Nothing recorded, but the breed and color imply genes, so the card shows them as Possible.
        self.assertContains(page, 'data-gene-level="possible"')
        self.assertContains(page, 'href="' + reverse("rabbit_edit_step", args=[rabbit.pk, "genes"]) + '"')
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
        self.assertIn(">Add health note</summary>", body.replace("</svg>", ">").replace(">>", ">"))


class PhotoCreditTests(TestCase):
    """Critic v3 V1: no bare "Credit" toggle; the credit text itself shows under the photo."""

    def test_credit_text_shows_without_a_bare_label(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from .models import RabbitPhoto

        user = get_user_model().objects.create_user("credit@example.com", "pw-12345678")
        self.client.force_login(user)
        rabbit = Rabbit.objects.create(owner=user, name="Cinder", sex="doe", breed="Rex", birth_date=date(2025, 1, 1))
        RabbitPhoto.objects.create(rabbit=rabbit, image=SimpleUploadedFile("c.gif", b"GIF89a\x01\x00\x01\x00\x00\x00\x00;", content_type="image/gif"),
                                   notes="Demo photo: A. Person, CC0, via Wikimedia Commons (a doe).", is_main=True)
        body = self.client.get(reverse("rabbit_detail", args=[rabbit.pk])).content.decode()
        self.assertNotIn(">Credit<", body)
        self.assertIn("Demo photo: A. Person, CC0, via Wikimedia Commons (a doe).", body)
