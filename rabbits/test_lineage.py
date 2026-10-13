from django.db import DataError, IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from rabbits.models import (
    PEDIGREE_POSITIONS,
    Breed,
    BreedShare,
    OutsideRabbit,
    PedigreeEntry,
    Rabbit,
    Relative,
    position_label,
)


def make_rabbit(owner, name="Clover", sex=Rabbit.Sex.DOE, **extra):
    fields = {
        "owner": owner,
        "name": name,
        "sex": sex,
        "breed": "Dutch",
        "color": "Black",
        "birth_date": "2024-03-01",
    }
    fields.update(extra)
    return Rabbit.objects.create(**fields)


class LineageModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="frank@example.com", password="x")
        self.rabbit = make_rabbit(self.owner)

    def test_purebred_breed_line_uses_the_catalog_name(self):
        self.rabbit.breed_type = Rabbit.BreedType.PUREBRED
        self.rabbit.purebred = Breed.objects.get(name="Holland Lop")
        self.rabbit.save()

        self.assertEqual(self.rabbit.breed_line(), "Holland Lop")

    def test_crossbred_breed_line_lists_shares_largest_first(self):
        self.rabbit.breed_type = Rabbit.BreedType.CROSSBRED
        self.rabbit.save()
        BreedShare.objects.create(rabbit=self.rabbit, breed=Breed.objects.get(name="Rex"), percent=25)
        BreedShare.objects.create(
            rabbit=self.rabbit, breed=Breed.objects.get(name="New Zealand"), percent=75
        )

        self.assertEqual(self.rabbit.breed_line(), "Cross: 75% New Zealand, 25% Rex")

    def test_a_breed_appears_once_per_rabbit(self):
        breed = Breed.objects.get(name="Rex")
        BreedShare.objects.create(rabbit=self.rabbit, breed=breed, percent=50)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BreedShare.objects.create(rabbit=self.rabbit, breed=breed, percent=50)

    def test_a_share_cannot_be_0_or_100_percent(self):
        rex = Breed.objects.get(name="Rex")
        with self.assertRaises(IntegrityError), transaction.atomic():
            BreedShare.objects.create(rabbit=self.rabbit, breed=rex, percent=0)
        # The column holds at most 99.99, so 100 never reaches the check.
        with self.assertRaises(DataError), transaction.atomic():
            BreedShare.objects.create(rabbit=self.rabbit, breed=rex, percent=100)

    def test_relative_points_at_exactly_one_rabbit(self):
        dam = make_rabbit(self.owner, name="Maple")
        outside = OutsideRabbit.objects.create(owner=self.owner, name="Duke", details="Tag 7")

        Relative.objects.create(rabbit=self.rabbit, relationship="dam", herd_rabbit=dam)
        Relative.objects.create(rabbit=self.rabbit, relationship="sire", outside=outside)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Relative.objects.create(rabbit=self.rabbit, relationship="sibling")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Relative.objects.create(
                rabbit=self.rabbit, relationship="cousin", herd_rabbit=dam, outside=outside
            )
        self.assertEqual(str(outside), "Duke (Tag 7)")

    def test_pedigree_positions_cover_three_generations(self):
        self.assertEqual(len(PEDIGREE_POSITIONS), 14)
        self.assertEqual(PEDIGREE_POSITIONS[:2], ["s", "d"])
        self.assertEqual(position_label("sd"), "Sire's dam")
        self.assertEqual(position_label("dds"), "Dam's dam's sire")

    def test_one_ancestor_per_pedigree_position(self):
        outside = OutsideRabbit.objects.create(owner=self.owner, name="Duke")
        entry = PedigreeEntry.objects.create(rabbit=self.rabbit, position="s", outside=outside)

        self.assertEqual(entry.expected_sex, Rabbit.Sex.BUCK)
        self.assertEqual(self.rabbit.pedigree_by_position()["s"].ancestor, outside)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PedigreeEntry.objects.create(rabbit=self.rabbit, position="s", outside=outside)
