import csv
import datetime
import io

from django.test import TestCase
from django.urls import reverse

from .models import Expense, Litter, Pairing, Rabbit, ShowEntry, Weight
from .test_contacts import user


def rows(response):
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


class ExportTests(TestCase):
    def setUp(self):
        self.owner = user("export@example.com")
        self.client.force_login(self.owner)
        base = {"owner": self.owner, "breed": "Dutch", "color": "Black", "birth_date": datetime.date(2025, 1, 1)}
        self.doe = Rabbit.objects.create(name="=HYPERLINK(1)", sex="doe", tattoo="D1", **base)
        self.buck = Rabbit.objects.create(name="Buck", sex="buck", **base)
        Litter.objects.create(owner=self.owner, pairing=Pairing.objects.create(owner=self.owner, doe=self.doe, buck=self.buck),
                              bred_on=datetime.date(2026, 5, 1), kindled_on=datetime.date(2026, 6, 1), born_alive=5, died_after=1)
        Weight.objects.create(rabbit=self.buck, date=datetime.date(2026, 9, 1), grams=1814)
        ShowEntry.objects.create(rabbit=self.buck, show_name="Fall Open", date=datetime.date(2026, 9, 5), placing=1, out_of=4, leg=True)
        Expense.objects.create(owner=self.owner, date=datetime.date(2026, 9, 2), description="Pellets", amount=20, weight_lb=50)
        other = user("other@example.com")
        Rabbit.objects.create(**{**base, "owner": other, "name": "Not mine", "sex": "doe"})

    def test_each_export(self):
        response = self.client.get(reverse("export_csv", args=["rabbits"]))
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn('attachment; filename="bramble-burrow-rabbits-', response["Content-Disposition"])
        data = rows(response)
        self.assertEqual(data[0][:3], ["Name", "Ear tattoo", "Sex"])
        self.assertEqual([row[0] for row in data[1:]], ["'=HYPERLINK(1)", "Buck"])
        self.assertEqual(data[1][4], "Yes")  # Dutch is a known breed, so purebred
        litter = rows(self.client.get(reverse("export_csv", args=["litters"])))[1]
        self.assertEqual(litter[:3] + litter[5:9], ["'=HYPERLINK(1)", "Buck", "2026-05-01", "5", "0", "1", "4"])
        weight = rows(self.client.get(reverse("export_csv", args=["weights"])))[1]
        self.assertEqual(weight[:5] + weight[5:7], ["Buck", "", "2026-09-01", "4 lb", "1814", "4.00", "1.814"])
        show = rows(self.client.get(reverse("export_csv", args=["shows"])))[1]
        self.assertEqual(show[:3] + [show[5], show[9]], ["Buck", "Fall Open", "2026-09-05", "1", "Yes"])
        cost = rows(self.client.get(reverse("export_csv", args=["costs"])))[1]
        self.assertEqual(cost[:6], ["2026-09-02", "Feed", "Pellets", "20.00", "50.00", "0.40"])

    def test_unknown_kind_login_and_account_links(self):
        self.assertEqual(self.client.get("/export/passwords.csv").status_code, 404)
        self.assertContains(self.client.get(reverse("account")), "/export/weights.csv")
        self.client.logout()
        self.assertEqual(self.client.get(reverse("export_csv", args=["rabbits"])).status_code, 302)
