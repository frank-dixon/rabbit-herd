"""List-first pages: the add form is in a closed sheet that the header's
New button (?new=1) opens; errors keep it open. Works without JS."""

from django.test import TestCase, override_settings
from django.urls import reverse

from .test_flow_rules import FlowTestMixin

PAGES = [("pairing_list", "New pairing", "new-pairing"), ("task_list", "New task", "new-task"),
         ("location_list", "New location", "new-location"), ("cost_list", "New cost", "add"),
         ("waitlist", "New buyer", "form")]


@override_settings(FEATURE_LOCATIONS=True)
class AddSheetTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_closed_by_default_with_a_new_button(self):
        for name, label, sid in PAGES:
            body = self.client.get(reverse(name)).content.decode()
            self.assertIn(f'href="?new=1#{sid}"', body, name)
            self.assertIn(f'id="{sid}" data-add-sheet>', body, name)

    def test_new_opens_it(self):
        for name, label, sid in PAGES:
            body = self.client.get(reverse(name) + "?new=1").content.decode()
            self.assertIn(f'id="{sid}" data-add-sheet open>', body, name)

    def test_errors_keep_it_open(self):
        body = self.client.post(reverse("task_list"), {"title": "", "due_on": ""}).content.decode()
        self.assertIn('data-add-sheet open>', body)
