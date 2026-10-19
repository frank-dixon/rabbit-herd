"""Critic PA3 (v4): three stat tiles on a phone sit in one row of three, so the third
(Pairings' 'High COI') never sits alone on its own row."""
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class StatGridTests(SimpleTestCase):
    def test_three_tiles_make_one_row_on_phones(self):
        css = (ROOT / "assets" / "components.css").read_text()
        phone = css[css.index("@media (max-width: 767px) {\n  .stat-grid"):]
        self.assertIn(".stat-grid:has(> :nth-child(3):last-child) { grid-template-columns: repeat(3, minmax(0, 1fr)); }", phone)
        self.assertIn(".stat-grid:has(> :nth-child(3):last-child) > :last-child { grid-column: auto; }", phone)
