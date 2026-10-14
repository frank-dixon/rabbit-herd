import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Contact, CullNote, Rabbit

User = get_user_model()


class StatusFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="frank@example.com", password="x-strong-Pass-1")
        self.client.force_login(self.user)
        self.rabbit = Rabbit.objects.create(owner=self.user, name="Hazel", sex="doe", breed="Mini Rex", color="Black",
                                            birth_date=datetime.date(2025, 3, 1))
        self.url = reverse("rabbit_status", args=[self.rabbit.pk])

    def test_sold_to_a_new_buyer_saves_the_contact_and_price(self):
        self.client.post(self.url, {"status": "sold", "sold_on": "2026-10-01", "buyer": "new", "buyer_name": "Dana Whitfield",
                                    "buyer_rabbitry": "Whitfield Farm", "price": "$45"})
        self.rabbit.refresh_from_db()
        self.assertEqual((self.rabbit.status, self.rabbit.sold_on, str(self.rabbit.sale_price)), ("sold", datetime.date(2026, 10, 1), "45.00"))
        self.assertTrue(Contact.objects.get(name="Dana Whitfield").is_buyer)
        self.assertContains(self.client.get(reverse("rabbit_detail", args=[self.rabbit.pk])), "Whitfield Farm")

    def test_culled_writes_a_cull_note_and_back_to_breeding_clears(self):
        self.client.post(self.url, {"status": "culled", "culled_on": "2026-10-02", "reason": "Narrow shoulders."})
        self.rabbit.refresh_from_db()
        self.assertEqual(self.rabbit.death_date, datetime.date(2026, 10, 2))
        self.assertEqual(CullNote.objects.get(rabbit=self.rabbit).reason, "Narrow shoulders.")
        self.client.post(self.url, {"status": "breeding"})
        self.rabbit.refresh_from_db()
        self.assertIsNone(self.rabbit.death_date)

    def test_bad_input_is_refused(self):
        response = self.client.post(self.url, {"status": "deceased", "deceased_on": "2024-01-01"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post(self.url, {"status": "sold", "price": "abc"}).status_code, 400)
