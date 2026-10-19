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
        for rule in (".temp-rail { position: fixed;", "bottom: var(--tabbar-h)", "height: 44px",
                     "body:has([data-app-tabs]) .pin-main { position: fixed;", "bottom: calc(var(--tabbar-h) + var(--rail-h))",
                     "[data-action-bar] { bottom: calc(var(--tabbar-h) + var(--rail-h)) !important",
                     "[data-shell] main { padding-bottom: calc(var(--stack-h"):
            self.assertIn(rule, block)
        self.assertNotIn("backdrop-filter: blur", block)
        self.assertNotIn("var(--surface)", block)  # not a token; the stack must be opaque
        self.assertGreaterEqual(block.count("background: var(--color-surface)") + block.count("background-color: var(--color-surface)"), 3)

    def test_the_whole_rail_is_one_44px_target(self):
        # Critic v4: one 44px row that is itself the link, with no hit area reaching past it.
        css = (ROOT / "assets" / "layout.css").read_text()
        block = css[css.index("Phone bottom stack"):css.index("Tap targets: 44px")]
        self.assertIn("height: 44px; min-height: 44px", block)
        self.assertNotIn("::after", css[css.index(".temp-rail {"):css.index("Tap targets: 44px")])
        self.assertIn(".temp-rail-hit { display: flex; flex: 1; min-width: 0; min-height: 44px;", css)
        rail = (ROOT / "templates" / "components" / "temp_rail.html").read_text()
        self.assertEqual(rail.count('class="temp-rail-hit"'), 2)  # guest link, demo button
        self.assertIn('<span class="temp-rail-text">{{ temp_rail.text }}</span> <span class="temp-rail-action">', rail)

    def test_the_measurer_is_bound(self):
        js = (ROOT / "assets" / "app.js").read_text()
        self.assertIn('import { bindBottomStack } from "./bottom-stack.mjs";', js)
        self.assertIn("bindBottomStack(document, window);", js)


class StepScrollPaddingTests(SimpleTestCase):
    """Critic v6 M5: on the add-rabbit steps a field and its error scroll into view above the pinned Back/Next bar."""

    def test_scroll_padding_is_the_stack_height(self):
        css = (ROOT / "assets" / "layout.css").read_text()
        self.assertIn("html:has([data-action-bar]) { scroll-padding-bottom: calc(var(--stack-h, 120px) + 1rem); }", css)
        self.assertIn('html:has([data-action-bar]) [aria-invalid="true"] { scroll-margin-bottom: 3.5rem; }', css)
        js = (ROOT / "assets" / "bottom-stack.mjs").read_text()
        self.assertIn('doc.documentElement?.style.setProperty("--stack-h"', js)
        self.assertIn("data-action-bar", (ROOT / "templates" / "rabbits" / "flow" / "step.html").read_text())


class WideRailInFlowTests(SimpleTestCase):
    """Critic v8 O3: on wide screens the guest rail is the content column's last row in the flow, not an overlay,
    so on first load it never lies over Next, with or without JS. The column is at least the screen's height."""

    def test_wide_rail_takes_its_own_row(self):
        css = (ROOT / "assets" / "layout.css").read_text()
        base = css[css.index(".temp-rail {"):]
        base = base[:base.index("}")]
        self.assertIn("position: relative;", base)
        self.assertNotIn("sticky", base)
        self.assertIn("min-height: 44px", base)
        self.assertNotIn("(scripting: none) and (min-width: 768px)", css)  # the v7 padding stopgap is gone
        page = (ROOT / "templates" / "components" / "page.html").read_text()
        column = page.index('<div class="flex min-h-screen min-w-0 flex-1 flex-col">')
        self.assertLess(column, page.index('{% include "components/temp_rail.html" %}'))
        self.assertLess(page.index("</main>"), page.index('{% include "components/temp_rail.html" %}'))
