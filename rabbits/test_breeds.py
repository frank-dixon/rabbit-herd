from django.db import IntegrityError
from django.test import TestCase

from rabbits.models import Breed


class BreedCatalogTests(TestCase):
    def test_every_arba_breed_is_seeded(self):
        arba = Breed.objects.filter(registry=Breed.Registry.ARBA)

        self.assertEqual(arba.count(), 53)
        for name in ["Mini Californian", "Blue Holicer", "Holland Lop", "New Zealand"]:
            self.assertTrue(arba.filter(name=name).exists(), name)
        self.assertFalse(Breed.objects.filter(name__icontains="cav").exists())

    def test_common_non_arba_breeds_are_seeded(self):
        other = Breed.objects.filter(registry=Breed.Registry.OTHER)

        self.assertGreaterEqual(other.count(), 30)
        for name in ["Continental Giant", "Dwarf Lop", "Thuringer"]:
            self.assertTrue(other.filter(name=name).exists(), name)

    def test_names_are_unique(self):
        with self.assertRaises(IntegrityError):
            Breed.objects.create(name="Dutch", registry=Breed.Registry.OTHER)

    def test_breeds_list_by_name(self):
        # Postgres and SQLite collate punctuation differently, so check the
        # ordering rule rather than one database's exact order.
        self.assertEqual(Breed._meta.ordering, ["name"])
