"""An outside relative added on the relatives step can go straight into the
herd as a full rabbit, keeping its color, line and genes."""

from django.test import TestCase
from django.urls import reverse

from . import flow
from .models import OutsideRabbit, Rabbit
from .test_flow_rules import FlowTestMixin


def step(slug):
    return reverse("rabbit_flow_step", args=[slug])


class RelativeToHerdTests(FlowTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        session = self.client.session
        session[flow.SESSION_KEY] = self.draft(step="relatives")
        session.save()
        self.client.post(step("relatives"), {"action": "add-relative"})

    def post(self, **extra):
        data = {
            "relatives-0-relationship": "dam", "relatives-0-new_name": "Willow",
            "relatives-0-color": "Broken blue", "relatives-0-line": "Ridgeview",
            "relatives-0-gene_D": "dd", "relatives-0-cert_D": "known",
            "relatives-0-to_herd": "on", "action": "next",
        }
        data.update(extra)
        return self.client.post(step("relatives"), data)

    def test_dam_becomes_a_herd_doe_with_her_genes(self):
        self.post(**{"relatives-0-herd_born": "2024-03-01"})
        session = self.client.session
        session[flow.SESSION_KEY] = dict(session[flow.SESSION_KEY], step="review")
        session.save()
        self.client.post(step("review"), {"action": "next"})
        hazel = Rabbit.objects.get(name="Hazel")
        willow = Rabbit.objects.get(name="Willow", owner=self.user)
        self.assertEqual((willow.sex, str(willow.birth_date), willow.color, willow.line), ("doe", "2024-03-01", "Broken blue", "Ridgeview"))
        self.assertEqual(willow.genes.get(locus="D").genotype, "dd")
        relative = hazel.relatives.get()
        self.assertEqual((relative.herd_rabbit, relative.outside), (willow, None))
        self.assertFalse(OutsideRabbit.objects.filter(name="Willow").exists())

    def test_birth_date_is_required_and_the_fields_show_without_js(self):
        response = self.post()
        page = self.client.get(response["Location"]) if response.status_code == 302 else response
        self.assertContains(page, "Please enter the birth date to add this rabbit", status_code=page.status_code)
        self.assertContains(page, "data-to-herd-fields", status_code=page.status_code)
        self.assertFalse(Rabbit.objects.filter(name="Willow").exists())

    def test_unticked_stays_an_outside_rabbit(self):
        self.post(**{"relatives-0-to_herd": "", "relatives-0-herd_born": "2024-03-01"})
        session = self.client.session
        session[flow.SESSION_KEY] = dict(session[flow.SESSION_KEY], step="review")
        session.save()
        self.client.post(step("review"), {"action": "next"})
        self.assertFalse(Rabbit.objects.filter(name="Willow").exists())
        self.assertTrue(OutsideRabbit.objects.filter(name="Willow").exists())
