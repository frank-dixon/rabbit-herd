import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import costs
from .models import Expense, Litter, Pairing, Rabbit
from .test_contacts import user


class CostTests(TestCase):
    def setUp(self):
        self.owner = user("costs@example.com")
        self.client.force_login(self.owner)
        base = {"owner": self.owner, "breed": "Rex", "color": "Black", "birth_date": datetime.date(2024, 1, 1)}
        self.doe = Rabbit.objects.create(name="Mom", sex="doe", **base)
        self.buck = Rabbit.objects.create(name="Dad", sex="buck", **base)
        Rabbit.objects.create(name="Gone", sex="buck", status="sold", **base)
        self.litter = Litter.objects.create(owner=self.owner, pairing=Pairing.objects.create(owner=self.owner, doe=self.doe, buck=self.buck),
                                            bred_on=datetime.date(2026, 5, 1))
        self.today = timezone.localdate()
        self.url = reverse("cost_list")

    def data(self, **extra):
        return {"date": self.today.isoformat(), "category": "feed", "description": "50 lb pellets",
                "amount": "$24.50", "weight_lb": "50", **extra}

    def test_add_edit_remove_and_totals(self):
        self.client.post(self.url, self.data())
        self.client.post(self.url, self.data(category="vet", description="Ivermectin", amount="12", weight_lb="", rabbit=str(self.doe.pk)))
        self.client.post(self.url, self.data(category="supplies", description="Nest box", amount="15.25", weight_lb="", litter=str(self.litter.pk)))
        feed = Expense.objects.get(description="50 lb pellets")
        self.assertEqual((feed.amount, feed.per_lb), (Decimal("24.50"), Decimal("0.49")))
        page = self.client.get(self.url)
        t = page.context["totals"]
        self.assertEqual((t["month"], t["active"], t["feed_per_rabbit"], t["price_per_lb"]),
                         (Decimal("51.75"), 2, Decimal("12.25"), Decimal("0.49")))
        self.assertContains(page, "$51.75")
        self.assertContains(page, "50 lb at $0.49/lb")
        editing = self.client.get(self.url + f"?edit={feed.pk}")
        self.assertContains(editing, "Edit 50 lb pellets")
        self.assertContains(editing, 'value="24.50"')
        self.client.post(reverse("cost_edit", args=[feed.pk]), self.data(amount="30"))
        feed.refresh_from_db()
        self.assertEqual(feed.amount, Decimal("30.00"))
        rabbit_page = self.client.get(reverse("rabbit_detail", args=[self.doe.pk]))
        self.assertContains(rabbit_page, "Ivermectin")
        self.assertContains(rabbit_page, f"/costs/?rabbit={self.doe.pk}#add")
        self.assertContains(self.client.get(reverse("litter_detail", args=[self.litter.pk])), "Nest box")
        prefilled = self.client.get(self.url + f"?litter={self.litter.pk}")
        self.assertContains(prefilled, f'<option value="{self.litter.pk}" selected')
        self.client.post(reverse("cost_delete", args=[feed.pk]))
        self.assertEqual(Expense.objects.count(), 2)

    def test_bad_input_keeps_values(self):
        response = self.client.post(self.url, self.data(amount="lots", description="", weight_lb="-3"))
        self.assertEqual(response.status_code, 400)
        for text in ("Please enter the amount", "Please say what it was", "Please enter pounds"):
            self.assertContains(response, text, status_code=400)
        future = (self.today + datetime.timedelta(days=1)).isoformat()
        self.assertContains(self.client.post(self.url, self.data(date=future)), "in the future", status_code=400)
        other = Rabbit.objects.create(owner=user("x@example.com"), name="Not mine", sex="doe", breed="Rex", color="Black",
                                      birth_date=datetime.date(2024, 1, 1))
        self.assertContains(self.client.post(self.url, self.data(rabbit=str(other.pk))), "one of your rabbits", status_code=400)
        self.assertFalse(Expense.objects.exists())

    def test_owner_scope_and_nav(self):
        expense = Expense.objects.create(owner=self.owner, date=self.today, description="Timothy bale", amount=8, category="hay")
        self.assertContains(self.client.get("/"), 'href="/costs/"')
        self.client.force_login(user("x@example.com"))
        self.assertNotContains(self.client.get(self.url), "Timothy bale")
        self.assertEqual(self.client.post(reverse("cost_edit", args=[expense.pk]), self.data()).status_code, 404)
        self.assertEqual(self.client.post(reverse("cost_delete", args=[expense.pk])).status_code, 404)
        self.assertEqual(costs.totals(self.owner)["all"], Decimal("8"))
