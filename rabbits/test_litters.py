import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Breed, Litter, Pairing, Rabbit
from .test_contacts import user


class LitterTests(TestCase):
    def setUp(self):
        self.owner = user("litter@example.com")
        self.client.force_login(self.owner)
        rex = Breed.objects.get(name="Rex")
        mk = lambda name, sex: Rabbit.objects.create(owner=self.owner, name=name, sex=sex, breed="Rex", breed_type="purebred",
                                                     purebred=rex, color="Black", birth_date=datetime.date(2024, 1, 1))
        self.pairing = Pairing.objects.create(owner=self.owner, doe=mk("Hazel", "doe"), buck=mk("Basil", "buck"))
        self.today = timezone.localdate()

    def start(self, days_ago=5):
        self.client.post(reverse("litter_create", args=[self.pairing.pk]),
                         {"bred_on": (self.today - datetime.timedelta(days=days_ago)).isoformat()})
        return Litter.objects.get()

    def test_dates_from_the_breed_date(self):
        litter = self.start(13)
        self.assertEqual([t["date"] - litter.bred_on for t in litter.tasks()],
                         [datetime.timedelta(days=d) for d in (12, 28, 31)])
        page = self.client.get(reverse("litter_detail", args=[litter.pk]))
        self.assertContains(page, "overdue")
        self.client.post(reverse("litter_task", args=[litter.pk]), {"task": "palpate", "done": "1"})
        litter.refresh_from_db()
        self.assertTrue(litter.palpated)
        self.assertEqual(litter.next_task()["key"], "nest_box")
        self.assertContains(self.client.get(reverse("litter_list")), "Next: Put the nest box in")

    def test_future_or_missing_breed_date_is_refused(self):
        self.client.post(reverse("litter_create", args=[self.pairing.pk]), {"bred_on": ""})
        self.client.post(reverse("litter_create", args=[self.pairing.pk]),
                         {"bred_on": (self.today + datetime.timedelta(days=1)).isoformat()})
        self.assertFalse(Litter.objects.exists())

    def test_kindling_counts_and_kits_into_the_herd(self):
        litter = self.start(31)
        url = reverse("litter_kindle", args=[litter.pk])
        self.client.post(url, {"kindled_on": self.today.isoformat(), "born_alive": "3", "died_after": "5"})
        litter.refresh_from_db()
        self.assertIsNone(litter.kindled_on)
        self.client.post(url, {"kindled_on": self.today.isoformat(), "born_alive": "3", "born_dead": "1", "died_after": "1"})
        litter.refresh_from_db()
        self.assertEqual((litter.born_alive, litter.born_dead, litter.survivors), (3, 1, 2))
        self.assertIsNone(litter.next_task())
        add = reverse("litter_add_kit", args=[litter.pk])
        self.client.post(add, {"name": "Clover", "sex": "doe", "tattoo": "CL1"})
        self.client.post(add, {"name": "Dup", "sex": "buck", "tattoo": "cl1"})
        self.client.post(add, {"name": "Thyme", "sex": "buck"})
        page = self.client.post(add, {"name": "Extra", "sex": "buck"}, follow=True)
        self.assertContains(page, "All 2 surviving kits are already in your herd.")
        kits = list(litter.kits.order_by("name"))
        self.assertEqual([k.name for k in kits], ["Clover", "Thyme"])
        clover = kits[0]
        self.assertEqual((clover.birth_date, clover.status, clover.breed, clover.tattoo), (self.today, "growing", "Rex", "CL1"))
        self.assertEqual({r.relationship: r.herd_rabbit for r in clover.relatives.all()},
                         {"dam": self.pairing.doe, "sire": self.pairing.buck})
        # Survivors can't drop below the kits already added.
        self.client.post(url, {"kindled_on": self.today.isoformat(), "born_alive": "3", "died_after": "2"})
        litter.refresh_from_db()
        self.assertEqual(litter.survivors, 2)

    def test_owner_scope_and_nav(self):
        litter = self.start()
        self.assertContains(self.client.get(reverse("pairing_detail", args=[self.pairing.pk])), "Start a litter")
        self.assertContains(self.client.get(reverse("litter_list")), 'href="/litters/"')
        self.client.force_login(user("other@example.com"))
        self.assertEqual(self.client.get(reverse("litter_detail", args=[litter.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("litter_add_kit", args=[litter.pk]), {"name": "X", "sex": "doe"}).status_code, 404)
