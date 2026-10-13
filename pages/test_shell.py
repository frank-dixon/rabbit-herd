from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rabbits.models import Rabbit


class AppShellTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="shell@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        self.rabbit = Rabbit.objects.create(owner=self.user, name="Pepper", sex="doe", birth_date="2024-03-10")

    def test_logged_in_pages_get_the_side_menu_and_tabs(self):
        for url in (reverse("index"), reverse("rabbit_list"), reverse("rabbit_detail", args=[self.rabbit.pk]),
                    reverse("rabbit_photos", args=[self.rabbit.pk]), reverse("account")):
            page = self.client.get(url)
            self.assertContains(page, 'aria-label="App"', msg_prefix=url)
            self.assertContains(page, "data-app-tabs", msg_prefix=url)
            self.assertContains(page, 'aria-current="page"', msg_prefix=url)

    def test_only_built_sections_are_listed(self):
        html = self.client.get(reverse("index")).content.decode()
        page = html[html.index('<aside'):html.index('</aside>')] + html[html.index('data-app-tabs'):]
        for missing in ("coming soon", "Coming soon", ">More<"):
            self.assertNotIn(missing, page)
        for label in ("Today", "Rabbits", "Archived", "Tasks", "Pairings", "Litters", "Weights", "Locations"):
            self.assertIn(label, page)
        panel = html[html.index('id="app-menu"'):html.index('data-shell')]
        for label in ("Contacts", "Costs", "Waitlist", "Shows", "Health", "Export", "Settings", "Account", "Sign out"):
            self.assertIn(label, panel)

    def test_phone_bar_is_n1_with_a_due_badge(self):
        from datetime import date, timedelta
        from rabbits.models import Task
        Task.objects.create(owner=self.user, title="Trim nails", due_on=date.today() - timedelta(days=1))
        Task.objects.create(owner=self.user, title="Later", due_on=date.today() + timedelta(days=5))
        html = self.client.get(reverse("rabbit_list")).content.decode()
        tabs = html[html.index("data-app-tabs"):]
        self.assertEqual([t for t in ("today", "rabbits", "litters", "weights", "tasks") if f'data-tab="{t}"' in tabs],
                         ["today", "rabbits", "litters", "weights", "tasks"])
        self.assertIn('1<span class="sr-only"> due</span>', tabs)

    def test_menu_button_works_without_js(self):
        html = self.client.get(reverse("rabbit_list")).content.decode()
        self.assertIn('href="#app-menu"', html)
        self.assertIn('aria-controls="app-menu" aria-expanded="false" data-menu-button', html)
        drawer = html[html.index('id="app-menu"'):html.index("data-shell")]
        self.assertIn("Sign out", drawer)
        self.assertIn('href="/pairings/"', drawer)
        self.assertNotIn(" inert", drawer[:200])

    def test_layout_a_rail_records_and_account_footer(self):
        from rabbits.models import HerdSettings
        HerdSettings.objects.create(user=self.user, rabbitry_name="Dixon Rabbitry")
        html = self.client.get(reverse("rabbit_list")).content.decode()
        rail = html[html.index("data-app-rail"):html.index("</aside>")]
        self.assertNotIn("/rabbits/new/", rail)
        self.assertIn(">Records<", rail)
        for url in ("/contacts/", "/costs/", "/waitlist/", "/shows/", "/health/"):
            self.assertIn(f'href="{url}"', rail)
        self.assertLess(rail.index("/archived") if "/archived" in rail else rail.index("tab=archived"), rail.index("/contacts/"))
        self.assertIn("Dixon Rabbitry", rail)
        pop = rail[rail.index("data-account-pop"):]
        self.assertIn("Settings</a>", pop)
        self.assertIn("Account", pop)
        self.assertIn("Sign out", pop)
        self.assertNotIn("Appearance", pop)
        self.assertNotIn("Contacts", pop)
        self.assertRedirects(self.client.get("/menu/"), reverse("account"))

    def test_herd_pages_for_weights_health_and_shows(self):
        for name in ("weights_hub", "health_list", "show_list"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertContains(self.client.get(reverse("weights_hub")), "Pepper")

    def test_the_current_section_is_marked(self):
        page = self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk])).content.decode()
        self.assertRegex(page, r'href="/rabbits/"[^>]*aria-current="page"')
        archived = self.client.get(reverse("rabbit_list") + "?tab=archived").content.decode()
        self.assertRegex(archived, r'href="/rabbits/\?tab=archived"[^>]*aria-current="page"')

    def test_pages_with_their_own_action_bar_drop_the_phone_tabs(self):
        for url in (reverse("rabbit_edit", args=[self.rabbit.pk]),
                    reverse("rabbit_edit_step", args=[self.rabbit.pk, "name"]),
                    reverse("rabbit_flow_step", args=["name"])):
            page = self.client.get(url, follow=True)
            self.assertNotContains(page, "data-app-tabs", msg_prefix=url)
            self.assertContains(page, 'aria-label="App"', msg_prefix=url)
            self.assertContains(page, "md:static", msg_prefix=url)  # Inline actions from tablet up.

    def test_signed_out_pages_have_no_shell(self):
        self.client.logout()
        for url in (reverse("index"), reverse("login")):
            page = self.client.get(url)
            self.assertNotContains(page, 'aria-label="App"')
            self.assertNotContains(page, "data-app-tabs")
        self.assertRedirects(self.client.get(reverse("account")), reverse("login") + "?next=/settings/")


class PullRefreshTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="ptr@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        self.rabbit = Rabbit.objects.create(owner=self.user, name="Pepper", sex="doe", birth_date="2024-03-10")

    def test_today_and_lists_can_refresh(self):
        for name in ("index", "rabbit_list", "litter_list", "task_list", "contact_list", "weights_hub"):
            self.assertContains(self.client.get(reverse(name)), "data-refreshable", msg_prefix=name)

    def test_detail_and_forms_do_not(self):
        for url in (reverse("rabbit_detail", args=[self.rabbit.pk]), reverse("account")):
            self.assertNotContains(self.client.get(url), "data-refreshable")

    def test_offline_banner_is_in_every_page(self):
        self.assertContains(self.client.get(reverse("index")), 'class="net-banner" role="status" data-connection-status')


class EmptyStateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="empty@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)

    def test_each_empty_list_offers_one_next_step(self):
        for name, step in (("index", "rabbit_create"), ("rabbit_list", "rabbit_create"),
                           ("contact_list", "contact_create"), ("weights_hub", "rabbit_create")):
            html = self.client.get(reverse(name)).content.decode()
            block = html[html.index('class="empty'):]
            block = block[:block.index("</div>\n</div>") if "</div>\n</div>" in block else 1500]
            self.assertIn(f'href="{reverse(step)}"', block, name)
            self.assertEqual(block.count("<a "), 1, name)

    def test_empty_litters_does_not_repeat_the_header_action(self):
        html = self.client.get(reverse("litter_list")).content.decode()
        self.assertIn("No litters on the way.", html)
        self.assertEqual(html.count(f'href="{reverse("pairing_list")}"', html.index("<main")), 1)
