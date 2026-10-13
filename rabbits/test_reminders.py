import datetime

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from . import reminders
from .models import HerdSettings, Litter, Pairing, Rabbit, Task
from .test_contacts import user


class DailySummaryTests(TestCase):
    def setUp(self):
        self.owner = user("remind@example.com")
        self.now = timezone.make_aware(datetime.datetime(2026, 10, 12, 7, 0))
        self.today = self.now.date()
        mk = lambda name, sex: Rabbit.objects.create(owner=self.owner, name=name, sex=sex, breed="Rex",
                                                     color="Black", birth_date=datetime.date(2024, 1, 1))
        pairing = Pairing.objects.create(owner=self.owner, doe=mk("Clover", "doe"), buck=mk("Basil", "buck"))
        Litter.objects.create(owner=self.owner, pairing=pairing, bred_on=self.today - datetime.timedelta(days=12))
        Task.objects.create(owner=self.owner, title="Trim nails", due_on=self.today - datetime.timedelta(days=2))
        Task.objects.create(owner=self.owner, title="Order feed", due_on=self.today + datetime.timedelta(days=3))
        self.prefs = HerdSettings.objects.create(user=self.owner, daily_email=True, daily_email_time=datetime.time(6, 0))

    def test_sends_once_with_due_and_overdue(self):
        self.assertEqual(reminders.send_due(self.now), 1)
        [message] = mail.outbox
        self.assertEqual(message.to, ["remind@example.com"])
        self.assertIn("2 things due", message.subject)
        self.assertIn("Palpate: Clover (day 12)", message.body)
        self.assertIn("Trim nails (since Oct 10)", message.body)
        self.assertNotIn("Order feed", message.body)
        self.assertEqual(reminders.send_due(self.now), 0)

    def test_respects_choices_and_time(self):
        self.assertEqual(reminders.send_due(self.now.replace(hour=5)), 0)
        self.prefs.remind_palpate = False
        self.prefs.save()
        reminders.send_due(self.now)
        self.assertNotIn("Palpate", mail.outbox[0].body)
        self.assertIn("Trim nails", mail.outbox[0].body)

    def test_off_or_nothing_due_sends_nothing(self):
        self.prefs.remind_palpate = self.prefs.remind_tasks = False
        self.prefs.save()
        self.assertEqual(reminders.send_due(self.now), 0)
        HerdSettings.objects.update(daily_email=False, daily_email_sent_on=None)
        self.assertEqual(reminders.send_due(self.now), 0)
        self.assertEqual(mail.outbox, [])

    def test_command_runs(self):
        call_command("send_daily_summaries", stdout=open("/dev/null", "w"))
