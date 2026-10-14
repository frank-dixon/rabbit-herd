"""The edit draft: reading a saved rabbit, legacy breed text, and saving."""

import datetime

from django.test import TestCase

from . import flow
from .models import Breed, Gene, OutsideRabbit, Relative
from .test_flow_rules import FlowTestMixin


def breed(name):
    return Breed.objects.get(name=name)


class LegacyBreedTests(TestCase):
    def test_reads_a_purebred_ignoring_case_and_accents(self):
        self.assertEqual(flow.parse_legacy_breed("crème d'argent"), ("purebred", breed("Creme d'Argent"), []))

    def test_reads_a_cross_with_shares(self):
        kind, purebred, parts = flow.parse_legacy_breed(
            "Cross: 50% Creme d'Argent, 25% Flemish Giant, 25% New Zealand"
        )
        self.assertEqual((kind, purebred), ("crossbred", None))
        self.assertEqual(
            parts, [(breed("Creme d'Argent"), 50), (breed("Flemish Giant"), 25), (breed("New Zealand"), 25)]
        )

    def test_reads_a_cross_cut_short_with_an_ellipsis(self):
        _, _, parts = flow.parse_legacy_breed("Cross: 50% Creme d'Argent, 25% Flemish Giant, 25% New Ze…")
        self.assertEqual(parts[-1], (breed("New Zealand"), 25))

    def test_same_breed_twice_is_a_purebred(self):
        self.assertEqual(flow.parse_legacy_breed("Cross: 50% New Zealand, 50% New Zealand")[0], "purebred")

    def test_unreadable_text_is_none(self):
        for text in ("", "mutt", "Cross: 60% Rex, 30% Dutch", "New Zealand, Flemish Giant"):
            self.assertIsNone(flow.parse_legacy_breed(text), text)


class DraftFromRabbitTests(FlowTestMixin, TestCase):
    def test_a_legacy_cross_fills_the_mix_rows(self):
        self.juniper.breed = "Cross: 50% Creme d'Argent, 25% Flemish Giant, 25% New Ze…"
        self.juniper.line = "Ridgeview"
        self.juniper.save()
        draft = flow.draft_from_rabbit(self.juniper)
        self.assertEqual(draft["breed_type"], "crossbred")
        self.assertEqual([row["percent"] for row in draft["cross"]], ["50", "25", "25"])
        self.assertEqual((draft["name"], draft["line"], draft["birth_date"]), ("Juniper", "Ridgeview", "2023-04-12"))
        self.assertIsNone(flow.first_invalid_step(draft, self.user, steps=flow.EDIT_STEPS))

    def test_unreadable_breed_is_kept_and_asked_again(self):
        self.juniper.breed = "barn mix"
        self.juniper.save()
        draft = flow.draft_from_rabbit(self.juniper)
        self.assertEqual((draft["breed_type"], draft["legacy_breed"]), ("", "barn mix"))
        self.assertEqual(flow.first_invalid_step(draft, self.user, steps=flow.EDIT_STEPS), "breed-type")

    def test_a_listed_color_is_chosen_and_relatives_come_back(self):
        self.juniper.breed = "Creme d'Argent"
        self.juniper.color = "creme"
        self.juniper.save()
        snow = OutsideRabbit.objects.create(owner=self.user, name="Snow")
        dam = Relative.objects.create(rabbit=self.juniper, relationship="dam", outside=snow, line="Ridgeview")
        Gene.objects.create(relative=dam, locus="C", genotype="c/c", certainty="known")
        draft = flow.draft_from_rabbit(self.juniper)
        self.assertEqual(draft["color_choice"], breed("Creme d'Argent").colors[0]["name"])
        row = draft["relatives"][0]
        self.assertEqual((row["ref"], row["line"], row["gene_C"], row["cert_C"]), (f"o:{snow.pk}", "Ridgeview", "c/c", "known"))


class UpdateRabbitTests(FlowTestMixin, TestCase):
    def test_saves_a_cross_and_relatives_and_replaces_old_ones(self):
        Relative.objects.create(rabbit=self.juniper, relationship="sire", herd_rabbit=self.pepper)
        draft = flow.draft_from_rabbit(self.juniper)
        nz, fg = breed("New Zealand"), breed("Flemish Giant")
        draft.update(breed_type="crossbred", purebred="", color="Black head, fawn silvering", color_choice="", line="Oak")
        draft["cross"] = [{"breed": str(nz.pk), "percent": "75"}, {"breed": str(fg.pk), "percent": "25"}]
        draft["relatives"][0].update(gene_En="En/en", cert_En="known")
        rabbit = flow.update_rabbit(draft, self.user, self.juniper)
        rabbit.refresh_from_db()
        self.assertEqual(rabbit.breed, "Cross: 75% New Zealand, 25% Flemish Giant")
        self.assertEqual((rabbit.breed_type, rabbit.line, rabbit.purebred), ("crossbred", "Oak", None))
        self.assertEqual(sorted(rabbit.breed_shares.values_list("percent", flat=True)), [25, 75])
        relative = rabbit.relatives.get()
        # A herd relative's genes live on its own page, so the row keeps none.
        self.assertEqual((relative.herd_rabbit, relative.genes.count()), (self.pepper, 0))

    def test_refuses_a_future_birth_date_and_self_relative(self):
        draft = flow.draft_from_rabbit(self.juniper)
        draft["breed_type"], draft["purebred"] = "purebred", str(breed("New Zealand").pk)
        draft["birth_date"] = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
        with self.assertRaises(flow.DraftNotReady) as caught:
            flow.update_rabbit(draft, self.user, self.juniper)
        self.assertEqual(caught.exception.slug, "birth-date")
        draft["birth_date"] = "2024-01-01"
        draft["relatives"] = [dict(flow.blank_relative(), relationship="sibling", ref=f"h:{self.juniper.pk}")]
        with self.assertRaises(flow.DraftNotReady) as caught:
            flow.update_rabbit(draft, self.user, self.juniper)
        self.assertEqual(caught.exception.slug, "relatives")
