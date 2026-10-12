from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Breed, Gene, OutsideRabbit, Rabbit, Relative


class AddToHerdTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("herd@example.com", "pw-12345678")
        self.client.force_login(self.user)
        mk = lambda name: Rabbit.objects.create(owner=self.user, name=name, sex="buck", breed="Rex", color="Black", birth_date=date(2026, 5, 18))
        self.kit, self.sibling = mk("Blackberry"), mk("Bramble")
        self.pepper = OutsideRabbit.objects.create(owner=self.user, name="Pepper")
        self.dam = Relative.objects.create(rabbit=self.kit, relationship="dam", outside=self.pepper, breed="Rex", color="Castor", line="Oak")
        Gene.objects.create(relative=self.dam, locus="C", genotype="C/c", certainty="known")
        self.other = Relative.objects.create(rabbit=self.sibling, relationship="dam", outside=self.pepper)
        self.url = reverse("relative_add_to_herd", args=[self.dam.pk])

    def test_card_links_to_add_to_herd(self):
        page = self.client.get(reverse("rabbit_detail", args=[self.kit.pk]))
        self.assertContains(page, f'href="{self.url}"')

    def test_get_shows_form_and_creates_nothing(self):
        page = self.client.get(self.url)
        self.assertContains(page, "Add Pepper to your herd")
        self.assertFalse(Rabbit.objects.filter(name="Pepper").exists())

    def test_post_copies_relinks_everything_and_opens_status_card(self):
        response = self.client.post(self.url, {"sex": "doe", "birth_date": "2024-02-01"})
        pepper = Rabbit.objects.get(name="Pepper", owner=self.user)
        self.assertRedirects(response, reverse("rabbit_edit_step", args=[pepper.pk, "status"]), fetch_redirect_response=False)
        self.assertEqual((pepper.sex, pepper.color, pepper.line, pepper.breed), ("doe", "Castor", "Oak", "Rex"))
        if Breed.objects.filter(name="Rex").exists():
            self.assertEqual(pepper.purebred.name, "Rex")
        self.assertEqual([(g.locus, g.genotype) for g in pepper.genes.all()], [("C", "C/c")])
        self.assertEqual(Relative.objects.filter(herd_rabbit=pepper).count(), 2)
        self.assertFalse(OutsideRabbit.objects.filter(pk=self.pepper.pk).exists())
        # A second post finds no outside relative left, so no duplicate is made.
        self.assertEqual(self.client.post(self.url, {"sex": "doe", "birth_date": "2024-02-01"}).status_code, 404)
        self.assertEqual(Rabbit.objects.filter(name="Pepper").count(), 1)

    def test_birth_date_and_sex_are_required(self):
        self.assertEqual(self.client.post(self.url, {"sex": "", "birth_date": ""}).status_code, 400)
        self.assertFalse(Rabbit.objects.filter(name="Pepper").exists())

    def test_other_keepers_get_404(self):
        self.client.force_login(get_user_model().objects.create_user("x@example.com", "pw-12345678"))
        self.assertEqual(self.client.post(self.url, {"sex": "doe", "birth_date": "2024-02-01"}).status_code, 404)
