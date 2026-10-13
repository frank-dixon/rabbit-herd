"""Rabbit page header: Pedigree button, Delete in the … menu, Edit last;
the parents card links the pedigree with a real button."""

from django.test import TestCase
from django.urls import reverse

from .test_flow_rules import FlowTestMixin


class DetailActionsTests(FlowTestMixin, TestCase):
    def test_header_has_pedigree_and_delete_in_more_menu(self):
        self.client.force_login(self.user)
        rabbit = self.rabbit("Bun", "doe")
        body = self.client.get(reverse("rabbit_detail", args=[rabbit.pk])).content.decode()
        pedigree = reverse("rabbit_pedigree", args=[rabbit.pk])
        start = body.index("data-header-actions")
        header = body[start:body.index("</header>", start)]
        self.assertIn(f'href="{pedigree}"', header)
        self.assertIn("data-pedigree-button", header)
        menu = header[header.index("data-more-menu"):header.index("</details>")]
        self.assertIn(reverse("rabbit_delete", args=[rabbit.pk]), menu)
        self.assertLess(header.index("data-more-menu"), header.index(">Edit<"))
        self.assertIn(">View pedigree<", body)
        self.assertNotIn("Printable pedigree", body)
