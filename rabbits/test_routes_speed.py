"""goal_options must stay fast enough that /programs/new/ opens on click.

With a herd the size of the demo account (~30 rabbits with genes), scanning
every target used to take tens of seconds and the New program button looked
dead. hit() and g2_hit() are cached so the same locus questions aren't
recomputed hundreds of thousands of times."""
import time

from django.contrib.auth import get_user_model
from django.test import TestCase

from rabbits.models import Gene, Rabbit
from rabbits.program_plan import goal_options


class GoalOptionsSpeedTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="speed@example.com", password="x")
        # Enough rabbits that an uncached scan is slow, still small enough for CI.
        genes = {
            "A": "Aa", "B": "Bb", "C": "CC", "D": "Dd", "E": "Ee", "En": "enen",
        }
        for i in range(12):
            r = Rabbit.objects.create(
                owner=self.user, name=f"R{i}", sex="doe" if i % 2 else "buck",
                breed="Mini Rex", color="Black", birth_date="2025-01-01",
            )
            Gene.objects.bulk_create([
                Gene(rabbit=r, locus=locus, genotype=text, certainty=Gene.Certainty.PROBABLE)
                for locus, text in genes.items()
            ])

    def test_goal_options_finishes_quickly(self):
        start = time.perf_counter()
        options = goal_options(self.user)
        elapsed = time.perf_counter() - start
        self.assertGreaterEqual(len(options), 10)
        self.assertLess(elapsed, 5.0, f"goal_options took {elapsed:.2f}s; New program would hang")
