"""Every status pill uses a color from the one map (rabbits/status_pills.py): g, b, y, r, o or
the plain neutral pill. Nothing else colors a pill (Critic v2, item 3)."""
import datetime
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rabbits.models import HealthNote, Litter, Pairing, Rabbit
from rabbits.status_pills import TONES, tone

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
PILL = re.compile(r'class="([^"]*\bpill\b[^"]*)"')
COLOR_UTILITY = re.compile(r"\b(?:bg|text|border)-(?:accent|warn|danger|ok|info|success|red|green|amber|yellow|blue|emerald|sky|rose)\b|#[0-9a-fA-F]{3,6}")
ALLOWED = set(TONES)


def pill_classes(html):
    for cls in PILL.findall(html):
        yield cls, set(re.findall(r"\bpill-([a-z0-9]+)\b", cls))


class PillMapTemplateTests(TestCase):
    def test_no_template_colors_a_pill_outside_the_map(self):
        for path in TEMPLATES.rglob("*.html"):
            for cls, tones in pill_classes(path.read_text()):
                literal = {t for t in tones if "{" not in t}
                self.assertLessEqual(literal, ALLOWED, f"{path.name}: {cls}")
                self.assertIsNone(COLOR_UTILITY.search(cls), f"{path.name}: {cls}")

    def test_routine_checkups_are_neutral(self):
        self.assertEqual(tone("checkup"), "")
        self.assertEqual(tone("overdue"), "r")


    def test_coi_is_green_low_grey_medium_red_high(self):
        from rabbits.status_pills import coi_tone, tone

        self.assertEqual([coi_tone(2), coi_tone(6.25), coi_tone(12.5), coi_tone(25)], ["g", "", "", "r"])
        self.assertEqual([tone("mid"), tone("moderate")], ["", ""])


class PillMapPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("pills@example.com", "pw-12345678")
        self.client.force_login(self.user)
        mk = lambda name, sex, **kw: Rabbit.objects.create(owner=self.user, name=name, sex=sex, breed="Rex", birth_date=datetime.date(2024, 1, 1), **kw)
        self.doe, self.buck = mk("Willow", "doe", status="breeding"), mk("Jet", "buck", status="breeding")
        mk("Sold one", "doe", status="sold")
        today = timezone.localdate()
        pairing = Pairing.objects.create(owner=self.user, doe=self.doe, buck=self.buck)
        self.litter = Litter.objects.create(owner=self.user, pairing=pairing, bred_on=today - datetime.timedelta(days=60),
                                            kindled_on=today - datetime.timedelta(days=29))
        HealthNote.objects.create(rabbit=self.doe, date=today, kind="checkup", notes="All fine")
        HealthNote.objects.create(rabbit=self.buck, date=today - datetime.timedelta(days=9), kind="illness", notes="Sneezing",
                                  follow_up_on=today - datetime.timedelta(days=2))

    def pages(self):
        yield "index", self.client.get(reverse("index")).content.decode()
        yield "detail", self.client.get(reverse("rabbit_detail", args=[self.doe.pk])).content.decode()
        for name in ("rabbit_list", "pairing_list", "litter_list", "health_list", "cost_list", "weights_hub", "task_list"):
            yield name, self.client.get(reverse(name)).content.decode()
        yield "litter", self.client.get(reverse("litter_detail", args=[self.litter.pk])).content.decode()

    def test_every_rendered_pill_uses_a_map_color(self):
        for name, body in self.pages():
            for cls, tones in pill_classes(body):
                self.assertLessEqual(tones, ALLOWED, f"{name}: {cls}")
                self.assertIsNone(COLOR_UTILITY.search(cls), f"{name}: {cls}")

    def test_breeding_badge_on_rabbit_detail_is_green(self):
        body = self.client.get(reverse("rabbit_detail", args=[self.doe.pk])).content.decode()
        self.assertRegex(body, r'class="pill pill-g" data-header-badge>Breeding<')

    def test_checkup_is_neutral_on_health(self):
        body = self.client.get(reverse("health_list")).content.decode()
        self.assertRegex(body, r'class="pill">Checkup<')

    def test_recheck_overdue_on_today_is_red(self):
        body = self.client.get(reverse("index")).content.decode()
        self.assertRegex(body, r'text-sm text-danger">Noted ')

    def test_sold_and_processed_are_grey_in_the_outcome_legend(self):
        css = (Path(__file__).resolve().parents[1] / "assets" / "outcomes.css").read_text()
        for key in ("sold", "processed"):
            value = re.search(rf"--oc-{key}:\s*([^;]+);", css).group(1)
            self.assertIn("var(--ink-2)", value, key)
