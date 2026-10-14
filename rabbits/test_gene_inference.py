"""Planner fallback: herd rabbits with no Gene rows plan from their color."""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from rabbits import program_plan as plan
from rabbits.models import Rabbit


class InferenceFallbackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="f@example.com", password="x")

    def add(self, name, sex, color):
        return Rabbit.objects.create(owner=self.user, name=name, sex=sex, breed="Mini Rex", color=color,
                                     birth_date=datetime.date(2025, 1, 1))

    def test_color_only_rabbits_are_breeders(self):
        self.add("Ink", "doe", "Black")
        self.add("Coal", "buck", "Black")
        names = {b["name"] for b in plan.known_breeders(self.user)}
        self.assertEqual(names, {"Ink", "Coal"})
        black = next(o for o in plan.goal_options(self.user) if o["key"] == "black")
        self.assertEqual(black["tier"], 1)
        self.assertEqual(plan.unknown_gene_count(self.user), 0)

    def test_rabbits_with_nothing_to_infer_are_counted(self):
        self.add("Mystery", "doe", "")
        self.assertEqual(plan.known_breeders(self.user), [])
        self.assertEqual(plan.unknown_gene_count(self.user), 1)
