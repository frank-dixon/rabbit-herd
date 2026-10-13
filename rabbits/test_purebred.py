import datetime

from django.test import TestCase
from django.urls import reverse

from . import purebred
from .models import Breed, BreedShare, OutsideRabbit, Rabbit, Relative
from .test_contacts import user


class PurebredTests(TestCase):
    def setUp(self):
        self.owner = user("pure@example.com")
        self.client.force_login(self.owner)
        self.rex, _ = Breed.objects.get_or_create(name="Mini Rex")
        self.dutch, _ = Breed.objects.get_or_create(name="Dutch")

    def rabbit(self, name, **extra):
        fields = {"owner": self.owner, "name": name, "sex": "doe", "breed": "", "color": "Black",
                  "birth_date": datetime.date(2025, 1, 1), **extra}
        return Rabbit.objects.create(**fields)

    def parent(self, kit, relationship, herd=None, breed=""):
        if herd:
            return Relative.objects.create(rabbit=kit, relationship=relationship, herd_rabbit=herd)
        outside = OutsideRabbit.objects.create(owner=self.owner, name=f"{relationship} of {kit}")
        return Relative.objects.create(rabbit=kit, relationship=relationship, outside=outside, breed=breed)

    def test_entered_purebred_and_cross(self):
        pure = self.rabbit("Pure", breed="Mini Rex", breed_type="purebred", purebred=self.rex)
        self.assertEqual(purebred.purebred(pure), {"breed": "Mini Rex", "source": "entered"})
        cross = self.rabbit("Cross", breed="Cross: 50% Mini Rex, 50% Dutch", breed_type="crossbred")
        BreedShare.objects.create(rabbit=cross, breed=self.rex, percent=50)
        BreedShare.objects.create(rabbit=cross, breed=self.dutch, percent=50)
        self.assertIsNone(purebred.purebred(cross))

    def test_from_parents_herd_and_outside(self):
        dam = self.rabbit("Dam", breed="Mini Rex", breed_type="purebred", purebred=self.rex)
        kit = self.rabbit("Kit", breed="Unknown")
        self.parent(kit, "dam", herd=dam)
        self.assertIsNone(purebred.purebred(kit))  # sire unknown
        self.parent(kit, "sire", breed="mini rex")
        self.assertEqual(purebred.purebred(kit), {"breed": "Mini Rex", "source": "parents"})
        grandkit = self.rabbit("Grandkit")
        self.parent(grandkit, "dam", herd=kit)
        self.parent(grandkit, "sire", breed="Dutch")
        self.assertIsNone(purebred.purebred(grandkit))

    def test_older_text_breed(self):
        self.assertEqual(purebred.purebred(self.rabbit("Old", breed="Dutch"))["source"], "text")
        self.assertIsNone(purebred.purebred(self.rabbit("Mystery", breed="Barn mix")))

    def test_shown_on_page_and_filter(self):
        dam = self.rabbit("Dam", breed="Mini Rex", breed_type="purebred", purebred=self.rex)
        kit = self.rabbit("Kit", breed="Unknown")
        self.parent(kit, "dam", herd=dam)
        self.parent(kit, "sire", breed="Mini Rex")
        self.rabbit("Mutt", breed="Barn mix")
        page = self.client.get(reverse("rabbit_detail", args=[kit.pk]))
        self.assertContains(page, 'data-purebred="parents"')
        self.assertContains(page, "Both parents are Mini Rex.")
        names = lambda q: [r.name for r in self.client.get(reverse("rabbit_list") + q).context["rabbits"]]
        self.assertEqual(names("?pure=yes"), ["Dam", "Kit"])
        self.assertEqual(names("?pure=no"), ["Mutt"])
        self.assertEqual(len(names("?pure=bogus")), 3)
