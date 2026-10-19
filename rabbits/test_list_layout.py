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

    def test_list_is_the_default_with_the_agreed_row(self):
        # Frank, 2026-10-18: compact list by default (phones included), a Grid/List toggle, no Roomy/Compact.
        page = self.client.get(reverse("rabbit_list"))
        body = page.content.decode()
        self.assertEqual(body.count("data-view="), 1)
        self.assertIn('data-view="list"', body)
        self.assertNotIn("data-view-controls", body)
        self.assertNotIn('aria-label="Grid size"', body)
        self.assertIn('aria-label="Layout"', body)
        self.assertNotIn("data-density", body.split("<body", 1)[1])
        self.assertIn("Blackberry", body)
        self.assertIn("Buck", body)
        self.assertIn('class="pill pill-g"', body)  # Breeding: green
        self.assertContains(page, "1 active rabbit in your herd")
        self.assertContains(page, "max-w-6xl")
        for header in ("Sex", "Age", "Last weight", "Status"):
            self.assertIn(header, body)

    def test_old_view_and_density_links_are_harmless(self):
        for params in ({"view": "table"}, {"density": "compact"}):
            body = self.client.get(reverse("rabbit_list"), params).content.decode()
            self.assertEqual(body.count("data-view="), 1)
            self.assertIn('data-view="list"', body)

    def test_grid_uses_the_row_anatomy_and_the_plain_placeholder(self):
        body = self.client.get(reverse("rabbit_list"), {"view": "grid"}).content.decode()
        self.assertEqual(body.count("data-view="), 1)
        self.assertIn('data-view="grid"', body)
        card = body.split("data-grid-card", 1)[1].split("</li>", 1)[0]
        for bit in ("Blackberry", "Buck", 'class="pill pill-g"', "coat-swatch", "is-empty"):
            self.assertIn(bit, card)
        self.assertNotIn("stripe", card)
        # The choice is remembered for the account; ?view=list switches back.
        self.assertIn('data-view="grid"', self.client.get(reverse("rabbit_list")).content.decode())
        self.client.get(reverse("rabbit_list"), {"view": "list"})
        self.assertIn('data-view="list"', self.client.get(reverse("rabbit_list")).content.decode())

    def test_latest_weight_is_one_small_query(self):
        from .models import Weight

        rabbit = Rabbit.objects.get(name="Blackberry")
        for day in range(1, 29):
            Weight.objects.create(rabbit=rabbit, date=date(2026, 2, day), grams=3028 if day == 28 else 2000)
        body = self.client.get(reverse("rabbit_list")).content.decode()
        self.assertIn(Weight.objects.get(grams=3028).text, body)
        self.assertNotIn(Weight.objects.filter(grams=2000).first().text, body)


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


