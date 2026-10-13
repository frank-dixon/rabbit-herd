import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Litter, Pairing, Rabbit, Task
from .test_contacts import user


class TaskTests(TestCase):
    def setUp(self):
        self.owner = user("tasks@example.com")
        self.client.force_login(self.owner)
        mk = lambda name, sex: Rabbit.objects.create(owner=self.owner, name=name, sex=sex, breed="Rex", color="Black",
                                                     birth_date=datetime.date(2024, 1, 1))
        self.doe, self.buck = mk("Hazel", "doe"), mk("Basil", "buck")
        self.today = timezone.localdate()

    def test_add_list_overdue_and_done(self):
        url = reverse("task_list")
        bad = self.client.post(url, {"title": " ", "due_on": ""})
        self.assertContains(bad, "Say what needs doing")
        self.assertContains(bad, "Enter a due date.")
        self.client.post(url, {"title": "Trim nails", "due_on": (self.today - datetime.timedelta(days=2)).isoformat(), "rabbit": self.doe.pk})
        self.client.post(url, {"title": "Order hay", "due_on": self.today.isoformat()})
        page = self.client.get(url)
        self.assertContains(page, "data-overdue")
        self.assertContains(page, "Overdue ·")
        self.assertContains(page, "Today ·")
        task = Task.objects.get(title="Trim nails")
        self.assertEqual(task.rabbit, self.doe)
        self.client.post(reverse("task_done", args=[task.pk]), {"next": "/"})
        task.refresh_from_db()
        self.assertIsNotNone(task.done_at)
        self.assertContains(self.client.get(url), "Recently done")

    def test_litter_dates_feed_tasks_and_home(self):
        pairing = Pairing.objects.create(owner=self.owner, doe=self.doe, buck=self.buck)
        litter = Litter.objects.create(owner=self.owner, pairing=pairing, bred_on=self.today - datetime.timedelta(days=13))
        page = self.client.get(reverse("task_list"))
        self.assertContains(page, "Palpate: Hazel (day 12)")
        self.assertContains(page, "Put the nest box in: Hazel (day 28)")
        self.assertContains(page, "Due to kindle: Hazel (day 31)")
        home = self.client.get("/")
        nxt = home.content.decode().split("data-next-up", 1)[1]
        self.assertIn("csrfmiddlewaretoken", nxt.split("</ul>", 1)[0])
        self.assertContains(home, "Due in the next 7 days")
        self.assertContains(home, "Palpate: Hazel")
        self.client.post(reverse("litter_task", args=[litter.pk]), {"task": "palpate", "done": "1", "next": "/tasks/"})
        self.assertNotContains(self.client.get(reverse("task_list")), "Palpate: Hazel")
        litter.kindled_on = self.today
        litter.born_alive = 3
        litter.save()
        self.assertNotContains(self.client.get(reverse("task_list")), "Due to kindle")

    def test_owner_scope_and_safe_next(self):
        task = Task.objects.create(owner=self.owner, title="Zebra brush", due_on=self.today)
        response = self.client.post(reverse("task_done", args=[task.pk]), {"next": "https://evil.example/"})
        self.assertRedirects(response, reverse("task_list"), fetch_redirect_response=False)
        self.client = self.client_class()
        self.client.force_login(user("other@example.com"))
        self.assertEqual(self.client.post(reverse("task_done", args=[task.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("task_list")), "Zebra brush")


class TaskRepeatTests(TestCase):
    def setUp(self):
        self.owner = user("repeat@example.com")
        self.client.force_login(self.owner)

    def test_interval_math_clamps_months(self):
        from .models import add_interval
        d = datetime.date
        self.assertEqual(add_interval(d(2026, 1, 31), 1, "months"), d(2026, 2, 28))
        self.assertEqual(add_interval(d(2028, 1, 31), 1, "months"), d(2028, 2, 29))
        self.assertEqual(add_interval(d(2026, 11, 30), 3, "months"), d(2027, 2, 28))
        self.assertEqual(add_interval(d(2026, 12, 15), 2, "months"), d(2027, 2, 15))
        self.assertEqual(add_interval(d(2026, 10, 13), 2, "weeks"), d(2026, 10, 27))
        self.assertEqual(add_interval(d(2026, 12, 31), 1, "days"), d(2027, 1, 1))

    def test_presets_and_custom_labels(self):
        t = Task(due_on=datetime.date(2026, 3, 31), repeat="bimonthly")
        self.assertEqual(t.next_due(), datetime.date(2026, 5, 31))
        self.assertEqual(t.repeat_label(), "Every 2 months")
        t = Task(due_on=datetime.date(2026, 3, 1), repeat="custom", repeat_every=10, repeat_unit="days")
        self.assertEqual(t.next_due(), datetime.date(2026, 3, 11))
        self.assertEqual(t.repeat_label(), "Every 10 days")
        self.assertIsNone(Task(due_on=datetime.date(2026, 3, 1)).next_due())

    def test_add_ignores_custom_fields_unless_custom(self):
        url = reverse("task_list")
        self.client.post(url, {"title": "Hay", "due_on": "2026-10-13", "repeat": "weekly", "repeat_every": "9", "repeat_unit": "days"})
        t = Task.objects.get(title="Hay")
        self.assertEqual((t.repeat, t.repeat_every, t.repeat_unit), ("weekly", None, ""))
        bad = self.client.post(url, {"title": "Odd", "due_on": "2026-10-13", "repeat": "custom", "repeat_every": "0", "repeat_unit": "weeks"})
        self.assertContains(bad, "Enter how often")
        self.client.post(url, {"title": "Odd", "due_on": "2026-10-13", "repeat": "custom", "repeat_every": "3", "repeat_unit": "weeks"})
        self.assertEqual(Task.objects.get(title="Odd").repeat_every, 3)
        self.assertContains(self.client.get(url), "Every 3 weeks")

    def test_done_makes_next_and_undo_removes_it(self):
        t = Task.objects.create(owner=self.owner, title="Clean trays", due_on=datetime.date(2026, 1, 31), repeat="monthly")
        done = reverse("task_done", args=[t.pk])
        self.client.post(done)
        t.refresh_from_db()
        self.assertIsNotNone(t.done_at)
        nxt = t.next_occurrence
        self.assertEqual((nxt.due_on, nxt.repeat, nxt.done_at), (datetime.date(2026, 2, 28), "monthly", None))
        self.client.post(done)  # Undo
        t.refresh_from_db()
        self.assertIsNone(t.done_at)
        self.assertFalse(Task.objects.filter(pk=nxt.pk).exists())
        self.assertEqual(Task.objects.filter(title="Clean trays").count(), 1)
        self.client.post(done)
        self.client.post(done)
        self.client.post(done)
        self.assertEqual(Task.objects.filter(title="Clean trays", done_at__isnull=True).count(), 1)

    def test_one_off_done_makes_nothing(self):
        t = Task.objects.create(owner=self.owner, title="Once", due_on=datetime.date(2026, 1, 1))
        self.client.post(reverse("task_done", args=[t.pk]))
        self.assertEqual(Task.objects.filter(title="Once").count(), 1)

    def test_edit_changes_repeat(self):
        t = Task.objects.create(owner=self.owner, title="Water", due_on=datetime.date(2026, 1, 1))
        url = reverse("task_edit", args=[t.pk])
        self.assertContains(self.client.get(url), 'data-repeat-custom')
        self.client.post(url, {"title": "Water", "due_on": "2026-01-02", "rabbit": "", "repeat": "custom", "repeat_every": "2", "repeat_unit": "days"})
        t.refresh_from_db()
        self.assertEqual((t.due_on, t.repeat, t.repeat_every, t.repeat_unit), (datetime.date(2026, 1, 2), "custom", 2, "days"))
        other = user("other@example.com")
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)


class SoldLastTests(TestCase):
    def test_sold_rabbits_sort_last_in_grid_list_and_search(self):
        owner = user("sold@example.com")
        self.client.force_login(owner)
        for name, status in [("Alder", "sold"), ("Birch", "breeding"), ("Cedar", "sold"), ("Dill", "growing")]:
            Rabbit.objects.create(owner=owner, name=name, sex="doe", breed="Rex", color="Black", status=status,
                                  birth_date=datetime.date(2024, 1, 1))
        for query in ("", "?view=list", "?view=grid", "?q=e", "?breed=Rex"):
            page = self.client.get(reverse("rabbit_list") + query)
            names = [r.name for r in page.context["rabbits"]]
            want = [n for n in ["Birch", "Dill", "Alder", "Cedar"] if n in names]
            self.assertEqual(names, want, query)
