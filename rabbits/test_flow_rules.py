import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from . import flow
from .models import Breed, OutsideRabbit, Rabbit, Relative


def breed_id(name):
    return str(Breed.objects.get(name=name).pk)


class FlowTestMixin:
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="keeper@example.com", password="pw-for-tests-only")
        self.other = User.objects.create_user(email="other@example.com", password="pw-for-tests-only")
        self.juniper = self.rabbit("Juniper", "doe")
        self.pepper = self.rabbit("Pepper", "buck")

    def rabbit(self, name, sex, owner=None):
        return Rabbit.objects.create(
            owner=owner or self.user,
            name=name,
            sex=sex,
            breed="Holland Lop",
            color="Black",
            birth_date=datetime.date(2023, 4, 12),
        )

    def draft(self, **changes):
        draft = flow.empty_draft()
        draft.update(
            name="Hazel",
            sex="doe",
            birth_date="2024-05-01",
            color="Fawn",
            status="growing",
            breed_type="purebred",
            purebred=breed_id("Holland Lop"),
        )
        draft.update(changes)
        return draft

    def errors(self, slug, draft):
        form = flow.bound_form(slug, draft, self.user)
        form.is_valid()
        return {key: list(value) for key, value in form.errors.items()}


class SimpleStepTests(FlowTestMixin, TestCase):
    def test_each_basic_question_states_the_rule_then_what_to_do(self):
        draft = flow.empty_draft()
        draft["status"] = ""
        self.assertEqual(self.errors("name", draft), {"name": ["Each rabbit needs a name or an ear tag. Please add one."]})
        self.assertEqual(self.errors("sex", draft), {"sex": ["Each rabbit is recorded as a doe or a buck. Please choose one."]})
        self.assertEqual(self.errors("birth-date", draft), {"birth_date": ["A birth date is required. Please pick one from the calendar."]})
        self.assertEqual(
            self.errors("color", draft),
            {"color": ["A coat color helps tell rabbits apart, so it's required. Please describe the color."]},
        )
        self.assertEqual(self.errors("status", draft), {"status": ["Each rabbit needs a status. Please choose one."]})
        self.assertEqual(
            self.errors("breed-type", draft),
            {"breed_type": ["Each rabbit is either purebred or crossbred. Please choose one."]},
        )

    def test_birth_date_cannot_be_in_the_future_or_malformed(self):
        tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(
            self.errors("birth-date", self.draft(birth_date=tomorrow)),
            {"birth_date": ["The birth date can't be in the future. Please pick today or an earlier date."]},
        )
        self.assertIn("birth_date", self.errors("birth-date", self.draft(birth_date="2024-02-30")))
        self.assertEqual(self.errors("birth-date", self.draft(birth_date=timezone.localdate().isoformat())), {})

    def test_whitespace_is_not_a_name_and_long_text_is_refused(self):
        self.assertIn("name", self.errors("name", self.draft(name="   ")))
        self.assertIn("name", self.errors("name", self.draft(name="x" * 121)))
        self.assertIn("color", self.errors("color", self.draft(color="x" * 81)))

    def test_unknown_choices_are_refused(self):
        self.assertIn("sex", self.errors("sex", self.draft(sex="unicorn")))
        self.assertIn("status", self.errors("status", self.draft(status="napping")))


