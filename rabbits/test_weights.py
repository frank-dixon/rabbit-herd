import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Rabbit, Weight, weight_text
from .test_contacts import user
from .weights import chart


class WeightTests(TestCase):
    def setUp(self):
        self.owner = user("weights@example.com")
        self.client.force_login(self.owner)
        self.rabbit = Rabbit.objects.create(owner=self.owner, name="Hazel", sex="doe", birth_date=datetime.date(2026, 6, 1))
        self.url = reverse("rabbit_weight_add", args=[self.rabbit.pk])
        self.detail = reverse("rabbit_detail", args=[self.rabbit.pk])

    def test_text_in_each_unit(self):
        self.assertEqual(weight_text(1985, "lb"), "4 lb 6 oz")
        self.assertEqual(weight_text(907, "lb"), "2 lb")
        self.assertEqual(weight_text(250, "lb"), "9 oz")
        self.assertEqual(weight_text(2100, "kg"), "2.1 kg")

    def test_add_in_lb_oz_and_in_kg(self):
        self.assertRedirects(self.client.post(self.url, {"date": "2026-07-01", "lb": "2", "oz": "4", "note": "8 weeks"}),
                             self.detail + "#weights", fetch_redirect_response=False)
        self.client.post(self.url, {"date": "2026-08-01", "kg": "1,6"})
        first, second = Weight.objects.order_by("date")
        self.assertEqual((first.grams, first.unit, first.note), (1021, "lb", "8 weeks"))
        self.assertEqual((second.grams, second.unit), (1600, "kg"))
        page = self.client.get(self.detail)
        self.assertContains(page, "data-weight-chart")
        self.assertContains(page, "<polyline")
        self.assertContains(page, "3 lb 8 oz")  # Shown in the Settings unit (lb by default).
        self.assertContains(page, "8 weeks")

    def test_problems_are_explained_and_nothing_is_saved(self):
        tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        cases = [
            ({"date": "", "lb": "2"}, "A weight needs a date."),
            ({"date": tomorrow, "lb": "2"}, "can&#x27;t be in the future"),
            ({"date": "2026-01-01", "lb": "2"}, "can&#x27;t be before the rabbit was born"),
            ({"date": "2026-07-01"}, "Enter a weight"),
            ({"date": "2026-07-01", "lb": "two"}, "Enter a weight"),
            ({"date": "2026-07-01", "kg": "45"}, "That weight looks off."),
            ({"date": "2026-07-01", "lb": "2", "kg": "1"}, "but not both"),
        ]
        for data, message in cases:
            self.assertContains(self.client.post(self.url, data, follow=True), message, msg_prefix=str(data))
        self.assertFalse(Weight.objects.exists())

    def test_chart_scales_points_to_the_dates_and_values(self):
        a = Weight(rabbit=self.rabbit, date=datetime.date(2026, 7, 1), grams=454, unit="lb")
        b = Weight(rabbit=self.rabbit, date=datetime.date(2026, 7, 31), grams=1814, unit="lb")
        c = chart([a, b], "lb")
        (p1, p2) = c["points"]
        self.assertEqual((p1["x"], p2["x"]), (c["left"], c["right"]))
        self.assertGreater(p1["y"], p2["y"])
        self.assertEqual([t["label"] for t in c["ticks"]][-1], "4")
        self.assertIsNone(chart([], "lb"))

    def test_remove_and_owner_checks(self):
        weight = Weight.objects.create(rabbit=self.rabbit, date=datetime.date(2026, 7, 1), grams=900)
        self.client.force_login(user("other@example.com"))
        self.assertEqual(self.client.post(reverse("rabbit_weight_delete", args=[weight.pk])).status_code, 404)
        self.assertEqual(self.client.post(self.url, {"date": "2026-07-01", "lb": "2"}).status_code, 404)
        self.client.force_login(self.owner)
        self.client.post(reverse("rabbit_weight_delete", args=[weight.pk]))
        self.assertFalse(Weight.objects.exists())


class ChartAxisTests(TestCase):
    def test_axes_have_titles_and_date_ticks(self):
        import datetime
        from types import SimpleNamespace
        from .weights import chart
        rows = [SimpleNamespace(date=datetime.date(2026, 3, 1) + datetime.timedelta(days=d), grams=g)
                for d, g in ((0, 600), (14, 900), (28, 1250), (56, 1900))]
        c = chart(rows, "lb")
        self.assertEqual((c["y_title"], c["x_title"]), ("Weight (lb)", "Date weighed"))
        labels = [t["label"] for t in c["x_ticks"]]
        self.assertEqual(labels[0], "Mar 1")
        self.assertEqual(labels[-1], "Apr 26")
        self.assertEqual(len(labels), 5)
        self.assertEqual(len(set(labels)), len(labels))
        self.assertEqual(chart(rows, "kg")["y_title"], "Weight (kg)")
        self.assertEqual(len(chart(rows[:1], "lb")["x_ticks"]), 1)
        long = [SimpleNamespace(date=datetime.date(2025, 1, 1), grams=500), SimpleNamespace(date=datetime.date(2026, 2, 1), grams=3000)]
        self.assertEqual(chart(long, "lb")["x_ticks"][0]["label"], "Jan ’25")


class WeightErrorFeedbackTests(TestCase):
    """A refused weight is never silent: the card shows the error with the
    typed values kept, and an error toast says it wasn't saved."""

    def test_refused_weight_shows_inline_error_and_toast(self):
        from datetime import date
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        from .models import Rabbit

        user = get_user_model().objects.create_user("w@example.com", "pw-12345678")
        self.client.force_login(user)
        rabbit = Rabbit.objects.create(owner=user, name="Juniper", sex="doe", breed="Rex", color="Black", birth_date=date(2026, 9, 1))
        response = self.client.post(reverse("rabbit_weight_add", args=[rabbit.pk]), {"date": "2026-08-01", "lb": "5", "oz": "4"}, follow=True)
        self.assertContains(response, "data-weight-error")
        self.assertContains(response, 'toast toast-error')
        self.assertContains(response, "The weight wasn&#x27;t saved.")
        self.assertContains(response, 'name="lb" type="text" value="5"')
        self.assertEqual(rabbit.weights.count(), 0)

    def test_saved_weight_shows_toast_and_persists(self):
        from datetime import date
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        from django.utils import timezone
        from .models import Rabbit

        user = get_user_model().objects.create_user("w2@example.com", "pw-12345678")
        self.client.force_login(user)
        rabbit = Rabbit.objects.create(owner=user, name="Blackberry", sex="doe", breed="Rex", color="Black", birth_date=date(2025, 1, 1))
        today = timezone.localdate().isoformat()
        response = self.client.post(reverse("rabbit_weight_add", args=[rabbit.pk]), {"date": today, "lb": "5", "oz": "4"}, follow=True)
        self.assertContains(response, "was added.")
        self.assertNotContains(response, "No weights yet")
        self.assertEqual(rabbit.weights.count(), 1)
