import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from . import flow
from .models import Breed, Rabbit
from .test_contacts import user


class TattooTests(TestCase):
    def setUp(self):
        self.owner = user("tattoo@example.com")
        self.client.force_login(self.owner)
        rex = Breed.objects.get(name="Rex")
        make = lambda name, tattoo="": Rabbit.objects.create(
            owner=self.owner, name=name, tattoo=tattoo, sex="doe", birth_date=datetime.date(2025, 1, 1),
            breed="Rex", breed_type="purebred", purebred=rex, color="Black")
        self.hazel = make("Hazel", "HZ12")
        self.fern = make("Fern")

    def test_unique_per_owner_case_insensitively_and_blank_is_fine(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Rabbit.objects.create(owner=self.owner, name="X", tattoo="hz12", sex="doe", birth_date=datetime.date(2025, 1, 1))
        Rabbit.objects.create(owner=self.owner, name="Y", sex="doe", birth_date=datetime.date(2025, 1, 1))
        Rabbit.objects.create(owner=user("other@example.com"), name="Z", tattoo="HZ12", sex="doe", birth_date=datetime.date(2025, 1, 1))

    def test_the_name_card_sets_and_checks_the_tattoo_in_edit(self):
        url = reverse("rabbit_edit_step", args=[self.fern.pk, "name"])
        self.client.get(url)
        taken = self.client.post(url, {"name": "Fern", "tattoo": " hz12 ", "action": "next"}, follow=True)
        self.assertContains(taken, "Hazel already has the ear tattoo hz12.")
        self.client.post(url, {"name": "Fern", "tattoo": "FN 7", "action": "next"})
        saved = self.client.post(reverse("rabbit_edit", args=[self.fern.pk]), {"action": "save"})
        self.assertRedirects(saved, reverse("rabbit_detail", args=[self.fern.pk]), fetch_redirect_response=False)
        self.fern.refresh_from_db()
        self.assertEqual(self.fern.tattoo, "FN 7")
        self.assertContains(self.client.get(reverse("rabbit_detail", args=[self.fern.pk])), "data-tattoo>FN 7")
        # Keeping its own tattoo is not a clash.
        own = reverse("rabbit_edit_step", args=[self.hazel.pk, "name"])
        self.client.get(own)
        self.assertRedirects(self.client.post(own, {"name": "Hazel", "tattoo": "HZ12", "action": "next"}),
                             reverse("rabbit_edit", args=[self.hazel.pk]), fetch_redirect_response=False)

    def test_the_add_flow_takes_a_tattoo(self):
        self.client.post(reverse("rabbit_flow_step", args=["name"]), {"name": "Kit", "tattoo": "K1", "action": "next"})
        self.assertEqual(flow.load_draft(self.client.session)["tattoo"], "K1")
        self.assertContains(self.client.get(reverse("rabbit_flow_step", args=["name"])), 'value="K1"')

    def test_search_finds_a_tattoo(self):
        names = lambda q: [r.name for r in self.client.get(reverse("rabbit_list"), {"q": q}).context["rabbits"]]
        self.assertEqual(names("hz12"), ["Hazel"])
        self.assertEqual(names("HZ"), ["Hazel"])
        self.assertContains(self.client.get(reverse("rabbit_list")), "· HZ12")

    def test_self_pk_cannot_be_posted(self):
        url = reverse("rabbit_flow_step", args=["name"])
        self.client.post(url, {"name": "Kit", "tattoo": "HZ12", "self_pk": str(self.hazel.pk), "action": "next"})
        self.assertEqual(flow.load_draft(self.client.session)["self_pk"], "")
        self.assertContains(self.client.get(url + "?check=1"), "Hazel already has the ear tattoo HZ12.")
