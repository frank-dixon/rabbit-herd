import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Rabbit, WaitlistEntry
from .test_contacts import user


class WaitlistTests(TestCase):
    def setUp(self):
        self.owner = user("wait@example.com")
        self.client.force_login(self.owner)
        base = {"owner": self.owner, "breed": "Mini Rex", "birth_date": datetime.date(2026, 6, 1), "status": "growing"}
        self.blue_doe = Rabbit.objects.create(name="Bluebell", sex="doe", color="Blue", **base)
        Rabbit.objects.create(name="Castor Buck", sex="buck", color="Castor", **base)
        Rabbit.objects.create(name="Old Doe", sex="doe", color="Blue", **{**base, "status": "breeding"})
        self.today = timezone.localdate()
        self.url = reverse("waitlist")

    def data(self, **extra):
        return {"buyer": "Dana Ruiz", "reach": "555-0100", "requested_on": self.today.isoformat(), "breed": "mini rex",
                "sex": "doe", "color": "blue", "status": "waiting", "deposit": "25", **extra}

    def test_add_match_edit_close(self):
        self.client.post(self.url, self.data(requested_on=(self.today - datetime.timedelta(days=3)).isoformat()))
        self.client.post(self.url, self.data(buyer="Lee Park", sex="", color="", breed=""))
        page = self.client.get(self.url)
        first, second = page.context["open_entries"]
        self.assertEqual((first.buyer, first.position, [r.name for r in first.fits]), ("Dana Ruiz", 1, ["Bluebell"]))
        self.assertEqual([r.name for r in second.fits], ["Bluebell", "Castor Buck"])
        self.assertContains(page, "Wants Any rabbit")
        self.assertContains(page, "Wants blue mini rex doe")
        self.assertContains(page, "$25.00 deposit")
        editing = self.client.get(self.url + f"?edit={first.pk}")
        self.assertContains(editing, "Edit Dana Ruiz's request")
        self.assertContains(editing, 'value="555-0100"')
        self.client.post(reverse("waitlist_edit", args=[first.pk]), self.data(status="done", rabbit=str(self.blue_doe.pk)))
        page = self.client.get(self.url)
        self.assertEqual([e.buyer for e in page.context["open_entries"]], ["Lee Park"])
        self.assertEqual(page.context["open_entries"][0].position, 1)
        self.assertContains(page, "Closed")
        self.client.post(reverse("waitlist_delete", args=[first.pk]))
        self.assertEqual(WaitlistEntry.objects.count(), 1)

    def test_bad_input(self):
        response = self.client.post(self.url, self.data(buyer="", sex="cat", deposit="abc", rabbit="999"))
        for text in ("buyer&#x27;s name", "doe, buck or either", "deposit as an amount", "one of your rabbits"):
            self.assertContains(response, text, status_code=400)
        self.assertContains(response, 'value="555-0100"', status_code=400)
        self.assertFalse(WaitlistEntry.objects.exists())

    def test_owner_scope(self):
        entry = WaitlistEntry.objects.create(owner=self.owner, buyer="Sam", requested_on=self.today)
        self.assertContains(self.client.get("/"), 'href="/waitlist/"')
        self.client.force_login(user("x@example.com"))
        self.assertNotContains(self.client.get(self.url), "Sam")
        self.assertEqual(self.client.post(reverse("waitlist_edit", args=[entry.pk]), self.data()).status_code, 404)
        self.assertEqual(self.client.post(reverse("waitlist_delete", args=[entry.pk])).status_code, 404)
