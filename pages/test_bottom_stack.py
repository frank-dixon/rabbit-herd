"""Phone bottom stack (Critic v2 items 1 and 2): the guest/demo rail never covers an action bar or
the pinned main button; tab bar, rail and action stack flush, opaque, with the page padded by
their height."""
import re
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class BottomStackTests(SimpleTestCase):
    def test_every_fixed_bottom_action_bar_joins_the_stack(self):
        for path in (ROOT / "templates").rglob("*.html"):
            for cls in re.findall(r'<div class="(fixed inset-x-0 bottom-0[^"]*)"([^>]*)>', path.read_text()):
                self.assertIn("data-action-bar", cls[1], path.name)

    def test_stack_rules(self):
        css = (ROOT / "assets" / "layout.css").read_text()
        block = css[css.index("Phone bottom stack"):]
        for rule in (".temp-rail { position: fixed;", "bottom: var(--tabbar-h)", "height: 24px",
                     "body:has([data-app-tabs]) .pin-main { position: fixed;", "bottom: calc(var(--tabbar-h) + var(--rail-h))",
                     "[data-action-bar] { bottom: calc(var(--tabbar-h) + var(--rail-h)) !important",
                     "[data-shell] main { padding-bottom: calc(var(--stack-h"):
            self.assertIn(rule, block)
        self.assertNotIn("backdrop-filter: blur", block)
        self.assertNotIn("var(--surface)", block)  # not a token; the stack must be opaque
        self.assertGreaterEqual(block.count("background: var(--color-surface)") + block.count("background-color: var(--color-surface)"), 3)

    def test_the_measurer_is_bound(self):
        js = (ROOT / "assets" / "app.js").read_text()
        self.assertIn('import { bindBottomStack } from "./bottom-stack.mjs";', js)
        self.assertIn("bindBottomStack(document, window);", js)
