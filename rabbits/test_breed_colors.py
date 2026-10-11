from django.test import TestCase

from .models import Breed


class BreedColorSeedTests(TestCase):
    """The seed migration gives every breed a color list or the any-color flag."""

    def test_every_breed_has_colors_or_takes_any_color(self):
        breeds = list(Breed.objects.all())
        self.assertEqual(len(breeds), 86)
        for breed in breeds:
            with self.subTest(breed=breed.name):
                self.assertNotEqual(bool(breed.colors), breed.any_color)

    def test_colors_have_a_name_and_a_hint(self):
        for breed in Breed.objects.exclude(colors=[]):
            names = breed.color_names
            with self.subTest(breed=breed.name):
                self.assertEqual(len(names), len(set(names)), "no repeated colors")
                for color in breed.colors:
                    self.assertEqual(set(color), {"name", "hint"})
                    self.assertTrue(color["name"].strip())

    def test_single_color_breeds(self):
        singles = [breed for breed in Breed.objects.exclude(colors=[]) if len(breed.colors) == 1]
        self.assertEqual(len(singles), 32)
        for name, color in [
            ("Creme d'Argent", "Creme"),
            ("Florida White", "White"),
            ("Champagne d'Argent", "Champagne"),
            ("Mini Californian", "White with black points"),
            ("Thrianta", "Orange-red"),
            ("Alaska", "Black"),
        ]:
            with self.subTest(breed=name):
                self.assertEqual(Breed.objects.get(name=name).color_names, [color])

    def test_lists_keep_the_standard_order(self):
        self.assertEqual(Breed.objects.get(name="New Zealand").color_names, ["White", "Red", "Black", "Blue", "Broken"])
        self.assertEqual(Breed.objects.get(name="Checkered Giant").color_names, ["Black", "Blue"])

    def test_group_color_breeds_take_any_color(self):
        for name in ["Holland Lop", "Netherland Dwarf", "Mini Rex", "Lionhead", "Dwarf Lop"]:
            with self.subTest(breed=name):
                breed = Breed.objects.get(name=name)
                self.assertTrue(breed.any_color)
                self.assertEqual(breed.colors, [])
