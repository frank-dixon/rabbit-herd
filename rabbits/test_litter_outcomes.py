import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import litter_outcomes as O
from .models import Litter, Pairing, Rabbit, Weight
from .test_contacts import user


class LitterOutcomeTests(TestCase):
    def setUp(self):
        self.owner = user("outcome@example.com")
        self.client.force_login(self.owner)
        self.today = timezone.localdate()
        mk = lambda name, sex, **kw: Rabbit.objects.create(owner=self.owner, name=name, sex=sex, breed="New Zealand",
                                                           color="Black", birth_date=kw.pop("born", datetime.date(2024, 1, 1)), **kw)
        pairing = Pairing.objects.create(owner=self.owner, doe=mk("Juniper", "doe"), buck=mk("Ashford", "buck"))
        kindled = self.today - datetime.timedelta(days=80)
        self.litter = Litter.objects.create(owner=self.owner, pairing=pairing, bred_on=kindled - datetime.timedelta(days=31),
                                            kindled_on=kindled, born_alive=4, died_after=1)
        kit = lambda name, status, **kw: mk(name, "unknown", born=kindled, litter=self.litter, status=status, **kw)
        self.kept = kit("Briar", "breeding")
        self.sold = kit("Sorrel", "sold", sold_on=kindled + datetime.timedelta(days=68), sale_price=Decimal("45"))
        self.proc = kit("Kit 3", "culled", death_date=kindled + datetime.timedelta(days=74), dressed_grams=1100)
        Weight.objects.create(rabbit=self.proc, date=kindled + datetime.timedelta(days=73), grams=2000)
        Weight.objects.create(rabbit=self.proc, date=kindled + datetime.timedelta(days=79), grams=2400)  # after processing: ignored

    def kits(self):
        return list(self.litter.kits.all())

    def test_past_when_every_kit_has_an_outcome_or_after_120_days(self):
        self.assertTrue(O.is_past(self.litter, self.kits(), self.today))
        self.kept.status = "growing"
        self.kept.save()
        self.assertFalse(O.is_past(self.litter, self.kits(), self.today))
        self.assertTrue(O.is_past(self.litter, self.kits(), self.litter.kindled_on + datetime.timedelta(days=120)))

    def test_counts_dress_out_and_live_weight_at_processing(self):
        out = O.outcome(self.litter, self.kits(), "lb", self.today)
        self.assertEqual(out["split"], "1 · 1 · 1")
        self.assertEqual(out["counts"]["lost"], 1)
        self.assertEqual(out["dress_pct"], "55%")
        self.assertEqual(out["days"], 74)
        self.assertEqual(out["sold_note"], "Sold $45")

    def test_list_puts_it_under_past_and_notes_save(self):
        page = self.client.get(reverse("litter_list"))
        self.assertContains(page, f'data-past-litter="{self.litter.pk}"')
        self.client.post(reverse("litter_note_add", args=[self.litter.pk]), {"date": self.today.isoformat(), "text": "Good shoulders."})
        self.assertContains(self.client.get(reverse("litter_detail", args=[self.litter.pk])), "Good shoulders.")
