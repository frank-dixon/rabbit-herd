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
        self.assertContains(checked, "data-inbreeding")
        self.assertContains(checked, "Hazel and Basil are full siblings")
        self.assertFalse(Pairing.objects.exists())
        wrong = self.client.post(url, {"doe": self.buck.pk, "buck": "", "action": "save"})
        self.assertContains(wrong, "Choose a doe from your herd.")
        self.assertContains(wrong, "Choose a buck from your herd.")
        stranger = make(user("x@example.com"), "Stranger", "buck")
        self.assertContains(self.client.post(url, {"doe": self.doe.pk, "buck": stranger.pk, "action": "save"}),
                            "Choose a buck")
        saved = self.client.post(url, {"doe": self.doe.pk, "buck": self.other.pk, "notes": "Spring", "action": "save"})
        pairing = Pairing.objects.get()
        self.assertRedirects(saved, reverse("pairing_detail", args=[pairing.pk]))
        detail = self.client.get(reverse("pairing_detail", args=[pairing.pk]))
        self.assertContains(detail, "No shared ancestors in the parents")
        self.assertContains(self.client.get(url), "Hazel × Rowan")
        self.client.force_login(stranger.owner)
        self.assertEqual(self.client.get(reverse("pairing_detail", args=[pairing.pk])).status_code, 404)

    def test_nav_lists_pairings(self):
        self.assertContains(self.client.get(reverse("pairing_list")), 'href="/pairings/"')


class PairingCheckTests(TestCase):
    def test_check_by_query_string_warns_on_a_saved_pair(self):
        owner = user("dup@example.com")
        self.client.force_login(owner)
        doe, buck = make(owner, "Clover", "doe"), make(owner, "Basil", "buck")
        url = reverse("pairing_list")
        self.assertNotContains(self.client.get(url, {"doe": doe.pk, "buck": buck.pk}), "data-pair-duplicate")
        Pairing.objects.create(owner=owner, doe=doe, buck=buck)
        page = self.client.get(url, {"doe": doe.pk, "buck": buck.pk})
        self.assertContains(page, "Clover × Basil is already saved.")
        self.assertContains(page, "data-pair-check-btn")


class RelatednessTableTests(TestCase):
    def test_summary_line_and_sorted_ancestor_table(self):
        owner = user("rel@example.com")
        self.client.force_login(owner)
        sire = make(owner, "Obsidian", "buck")
        doe = make(owner, "Shadow", "doe")
        Relative.objects.create(rabbit=doe, relationship="sire", herd_rabbit=sire)
        page = self.client.get(reverse("pairing_list"), {"doe": doe.pk, "buck": sire.pk})
        self.assertContains(page, "Obsidian is Shadow&#x27;s sire")
        self.assertContains(page, "pill pill-r")
        self.assertContains(page, "COI ")
        self.assertNotContains(page, "<li class=\"break-words\">")

    def test_detail_page_uses_the_same_summary(self):
        owner = user("reldetail@example.com")
        self.client.force_login(owner)
        sire, doe = make(owner, "Obsidian", "buck"), make(owner, "Shadow", "doe")
        Relative.objects.create(rabbit=doe, relationship="sire", herd_rabbit=sire)
        pairing = Pairing.objects.create(owner=owner, doe=doe, buck=sire)
        page = self.client.get(reverse("pairing_detail", args=[pairing.pk]))
        self.assertContains(page, "data-inbreeding")
        self.assertContains(page, "Obsidian is Shadow&#x27;s sire")
        self.assertNotContains(page, "Inbreeding warning:")
