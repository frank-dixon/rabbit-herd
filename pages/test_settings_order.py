import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .views import SETTINGS_SECTIONS


class SettingsOrderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="order@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)

    def test_nav_order_matches_section_order(self):
        html = self.client.get(reverse("account")).content.decode()
        start = html.index("data-settings-nav")
        nav = html[start:html.index("</nav>", start)]
        links = re.findall(r'href="#([\w-]+)"', nav)
        sections = re.findall(r'data-settings-slot="([\w-]+)"', html)
        self.assertEqual(links, sections)
        self.assertEqual(links, [anchor for _g, anchor, _l, _t in SETTINGS_SECTIONS])
        for anchor in sections:
            self.assertIn(f'id="{anchor}"', html)
            self.assertLess(html.index(f'data-settings-slot="{anchor}"'), html.index(f'id="{anchor}"', html.index("</nav>")))
