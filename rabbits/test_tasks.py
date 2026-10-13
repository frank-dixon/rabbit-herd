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
        self.assertContains(bad, "Please say what needs doing")
        self.assertContains(bad, "Please enter a due date.")
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
        self.assertContains(home, "Due now")
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
