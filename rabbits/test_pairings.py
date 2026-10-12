import datetime

from django.test import TestCase
from django.urls import reverse

from .models import OutsideRabbit, Pairing, PedigreeEntry, Rabbit, Relative
from .pairings import inbreeding_warnings
from .test_contacts import user


def make(owner, name, sex, **extra):
    return Rabbit.objects.create(owner=owner, name=name, sex=sex, breed="Rex", color="Black",
                                 birth_date=datetime.date(2025, 1, 1), **extra)


class PairingTests(TestCase):
    def setUp(self):
        self.owner = user("pair@example.com")
        self.client.force_login(self.owner)
        self.mum = make(self.owner, "Pepper", "doe")
        self.doe = make(self.owner, "Hazel", "doe")
        self.buck = make(self.owner, "Basil", "buck")
        self.other = make(self.owner, "Rowan", "buck")

    def test_unrelated_pair_has_no_warning(self):
        self.assertEqual(inbreeding_warnings(self.doe, self.other), [])

    def test_shared_herd_dam_and_parent_child(self):
        Relative.objects.create(rabbit=self.doe, relationship="dam", herd_rabbit=self.mum)
        Relative.objects.create(rabbit=self.buck, relationship="dam", herd_rabbit=self.mum)
        self.assertEqual(inbreeding_warnings(self.doe, self.buck),
                         ["Shared ancestor Pepper: Hazel's parent and Basil's parent."])
        # A doe paired with her own son.
        son = make(self.owner, "Sorrel", "buck")
        Relative.objects.create(rabbit=self.mum, relationship="offspring", herd_rabbit=son)
        self.assertIn("Pepper is Sorrel's parent.", inbreeding_warnings(self.mum, son))

    def test_ancestors_are_followed_up_through_herd_rabbits_and_pedigrees(self):
        gran = OutsideRabbit.objects.create(owner=self.owner, name="Old Tom")
        PedigreeEntry.objects.create(rabbit=self.mum, position="s", outside=gran)
        Relative.objects.create(rabbit=self.doe, relationship="dam", herd_rabbit=self.mum)
        Relative.objects.create(rabbit=self.buck, relationship="grandsire", outside=gran)
        self.assertEqual(inbreeding_warnings(self.doe, self.buck),
                         ["Shared ancestor Old Tom: Hazel's grandparent and Basil's grandparent."])

    def test_pages_check_save_and_scope(self):
        Relative.objects.create(rabbit=self.doe, relationship="sibling", herd_rabbit=self.buck)
        url = reverse("pairing_list")
        checked = self.client.post(url, {"doe": self.doe.pk, "buck": self.buck.pk, "action": "check"})
        self.assertContains(checked, "Inbreeding warning: Hazel and Basil are related.")
        self.assertContains(checked, "recorded as full siblings")
        self.assertFalse(Pairing.objects.exists())
        wrong = self.client.post(url, {"doe": self.buck.pk, "buck": "", "action": "save"})
        self.assertContains(wrong, "Please choose a doe from your herd.")
        self.assertContains(wrong, "Please choose a buck from your herd.")
        stranger = make(user("x@example.com"), "Stranger", "buck")
        self.assertContains(self.client.post(url, {"doe": self.doe.pk, "buck": stranger.pk, "action": "save"}),
                            "Please choose a buck")
        saved = self.client.post(url, {"doe": self.doe.pk, "buck": self.other.pk, "notes": "Spring", "action": "save"})
        pairing = Pairing.objects.get()
        self.assertRedirects(saved, reverse("pairing_detail", args=[pairing.pk]))
        detail = self.client.get(reverse("pairing_detail", args=[pairing.pk]))
        self.assertContains(detail, "No shared ancestors found")
        self.assertContains(self.client.get(url), "Hazel × Rowan")
        self.client.force_login(stranger.owner)
        self.assertEqual(self.client.get(reverse("pairing_detail", args=[pairing.pk])).status_code, 404)

    def test_nav_lists_pairings(self):
        self.assertContains(self.client.get(reverse("pairing_list")), 'href="/pairings/"')
