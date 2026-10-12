from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Contact, Rabbit


def user(email):
    return get_user_model().objects.create_user(email=email, password="x-strong-Pass-1")


class ContactTests(TestCase):
    def setUp(self):
        self.owner = user("contacts@example.com")
        self.client.force_login(self.owner)
        self.rabbit = Rabbit.objects.create(owner=self.owner, name="Pepper", sex="doe", birth_date="2024-03-10")

    def test_add_a_contact_with_roles(self):
        response = self.client.post(reverse("contact_create"), {
            "name": "  Ann   Lee ", "rabbitry": "Hollow Creek Rabbitry", "phone": "555-0101",
            "email": "ann@example.com", "location": "Ithaca, NY", "notes": "Sells REWs", "is_breeder": "on", "is_stud_owner": "on",
        })
        ann = Contact.objects.get()
        self.assertRedirects(response, reverse("contact_detail", args=[ann.pk]))
        self.assertEqual((ann.owner, ann.name, ann.roles), (self.owner, "Ann Lee", ["Breeder", "Stud owner"]))
        page = self.client.get(reverse("contact_detail", args=[ann.pk]))
        for text in ("Hollow Creek Rabbitry", 'href="tel:555-0101"', "mailto:ann@example.com", "Ithaca, NY", "Sells REWs", "Stud owner"):
            self.assertContains(page, text)

    def test_a_name_is_required(self):
        response = self.client.post(reverse("contact_create"), {"name": " "})
        self.assertContains(response, "A contact needs a name. Please add one.")
        self.assertFalse(Contact.objects.exists())

    def test_the_list_filters_by_role_and_is_owner_scoped(self):
        Contact.objects.create(owner=self.owner, name="Ann", is_breeder=True)
        Contact.objects.create(owner=self.owner, name="Bob", is_buyer=True)
        Contact.objects.create(owner=user("other@example.com"), name="Stranger", is_buyer=True)
        page = self.client.get(reverse("contact_list"))
        self.assertContains(page, "Ann")
        self.assertContains(page, "Bob")
        self.assertNotContains(page, "Stranger")
        buyers = self.client.get(reverse("contact_list"), {"role": "buyer"})
        self.assertContains(buyers, "Bob")
        self.assertNotContains(buyers, ">Ann<")

    def test_pick_a_contact_as_the_source_and_see_it_both_ways(self):
        ann = Contact.objects.create(owner=self.owner, name="Ann", rabbitry="Hollow Creek")
        detail = reverse("rabbit_detail", args=[self.rabbit.pk])
        self.assertContains(self.client.get(detail), "Not recorded.")
        self.assertRedirects(self.client.post(reverse("rabbit_source", args=[self.rabbit.pk]), {"source": ann.pk}), detail)
        self.rabbit.refresh_from_db()
        self.assertEqual(self.rabbit.source, ann)
        self.assertContains(self.client.get(detail), f'href="{reverse("contact_detail", args=[ann.pk])}"')
        page = self.client.get(reverse("contact_detail", args=[ann.pk]))
        self.assertContains(page, "Came from them")
        self.assertContains(page, "Pepper")
        self.client.post(reverse("rabbit_source", args=[self.rabbit.pk]), {"source": ""})
        self.rabbit.refresh_from_db()
        self.assertIsNone(self.rabbit.source)

    def test_other_owners_contacts_and_rabbits_are_off_limits(self):
        theirs = Contact.objects.create(owner=user("other@example.com"), name="Stranger")
        self.client.post(reverse("rabbit_source", args=[self.rabbit.pk]), {"source": theirs.pk})
        self.rabbit.refresh_from_db()
        self.assertIsNone(self.rabbit.source)
        self.assertEqual(self.client.get(reverse("contact_detail", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("contact_edit", args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("contact_edit", args=[theirs.pk]), {"name": "x"}).status_code, 404)

    def test_contacts_are_in_the_nav(self):
        page = self.client.get(reverse("contact_list")).content.decode()
        self.assertRegex(page, r'href="/contacts/"[^>]*aria-current="page"')