class BreedStepTests(FlowTestMixin, TestCase):
    def cross(self, *rows):
        draft = self.draft(breed_type="crossbred", purebred="")
        draft["cross"] = [{"breed": breed, "percent": percent} for breed, percent in rows]
        while len(draft["cross"]) < 2:
            draft["cross"].append(flow.blank_cross_row())
        return draft

    def test_purebred_needs_a_breed_from_the_catalog(self):
        self.assertEqual(
            self.errors("breed", self.draft(purebred="")),
            {"purebred": ["A purebred rabbit needs a breed from the list. Please choose one."]},
        )
        self.assertIn("purebred", self.errors("breed", self.draft(purebred="999999")))
        self.assertEqual(self.errors("breed", self.draft()), {})

    def test_breed_type_comes_first(self):
        self.assertEqual(
            self.errors("breed", self.draft(breed_type="")),
            {"__all__": ["The breed choices depend on whether the rabbit is purebred or crossbred. Please choose that first."]},
        )

    def test_shares_must_total_exactly_100(self):
        rex, dutch = breed_id("Rex"), breed_id("Dutch")
        self.assertEqual(
            self.errors("breed", self.cross((rex, "60"), (dutch, "30"))),
            {"__all__": ["The shares need to add up to exactly 100%, and right now they add up to 90%. Please adjust the shares."]},
        )
        self.assertIn("110%", self.errors("breed", self.cross((rex, "60"), (dutch, "50")))["__all__"][0])
        self.assertEqual(self.errors("breed", self.cross((rex, "60"), (dutch, "40"))), {})
        lop = breed_id("Mini Lop")
        self.assertEqual(self.errors("breed", self.cross((rex, "50"), (dutch, "25"), (lop, "25"))), {})

    def test_a_cross_needs_two_different_breeds_with_whole_shares(self):
        rex, dutch = breed_id("Rex"), breed_id("Dutch")
        self.assertEqual(
            self.errors("breed", self.cross((rex, "50"))),
            {"__all__": ["A crossbred rabbit has at least two breeds. Please add another breed to the mix."]},
        )
        repeated = self.errors("breed", self.cross((rex, "50"), (rex, "50")))
        self.assertEqual(
            repeated["cross-1-breed"],
            ["Each breed can be listed only once in a mix. Please choose a different breed, or combine the shares."],
        )
        for bad in ("0", "100", "12.5", "-5", "ten"):
            errors = self.errors("breed", self.cross((rex, bad), (dutch, "50")))
            self.assertEqual(
                errors["cross-0-percent"],
                ["Each share is a whole number from 1 to 99. Please adjust this share."],
                bad,
            )
        missing = self.errors("breed", self.cross(("", "50"), (dutch, "50")))
        self.assertEqual(missing["cross-0-breed"], ["Each row in the mix needs a breed. Please choose one, or clear the share."])

    def test_empty_rows_are_ignored(self):
        rex, dutch = breed_id("Rex"), breed_id("Dutch")
        self.assertEqual(self.errors("breed", self.cross((rex, "50"), ("", ""), (dutch, "50"))), {})