class SearchFilterTests(TestCase):
    def setUp(self):
        from django.utils import timezone

        self.user = get_user_model().objects.create_user("s@example.com", "pw-12345678")
        self.client.force_login(self.user)
        make = lambda **kw: Rabbit.objects.create(owner=self.user, color="Black", birth_date=date(2025, 1, 1), **kw)
        make(name="Blackberry", sex="buck", breed="Cross: 50% Creme d'Argent, 50% New Zealand", status="breeding")
        make(name="Lily", sex="doe", breed="New Zealand", status="growing")
        make(name="Willow", sex="doe", breed="Rex", status="breeding")
        make(name="Clover", sex="doe", breed="Rex", status="breeding", archived_at=timezone.now())

    def names(self, **params):
        page = self.client.get(reverse("rabbit_list"), params)
        return page, sorted(r.name for r in page.context["rabbits"])

    def test_search_and_each_filter(self):
        self.assertEqual(self.names(q="  lil ")[1], ["Lily"])
        self.assertEqual(self.names(sex="doe")[1], ["Lily", "Willow"])
        self.assertEqual(self.names(status="breeding")[1], ["Blackberry", "Willow"])
        self.assertEqual(self.names(breed="New Zealand")[1], ["Blackberry", "Lily"])
        self.assertEqual(self.names(sex="doe", breed="New Zealand")[1], ["Lily"])

    def test_compact_filter_row_counts_and_removable_chips(self):
        page, _ = self.names(sex="doe", breed="New Zealand")
        self.assertContains(page, "data-filter-panel")
        self.assertContains(page, '<span class="sr-only">(</span>2<span class="sr-only"> active)</span>')
        chips = {chip["label"]: chip["remove_qs"] for chip in page.context["filter_chips"]}
        self.assertEqual(set(chips), {"Doe", "New Zealand"})
        self.assertNotIn("sex=", chips["Doe"])
        self.assertIn("breed=New+Zealand", chips["Doe"])

    def test_no_filters_means_no_chips_and_a_plain_filter_button(self):
        page, _ = self.names()
        self.assertEqual(page.context["filter_chips"], [])
        self.assertNotContains(page, "Active filters")

    def test_breed_options_include_breeds_inside_crosses(self):
        page, _ = self.names()
        self.assertEqual(page.context["breed_options"], ["Creme d'Argent", "New Zealand", "Rex"])

    def test_archived_tab_and_counts(self):
        page, names = self.names(tab="archived")
        self.assertEqual(names, ["Clover"])
        self.assertContains(page, 'Active <span class="num text-muted">3</span>')
        self.assertContains(page, 'Archived <span class="num text-muted">1</span>')
        self.assertContains(page, '<input type="hidden" name="tab" value="archived">')

    def test_unknown_values_are_ignored(self):
        self.assertEqual(self.names(sex="cat", status="gone", tab="x")[1], ["Blackberry", "Lily", "Willow"])

    def test_empty_results_state_and_clear_link(self):
        page, names = self.names(q="zzz")
        self.assertEqual(names, [])
        self.assertContains(page, "No rabbits match these filters.")
        self.assertContains(page, "0 of 3 active rabbits")

class DeceasedTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("dead@example.com", "pw-12345678")
        self.client.force_login(self.user)
        self.pepper = Rabbit.objects.create(
            owner=self.user, name="Pepper", sex="doe", breed="Rex", color="Black", birth_date=date(2024, 1, 1),
            status="deceased", death_date=date(2026, 5, 18), death_cause="Died kindling",
        )
        Rabbit.objects.create(owner=self.user, name="Blackberry", sex="buck", breed="Rex", color="Black", birth_date=date(2026, 5, 18))

    def names(self, **params):
        return sorted(r.name for r in self.client.get(reverse("rabbit_list"), params).context["rabbits"])

    def test_deceased_leave_active_and_get_their_own_tab(self):
        self.assertEqual(self.names(), ["Blackberry"])
        self.assertEqual(self.names(tab="deceased"), ["Pepper"])
        page = self.client.get(reverse("rabbit_list"), {"tab": "deceased"})
        self.assertContains(page, 'Former <span class="num text-muted">1</span>')
        self.assertContains(page, 'Active <span class="num text-muted">1</span>')
        self.assertContains(page, ">Deceased</span>")  # short pill; the date sits on the meta line
        self.assertContains(page, "Died Mon, May 18")

    def test_detail_tag_and_died_row(self):
        page = self.client.get(reverse("rabbit_detail", args=[self.pepper.pk]))
        self.assertContains(page, 'data-header-badge>Deceased<svg class="badge-chev"')  # the one status (v4 G4)
        self.assertContains(page, '<span class="sr-only">, change status</span></a>')
        self.assertContains(page, "Mon, May 18 · Died kindling")


class DensityTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_user(email="dense@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        Rabbit.objects.create(owner=self.user, name="Pepper", sex="doe", birth_date="2025-03-10", breed="Rex")

    def test_quick_toggle_saves_and_returns_to_the_list(self):
        response = self.client.post(reverse("account"), {"ui_theme": "light", "ui_density": "compact", "next": "/rabbits/?sex=doe"})
        self.assertRedirects(response, "/rabbits/?sex=doe")
        self.user.refresh_from_db()
        self.assertEqual(self.user.ui_density, "compact")

    def test_toggle_refuses_an_outside_next(self):
        response = self.client.post(reverse("account"), {"ui_theme": "light", "ui_density": "compact", "next": "https://example.org/"})
        self.assertRedirects(response, reverse("account"))

    def test_settings_no_longer_has_the_grid_row(self):
        self.assertNotContains(self.client.get(reverse("account")), "Rabbit grid")
