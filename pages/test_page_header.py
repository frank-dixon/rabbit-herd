from datetime import date

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from rabbits.models import Rabbit


class PageHeaderTests(TestCase):
    def test_component_back_link_nowrap_actions_and_print_button(self):
        html = render_to_string("components/page_header.html", {
            "title": "Pedigree: Clover", "back_label": "Clover", "back_href": "/rabbits/1/", "print_label": "Print"})
        self.assertNotIn("{#", html)
        self.assertLess(html.index("data-back-link"), html.index("<h1"))
        actions = html[html.index("data-header-actions") - 200:]
        self.assertIn("shrink-0", actions)
        self.assertIn("whitespace-nowrap", actions)
        self.assertIn("border-line", html[html.index("data-print-button") - 300:])

    def test_single_rabbit_pages_show_its_thumbnail(self):
        user = get_user_model().objects.create_user(email="h@example.com", password="x-strong-Pass-1")
        self.client.force_login(user)
        rabbit = Rabbit.objects.create(owner=user, name="Clover", sex="doe", breed="Rex", birth_date=date(2025, 1, 1))
        for name in ("rabbit_detail", "rabbit_edit", "rabbit_photos", "rabbit_pedigree"):
            body = self.client.get(reverse(name, args=[rabbit.pk])).content.decode()
            header = body[body.index("data-page-header"):body.index("</header>", body.index("data-page-header"))]
            self.assertIn("data-page-thumb", header, name)
            self.assertIn("data-back-link", header, name)
        pedigree = self.client.get(reverse("rabbit_pedigree", args=[rabbit.pk])).content.decode()
        subject = pedigree[pedigree.index("data-pedigree"):]
        self.assertIn("print:inline-flex", subject[:subject.index("subject-heading") + 400])
