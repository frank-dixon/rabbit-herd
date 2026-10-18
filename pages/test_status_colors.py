"""One color per status (rabbits/status_pills.py), readable in every theme."""

import re
from pathlib import Path

from django.test import SimpleTestCase

from rabbits.status_pills import TONES, coi_tone, status_tone, tone

ASSETS = Path(__file__).resolve().parents[1] / "assets"
PAIRS = {"g": ("g-ink", "g-soft"), "b": ("b-ink", "b-soft"), "y": ("y-ink", "y-soft"), "r": ("r-ink", "r-soft"), "o": ("ink-2", "pill")}


def luminance(hex_color):
    h = hex_color.lstrip("#")
    channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def themes():
    css = (ASSETS / "themes.css").read_text()
    for name, body in re.findall(r'html\[data-theme="([^"]+)"\][^{]*\{([^}]*)\}', css):
        yield name, dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})\b", body))


class StatusColorTests(SimpleTestCase):
    def test_the_map_follows_the_agreed_colors(self):
        for word, expected in [("breeding", "g"), ("healthy", "g"), ("bred", "b"), ("expecting", "b"),
                               ("due soon", "y"), ("needs attention", "y"), ("overdue", "r"), ("problem", "r"),
                               ("sold", "o"), ("processed", "o"), ("culled", "o"), ("archived", "o")]:
            self.assertEqual(tone(word), expected, word)
        self.assertEqual(status_tone("growing"), "g")
        self.assertEqual(status_tone("sold"), "o")
        self.assertEqual([coi_tone(0), coi_tone(3), coi_tone(12.5), coi_tone(25)], ["g", "g", "", "r"])  # medium is grey with its % label

    def test_every_word_has_one_color(self):
        seen = {}
        for letter, words in TONES.items():
            for word in words:
                self.assertNotIn(word, seen, f"{word!r} is both {seen.get(word)} and {letter}")
                seen[word] = letter

    def test_every_tone_has_a_pill_class(self):
        css = (ASSETS / "layout.css").read_text()
        for letter in PAIRS:
            self.assertRegex(css, rf"\.pill-{letter}\s*\{{")

    def test_pill_text_reads_at_4_5_to_1_in_every_theme(self):
        checked = set()
        for name, colors in themes():
            for letter, (ink, bg) in PAIRS.items():
                if ink in colors and bg in colors:
                    ratio = contrast(colors[ink], colors[bg])
                    self.assertGreaterEqual(ratio, 4.5, f"{name} pill-{letter}: {ratio:.2f}")
                    checked.add(name)
        self.assertTrue({"light", "heritage"} <= checked)
