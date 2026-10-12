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
        page = self.client.get(reverse("index"))
        for missing in ("Breeding", "Litters", "Tasks", "Pairings", "Weights", "coming soon", "Coming soon"):
            self.assertNotContains(page, missing)
        for label in ("Home", "Rabbits", "Add a rabbit", "Archived", "Account", "Log out"):
            self.assertContains(page, label)

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
            self.assertContains(page, "md:left-20 lg:left-56", msg_prefix=url)

    def test_signed_out_pages_have_no_shell(self):
        self.client.logout()
        for url in (reverse("index"), reverse("login")):
            page = self.client.get(url)
            self.assertNotContains(page, 'aria-label="App"')
            self.assertNotContains(page, "data-app-tabs")
        self.assertRedirects(self.client.get(reverse("account")), reverse("login") + "?next=/account/")
