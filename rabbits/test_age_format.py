"""Tiered ages: days, weeks, months, then years and months."""

from datetime import date

from django.test import SimpleTestCase

from .models import age_exact, age_tiered

BORN = date(2026, 1, 1)


class AgeTierTests(SimpleTestCase):
    def test_tiers(self):
        cases = [(date(2026, 1, 1), "0 days"), (date(2026, 1, 2), "1 day"), (date(2026, 2, 25), "55 days"),
                 (date(2026, 2, 26), "8 wk"), (date(2026, 6, 30), "25 wk"), (date(2026, 7, 1), "6 mo"),
                 (date(2027, 12, 31), "23 mo"), (date(2028, 1, 1), "2 yr"), (date(2028, 9, 15), "2 yr 8 mo")]
        for on, text in cases:
            with self.subTest(on=on):
                self.assertEqual(age_tiered(BORN, on), text)

    def test_exact(self):
        self.assertEqual(age_exact(BORN, date(2026, 5, 28)), "4 months 27 days")
        self.assertEqual(age_exact(BORN, date(2026, 2, 1)), "31 days")
        self.assertEqual(age_exact(BORN, date(2027, 1, 1)), "1 year")

    def test_month_end_birthdays(self):
        self.assertEqual(age_exact(date(2026, 1, 31), date(2026, 4, 30)), "2 months 30 days")
        self.assertEqual(age_tiered(None, BORN), "")
