import datetime

from django.test import TestCase
from django.utils import timezone

from . import litter_kits as K
from .models import Breed, Litter, LitterCheck, Pairing, Rabbit, Relative, prefs
from .test_litters import user


class ConvertTests(TestCase):
    def setUp(self):
        self.owner = user("convert@example.com")
        rex = Breed.objects.get(name="Rex")
        mk = lambda name, sex: Rabbit.objects.create(owner=self.owner, name=name, sex=sex, breed="Rex", breed_type="purebred",
                                                     purebred=rex, color="Black", birth_date=datetime.date(2024, 1, 1))
        self.doe, self.buck = mk("Hazel", "doe"), mk("Basil", "buck")
        today = timezone.localdate()
        self.litter = Litter.objects.create(owner=self.owner, pairing=Pairing.objects.create(owner=self.owner, doe=self.doe, buck=self.buck),
                                            bred_on=today - datetime.timedelta(days=60), kindled_on=today - datetime.timedelta(days=29),
                                            born_alive=3)
        self.today = today

    def slots(self, *sexes):
        slots = K.ensure_slots(self.litter)
        for slot, sex in zip(slots, sexes):
            slot.sex = sex
            slot.save()
        return slots

    def test_converts_every_kit_once_with_parents_birth_date_and_history(self):
        slots = self.slots("doe", "buck", "doe")
        K.record_whole(self.litter, self.today, 3, 1200, LitterCheck.WeightKind.TOTAL, "healthy", "Clean ears")
        K.record_each(self.litter, self.today, [(slots[0], 450, "watch", "Small"), (slots[1], None, "", ""), (slots[2], 380, "", "")])
        kits = K.convert(self.litter.pk, self.owner)
        self.assertEqual(len(kits), 3)
        first = Rabbit.objects.get(litter_slot__number=1)
        self.assertEqual((first.sex, first.birth_date, first.litter_id), ("doe", self.litter.kindled_on, self.litter.pk))
        self.assertEqual({r.relationship: r.herd_rabbit_id for r in Relative.objects.filter(rabbit=first)},
                         {"dam": self.doe.pk, "sire": self.buck.pk})
        # Whole-litter average (1200 g / 3) and its own row both carry over.
        self.assertEqual(sorted(first.weights.values_list("grams", flat=True)), [400, 450])
        self.assertEqual(first.health_notes.count(), 2)
        self.assertTrue(first.history.filter(subject="litter").exists())
        self.litter.refresh_from_db()
        self.assertIsNotNone(self.litter.converted_at)
        # A second submit (double click) changes nothing.
        K.convert(self.litter.pk, self.owner)
        self.assertEqual(Rabbit.objects.filter(litter=self.litter).count(), 3)

    def test_unsexed_kits_become_unknown(self):
        self.slots("doe", "", "buck")
        K.convert(self.litter.pk, self.owner)
        self.assertEqual(Rabbit.objects.get(litter_slot__number=2).sex, Rabbit.Sex.UNKNOWN)
        # Unknown-sex kits are never offered as breeders.
        from .program_plan import herd_breeders
        self.assertNotIn("unknown", {r.sex for r in herd_breeders(self.owner)})

    def test_existing_herd_kits_are_kept_and_tattoos_prefilled(self):
        settings = prefs(self.owner)
        settings.tattoo_format, settings.tattoo_prefill = "K{nn}", True
        settings.save()
        Rabbit.objects.create(owner=self.owner, name="Early", sex="buck", color="Black", litter=self.litter, tattoo="K01", birth_date=self.litter.kindled_on)
        self.slots("buck", "doe", "doe")
        K.convert(self.litter.pk, self.owner)
        kits = Rabbit.objects.filter(litter=self.litter).order_by("tattoo")
        self.assertEqual([k.tattoo for k in kits], ["K01", "K02", "K03"])


class ConvertViewTests(ConvertTests):
    """The convert dialog is a plain confirm: no typed name, still POST, CSRF and owner-only."""

    def test_confirm_page_has_no_typed_name_and_post_converts(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        url = reverse("litter_convert", args=[self.litter.pk])
        self.client.force_login(self.owner)
        page = self.client.get(url)
        self.assertContains(page, "This can't be undone.")
        self.assertNotContains(page, 'name="confirm"')
        self.assertNotContains(page, "to confirm")
        self.client.get(url)
        self.assertFalse(Rabbit.objects.filter(litter=self.litter).exists())
        other = get_user_model().objects.create_user("other-convert@example.com", "pw-12345678")
        self.client.force_login(other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertFalse(Rabbit.objects.filter(litter=self.litter).exists())
        self.client.force_login(self.owner)
        self.client.post(url)
        self.assertEqual(Rabbit.objects.filter(litter=self.litter).count(), 3)