class RelativesStepTests(FlowTestMixin, TestCase):
    def with_relatives(self, *rows):
        draft = self.draft()
        draft["relatives"] = [dict(flow.blank_relative(), **row) for row in rows]
        return draft

    def test_only_one_dam_and_one_sire(self):
        errors = self.errors(
            "relatives",
            self.with_relatives(
                {"relationship": "dam", "ref": f"h:{self.juniper.pk}"},
                {"relationship": "sire", "ref": f"h:{self.pepper.pk}"},
                {"relationship": "dam", "new_name": "Ridgeview Thistle"},
                {"relationship": "sire", "new_name": "Oak Hollow Major"},
            ),
        )
        self.assertEqual(
            errors["relatives-2-relationship"],
            ["A rabbit can have only one dam, and Relative 1 is already listed as the dam. Choose a different relationship here."],
        )
        self.assertEqual(
            errors["relatives-3-relationship"],
            ["A rabbit can have only one sire, and Relative 2 is already listed as the sire. Choose a different relationship here."],
        )

    def test_the_dam_is_a_doe_and_the_sire_a_buck(self):
        errors = self.errors(
            "relatives",
            self.with_relatives(
                {"relationship": "dam", "ref": f"h:{self.pepper.pk}"},
                {"relationship": "sire", "ref": f"h:{self.juniper.pk}"},
            ),
        )
        self.assertEqual(errors["relatives-0-ref"], ["The dam has to be a doe. Pepper is a buck, so pick a doe here."])
        self.assertEqual(errors["relatives-1-ref"], ["The sire has to be a buck. Juniper is a doe, so pick a buck here."])
        # Any sex is fine for other relationships.
        self.assertEqual(
            self.errors("relatives", self.with_relatives({"relationship": "sibling", "ref": f"h:{self.pepper.pk}"})),
            {},
        )

    def test_each_row_names_exactly_one_rabbit(self):
        errors = self.errors(
            "relatives",
            self.with_relatives(
                {"relationship": "cousin"},
                {"relationship": "cousin", "ref": f"h:{self.juniper.pk}", "new_name": "Thistle"},
                {"relationship": "cousin", "new_details": "Tag RV-12"},
                {"relationship": ""},
            ),
        )
        self.assertEqual(errors["relatives-0-ref"], ["Each relative needs a rabbit. Choose one from the list or add an outside rabbit."])
        self.assertEqual(
            errors["relatives-1-new_name"],
            ["Each place holds one rabbit. Choose one from the list or add an outside rabbit, but not both."],
        )
        self.assertEqual(errors["relatives-2-ref"], ["Each relative needs a rabbit. Choose one from the list or add an outside rabbit."])
        self.assertEqual(
            errors["relatives-3-relationship"],
            ["Each relative needs a relationship. Please choose how this rabbit is related."],
        )
        details_only = self.errors(
            "relatives",
            self.with_relatives({"relationship": "cousin", "ref": f"h:{self.juniper.pk}", "new_details": "Tag"}),
        )
        self.assertEqual(details_only["relatives-0-new_name"], ["An outside rabbit needs a name. Add a name, or clear the details."])

    def test_another_keepers_rabbit_is_never_accepted(self):
        stranger = self.rabbit("Stranger", "doe", owner=self.other)
        outside = OutsideRabbit.objects.create(owner=self.other, name="Theirs")
        for ref in (f"h:{stranger.pk}", f"o:{outside.pk}", "h:999999", "x:1", "h:abc"):
            errors = self.errors("relatives", self.with_relatives({"relationship": "dam", "ref": ref}))
            self.assertEqual(errors["relatives-0-ref"], ["That rabbit is no longer in your list. Please choose again."], ref)

    def test_relationship_choices_hide_a_taken_dam_or_sire(self):
        rows = [dict(flow.blank_relative(), relationship="dam"), flow.blank_relative()]
        values = lambda index: [value for value, _ in flow.flow_forms.relationship_choices(rows, index)]
        self.assertIn("dam", values(0))
        self.assertNotIn("dam", values(1))
        self.assertIn("sire", values(1))
        rows[1]["relationship"] = "sire"
        self.assertNotIn("sire", values(0))
        rows[0]["relationship"] = "sibling"
        self.assertIn("dam", values(1))
        # A row always keeps what it already holds.
        rows[0]["relationship"] = "dam"
        rows[1]["relationship"] = "dam"
        self.assertIn("dam", values(1))


