"""Glossary: every term cites a real source, and the page links them up."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .glossary import SECTIONS, SOURCES, numbered


class GlossaryTests(TestCase):
    def test_every_term_has_a_known_source_with_a_link(self):
        for _title, terms in SECTIONS:
            for term, _symbol, text, keys in terms:
                self.assertTrue(keys, term)
                self.assertTrue(text.strip(), term)
                for key in keys:
                    self.assertIn(key, SOURCES, term)
        for key, (text, url) in SOURCES.items():
            self.assertTrue(url.startswith("https://"), key)
            self.assertTrue(text.strip(), key)

    def test_sources_are_numbered_in_first_use_order_without_gaps(self):
        sections, references = numbered()
        self.assertEqual([r["n"] for r in references], list(range(1, len(references) + 1)))
        first = sections[0]["terms"][0]
        self.assertEqual(first["refs"], [1])

    def test_page_lists_terms_and_numbered_sources(self):
        user = get_user_model().objects.create_user(email="gl@example.com", password="x-strong-Pass-1")
        self.client.force_login(user)
        page = self.client.get(reverse("glossary"))
        self.assertContains(page, 'id="english-spotting"')
        self.assertContains(page, 'href="#source-1"')
        self.assertContains(page, 'id="source-1"')
        self.assertContains(page, "https://doi.org/10.1371/journal.pone.0093750")
        self.assertContains(page, ">Glossary<")

    def test_signed_out_visitors_are_sent_to_sign_in(self):
        self.assertEqual(self.client.get(reverse("glossary")).status_code, 302)
