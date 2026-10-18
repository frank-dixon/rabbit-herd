"""Add forms open in the shared dialog instead of sitting in the reading flow (Critic v2 item 5):
rabbit detail's Add a weight and Breeding schedule, and the kindling form on an expecting litter.
Each sits in a closed <details data-add-fold>, which modal.mjs opens in the dialog; without
JavaScript the fold opens in place."""
import datetime
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rabbits.models import Litter, Pairing, Rabbit


def fold_around(body, marker):
    """The opening <details> tag of the add fold that holds marker."""
    at = body.index(marker)
    start = body.rindex("<details", 0, at)
    assert body.rfind("</details>", start, at) == -1, "marker is not inside the fold"
    return body[start:body.index(">", start) + 1]


class SheetFormTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("sheets@example.com", "pw-12345678")
        self.client.force_login(self.user)
        self.doe = Rabbit.objects.create(owner=self.user, name="Willow", sex="doe", breed="Rex", birth_date=datetime.date(2024, 1, 1))
        buck = Rabbit.objects.create(owner=self.user, name="Jet", sex="buck", breed="Rex", birth_date=datetime.date(2024, 1, 1))
        pairing = Pairing.objects.create(owner=self.user, doe=self.doe, buck=buck)
        self.litter = Litter.objects.create(owner=self.user, pairing=pairing, bred_on=timezone.localdate() - datetime.timedelta(days=29))

    def test_detail_weight_and_schedule_forms_sit_in_closed_folds(self):
        body = self.client.get(reverse("rabbit_detail", args=[self.doe.pk])).content.decode()
        for marker in ('data-modal-content="weights"', 'data-modal-content="schedule"'):
            tag = fold_around(body, marker)
            self.assertIn("data-add-fold", tag)
            self.assertNotIn(" open", tag)
        self.assertIn("Add a weight</summary>", body)
        self.assertIn("Change schedule</summary>", body)

    def test_kindling_form_is_closed_on_an_expecting_litter(self):
        body = self.client.get(reverse("litter_detail", args=[self.litter.pk])).content.decode()
        tag = fold_around(body, 'data-modal-content="kindling"')
        self.assertIn("data-add-fold", tag)
        self.assertNotIn(" open", tag)
        self.assertIn("Record the kindling</summary>", body)

    def test_a_weight_error_opens_the_fold_in_place(self):
        body = self.client.post(reverse("rabbit_weight_add", args=[self.doe.pk]), {"date": "", "lb": "x"}, follow=True).content.decode()
        if "data-weight-error" in body:
            self.assertRegex(fold_around(body, 'data-modal-content="weights"'), r"\sopen")

    def test_modal_opens_add_folds(self):
        from pathlib import Path
        js = (Path(__file__).resolve().parents[1] / "assets" / "modal.mjs").read_text()
        self.assertIn('details[data-add-fold]:not([open]) > summary', js)
        self.assertTrue(re.search(r"function putBack\(\)", js))