class DraftTests(FlowTestMixin, TestCase):
    def test_load_fills_the_shape_and_drops_unknown_or_oversized_values(self):
        session = {
            flow.SESSION_KEY: {
                "name": "x" * 900,
                "cross": [{"breed": "1", "percent": "50", "evil": "y"}],
                "relatives": "not a list",
                "step": "nowhere",
                "is_staff": True,
            }
        }
        draft = flow.load_draft(session)
        self.assertEqual(len(draft["name"]), flow.MAX_TEXT)
        self.assertEqual(draft["cross"], [{"breed": "1", "percent": "50"}, {"breed": "", "percent": ""}])
        self.assertEqual(draft["relatives"], [])
        self.assertEqual(draft["step"], "name")
        self.assertNotIn("is_staff", draft)

    def test_a_card_only_updates_its_own_answers(self):
        draft = self.draft()
        flow.update_draft(draft, "color", {"color": "Blue", "name": "Changed", "sex": "buck"})
        self.assertEqual((draft["color"], draft["name"], draft["sex"]), ("Blue", "Hazel", "doe"))

    def test_row_actions_add_and_remove_within_limits(self):
        draft = self.draft()
        self.assertTrue(flow.apply_row_action(draft, "remove-cross-0"))
        self.assertEqual(len(draft["cross"]), 2, "a cross keeps two rows")
        for _ in range(20):
            flow.apply_row_action(draft, "add-cross")
            flow.apply_row_action(draft, "add-relative")
        self.assertEqual(len(draft["cross"]), flow.flow_forms.MAX_CROSS_ROWS)
        self.assertEqual(len(draft["relatives"]), flow.flow_forms.MAX_RELATIVES)
        flow.apply_row_action(draft, "remove-relative-3")
        self.assertEqual(len(draft["relatives"]), flow.flow_forms.MAX_RELATIVES - 1)
        self.assertFalse(flow.apply_row_action(draft, "next"))

    def test_first_invalid_step(self):
        self.assertEqual(flow.first_invalid_step(self.draft(), self.user), None)
        self.assertEqual(flow.first_invalid_step(self.draft(color=""), self.user), "color")
        self.assertEqual(flow.first_invalid_step(self.draft(color=""), self.user, before="birth-date"), None)


class SaveTests(FlowTestMixin, TestCase):
    def test_saves_a_crossbred_rabbit_with_relatives_in_one_go(self):
        OutsideRabbit.objects.create(owner=self.user, name="Oak Hollow Major", details="")
        draft = self.draft(breed_type="crossbred", purebred="")
        draft["cross"] = [
            {"breed": breed_id("Dutch"), "percent": "40"},
            {"breed": breed_id("Rex"), "percent": "60"},
        ]
        draft["relatives"] = [
            dict(flow.blank_relative(), relationship="dam", ref=f"h:{self.juniper.pk}"),
            dict(flow.blank_relative(), relationship="sire", new_name="oak hollow major"),
            dict(flow.blank_relative(), relationship="cousin", new_name="Sunny Acres Ruby", new_details="Tag 7"),
        ]
        rabbit = flow.save_rabbit(draft, self.user)
        self.assertEqual(rabbit.owner, self.user)
        self.assertEqual(rabbit.breed, "Cross: 60% Rex, 40% Dutch")
        self.assertEqual(rabbit.breed_line(), "Cross: 60% Rex, 40% Dutch")
        self.assertEqual(rabbit.breed_shares.count(), 2)
        relatives = {relative.relationship: relative for relative in rabbit.relatives.all()}
        self.assertEqual(relatives["dam"].herd_rabbit, self.juniper)
        self.assertEqual(relatives["sire"].outside.name, "Oak Hollow Major", "an existing outside rabbit is reused")
        self.assertEqual(OutsideRabbit.objects.filter(owner=self.user).count(), 2)
        self.assertEqual(relatives["cousin"].outside.details, "Tag 7")
        self.assertFalse(rabbit.pedigree_entries.exists())

    def test_saves_a_purebred_rabbit(self):
        rabbit = flow.save_rabbit(self.draft(), self.user)
        self.assertEqual((rabbit.breed_type, rabbit.purebred.name, rabbit.breed), ("purebred", "Holland Lop", "Holland Lop"))
        self.assertEqual(rabbit.birth_date, datetime.date(2024, 5, 1))

    def test_refuses_to_save_and_names_the_first_failing_step(self):
        draft = self.draft()
        draft["relatives"] = [dict(flow.blank_relative(), relationship="dam", ref=f"h:{self.pepper.pk}")]
        with self.assertRaises(flow.DraftNotReady) as raised:
            flow.save_rabbit(draft, self.user)
        self.assertEqual(raised.exception.slug, "relatives")
        self.assertFalse(Rabbit.objects.filter(name="Hazel").exists())
        self.assertFalse(Relative.objects.exists())

    def test_a_long_mix_is_shortened_for_the_list(self):
        self.assertEqual(len(flow.short_breed("x" * 120)), 80)
