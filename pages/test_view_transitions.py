"""Critic v3: page transitions between an app page and the marketing home were aborted (a console
page error) because only one side opted in. Every stylesheet a full page loads opts in the same way."""
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ViewTransitionOptInTests(SimpleTestCase):
    def test_app_and_marketing_both_opt_in(self):
        for path in (ROOT / "assets" / "motion.css", ROOT / "static" / "marketing" / "home.css"):
            css = path.read_text()
            self.assertIn("@view-transition { navigation: auto; }", css, path.name)
            self.assertIn("@view-transition { navigation: none; }", css, path.name)  # reduced motion

    def test_aborted_transitions_are_handled(self):
        js = (ROOT / "assets" / "app.js").read_text()
        self.assertIn("bindQuietTransitions(window);", js)
        for name in ("list-swap.mjs", "side-menu.mjs"):
            self.assertNotIn("doc.startViewTransition(", (ROOT / "assets" / name).read_text(), name)
