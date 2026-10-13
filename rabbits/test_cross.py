import datetime

from django.test import TestCase
from django.urls import reverse

from .models import Gene, Rabbit
from .test_contacts import user


class CrossPageTests(TestCase):
    def setUp(self):
        self.owner = user("cross@example.com")
        self.client.force_login(self.owner)
        base = {"owner": self.owner, "breed": "New Zealand", "color": "Black", "birth_date": datetime.date(2025, 1, 1)}
        self.doe = Rabbit.objects.create(name="Hazel", sex="doe", **base)
        for locus, genotype in dict(A="a/a", B="B/B", C="C/c", D="D/D", E="E/E").items():
            Gene.objects.create(rabbit=self.doe, locus=locus, genotype=genotype, certainty="known")

    def get(self, **params):
        return self.client.get(reverse("genetics_cross"), params)

    def test_empty_form(self):
        page = self.get()
        self.assertContains(page, "What-if cross")
        self.assertContains(page, "Crème d&#x27;Argent")
        self.assertNotContains(page, "data-cross-result")

    def test_herd_rabbit_by_breed(self):
        page = self.get(doe=f"r{self.doe.pk}", buck="b:new-zealand-white")
        self.assertContains(page, "Hazel × New Zealand White")
        self.assertContains(page, "data-breed-note")
        colors = dict(page.context["result"]["odds"]["colors"])
        self.assertEqual(colors, {"Black": "50%", "Ruby-eyed white": "50%"})

    def test_two_breeds(self):
        page = self.get(doe="b:creme-dargent", buck="b:creme-dargent")
        self.assertContains(page, "Crème d&#x27;Argent (2)")
        colors = dict(page.context["result"]["odds"]["colors"])
        self.assertEqual(colors, {"Silvered cream (Crème d'Argent type)": "100%"})

    def test_other_owners_rabbit_is_not_offered(self):
        other = user("other-cross@example.com")
        theirs = Rabbit.objects.create(owner=other, name="Secret", sex="buck", breed="Rex", color="Black",
                                       birth_date=datetime.date(2025, 1, 1))
        page = self.get(doe=f"r{self.doe.pk}", buck=f"r{theirs.pk}")
        self.assertIsNone(page.context["result"])
        self.assertContains(page, "Choose a rabbit or breed from the list.")
        self.assertNotContains(page, "Secret")

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.get().status_code, 302)
