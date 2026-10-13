import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import flow
from .models import Breed, BreedShare, Rabbit


def bid(name):
    return Breed.objects.get(name=name).pk


class ParentsFirstTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="pf@example.com", password="pw-for-tests-only")
        self.client.force_login(self.user)
        make = lambda **kw: Rabbit.objects.create(owner=self.user, color="Black", birth_date=datetime.date(2023, 1, 1), **kw)
        self.dam = make(name="Willow", sex="doe", breed="New Zealand", breed_type="purebred", purebred_id=bid("New Zealand"))
        self.sire = make(name="Snow", sex="buck", breed="New Zealand", breed_type="purebred", purebred_id=bid("New Zealand"))
        self.cross_sire = make(name="Jet", sex="buck", breed="Cross", breed_type="crossbred")
        BreedShare.objects.create(rabbit=self.cross_sire, breed_id=bid("Rex"), percent=50)
        BreedShare.objects.create(rabbit=self.cross_sire, breed_id=bid("Dutch"), percent=50)

    def post(self, url, **data):
        return self.client.post(url, {"action": "next", **data})

    def add_rows(self, url):
        self.client.post(url, {"action": "add-relative"})
        self.client.post(url, {"action": "add-relative"})

    def parents(self, sire):
        return {"relatives-0-relationship": "dam", "relatives-0-ref": f"h:{self.dam.pk}",
                "relatives-1-relationship": "sire", "relatives-1-ref": f"h:{sire.pk}"}

    def test_relatives_come_last_in_both_flows(self):
        # Frank, Oct 2026: the optional relatives card moved to just before the review.
        self.assertEqual(flow.SLUGS[-2:], ["relatives", "review"])
        self.assertEqual(flow.EDIT_SLUGS[-2:], ["relatives", "line"])

    def prefill(self, sire):
        """The parents fill an empty breed (still used when a breed is unanswered, as in the edit flow)."""
        draft = flow.empty_draft()
        draft.update(name="Kit", sex="doe", birth_date="2026-05-01", relatives=[flow.blank_relative(), flow.blank_relative()])
        for key, value in self.parents(sire).items():
            index, field = key.split("-")[1], key.split("-", 2)[2]
            draft["relatives"][int(index)][field] = value
        form = flow.bound_form("relatives", draft, self.user)
        self.assertTrue(form.is_valid(), form.errors)
        return draft, flow.prefill_breed_from_parents(draft, form.cleaned_data["relatives"])

    def test_same_breed_parents_prefill_a_purebred(self):
        draft, filled = self.prefill(self.sire)
        self.assertEqual(filled, "New Zealand")
        self.assertEqual((draft["breed_type"], draft["purebred"]), ("purebred", str(bid("New Zealand"))))

    def test_mixed_parents_prefill_half_of_each(self):
        draft, _ = self.prefill(self.cross_sire)
        self.assertEqual(draft["breed_type"], "crossbred")
        self.assertEqual(flow.draft_breed_line(draft), "Cross: 50% New Zealand, 25% Dutch, 25% Rex")

    def test_an_answered_breed_is_never_overwritten(self):
        kid = Rabbit.objects.create(owner=self.user, name="Kid", sex="doe", birth_date=datetime.date(2026, 5, 1),
                                    color="Black", breed="Rex", breed_type="purebred", purebred_id=bid("Rex"))
        url = reverse("rabbit_edit_step", args=[kid.pk, "relatives"])
        self.client.get(url)
        self.add_rows(url)
        self.assertRedirects(self.post(url, **self.parents(self.sire)), reverse("rabbit_edit", args=[kid.pk]))
        draft = flow.load_draft(self.client.session, flow.edit_key(kid.pk))
        self.assertEqual(draft["purebred"], str(bid("Rex")))

    def test_one_parent_or_unknown_breed_leaves_the_breed_alone(self):
        draft = flow.empty_draft()
        rows = [{"relationship": "dam", "target": self.dam}]
        self.assertEqual(flow.prefill_breed_from_parents(draft, rows), "")
        rows.append({"relationship": "sire", "target": None, "breed": "barn mix"})
        self.assertEqual(flow.prefill_breed_from_parents(draft, rows), "")
        self.assertEqual(draft["breed_type"], "")
