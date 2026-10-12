from django.test import SimpleTestCase

from .models import short_breed_text


class ShortBreedTests(SimpleTestCase):
    def test_cross_with_three_breeds_names_the_top_one(self):
        self.assertEqual(
            short_breed_text("Cross: 50% Creme d'Argent, 25% Flemish Giant, 25% New Zealand"),
            "Cross · Creme d'Argent 50% +2 more",
        )

    def test_cross_with_two_breeds(self):
        self.assertEqual(short_breed_text("Cross: 60% Rex, 40% Dutch"), "Cross · Rex 60% +1 more")

    def test_purebred_and_free_text_are_kept(self):
        self.assertEqual(short_breed_text("New Zealand"), "New Zealand")
        self.assertEqual(short_breed_text("Rex x Dutch"), "Rex x Dutch")
        self.assertEqual(short_breed_text(""), "")
