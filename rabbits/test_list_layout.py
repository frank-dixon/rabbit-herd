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
        # The saved choice applies at every screen size: no grid behind it.
        self.assertNotContains(again, 'data-view="grid"')
        self.assertEqual(again.content.decode().count("data-view="), 1)
        self.assertContains(again, "Last weight")
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

    def test_view_toggle_keeps_filters_and_saved_view(self):
        page, _ = self.names(sex="doe", view="list")
        self.assertContains(page, 'href="?sex=doe&amp;view=grid"')
        self.assertContains(page, 'data-view="list"')
        again, _ = self.names(status="growing")
        self.assertContains(again, 'data-view="list"')


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
        self.assertContains(page, ">Deceased</span>")
        self.assertContains(page, "May 18, 2026 · Died kindling")


class DensityTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_user(email="dense@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        Rabbit.objects.create(owner=self.user, name="Pepper", sex="doe", birth_date="2025-03-10", breed="Rex")

    def test_roomy_is_the_default_grid(self):
        page = self.client.get(reverse("rabbit_list"))
        self.assertContains(page, 'data-view="grid"')
        self.assertNotContains(page, 'data-density="compact"')
        controls = page.content.decode()
        controls = controls[controls.index("data-view-controls"):]
        self.assertIn('aria-label="Grid size"', controls)
        self.assertRegex(controls, r'href="\?density=roomy"[^>]*aria-current="true"')

    def test_compact_grid_is_two_up_with_a_single_detail_line(self):
        self.user.ui_density = "compact"
        self.user.save()
        page = self.client.get(reverse("rabbit_list"))
        self.assertContains(page, 'data-density="compact"')
        self.assertContains(page, "grid-cols-2")
        self.assertContains(page, "Doe · ")
        self.assertRegex(page.content.decode(), r'href="\?density=compact"[^>]*aria-current="true"')

    def test_quick_toggle_saves_and_returns_to_the_list(self):
        response = self.client.post(reverse("account"), {"ui_theme": "c1", "ui_density": "compact", "next": "/rabbits/?sex=doe"})
        self.assertRedirects(response, "/rabbits/?sex=doe")
        self.user.refresh_from_db()
        self.assertEqual(self.user.ui_density, "compact")

    def test_toggle_refuses_an_outside_next(self):
        response = self.client.post(reverse("account"), {"ui_theme": "c1", "ui_density": "compact", "next": "https://example.org/"})
        self.assertRedirects(response, reverse("account"))

    def test_density_and_layout_links_persist_per_account(self):
        self.client.get(reverse("rabbit_list") + "?density=compact&sex=doe")
        self.client.get(reverse("rabbit_list") + "?view=list")
        self.user.refresh_from_db()
        self.assertEqual((self.user.ui_density, self.user.ui_list_view), ("compact", "list"))
        self.client.logout()
        self.client.force_login(self.user)
        page = self.client.get(reverse("rabbit_list")).content.decode()
        self.assertIn('data-view="list"', page)
        self.assertNotIn('aria-label="Grid size"', page)
        self.assertRegex(page, r'href="\?view=list"[^>]*aria-current="true"')

    def test_settings_no_longer_has_the_grid_row(self):
        self.assertNotContains(self.client.get(reverse("account")), "Rabbit grid")
