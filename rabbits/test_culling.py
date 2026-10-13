import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CullNote, Litter, Pairing, Rabbit
from .test_contacts import user


class CullingTests(TestCase):
    def setUp(self):
        self.owner = user("cull@example.com")
        self.client.force_login(self.owner)
        base = {"owner": self.owner, "breed": "Rex", "color": "Black"}
        doe = Rabbit.objects.create(name="Mom", sex="doe", birth_date=datetime.date(2024, 1, 1), **base)
        buck = Rabbit.objects.create(name="Dad", sex="buck", birth_date=datetime.date(2024, 1, 1), **base)
        self.litter = Litter.objects.create(owner=self.owner, pairing=Pairing.objects.create(owner=self.owner, doe=doe, buck=buck),
                                            bred_on=datetime.date(2026, 5, 1), kindled_on=datetime.date(2026, 6, 1), born_alive=2)
        self.kit = Rabbit.objects.create(name="Kit", sex="doe", birth_date=datetime.date(2026, 6, 1), litter=self.litter, **base)
        self.today = timezone.localdate()
        self.detail = reverse("rabbit_detail", args=[self.kit.pk])

    def test_add_edit_and_remove(self):
        self.client.post(reverse("rabbit_cull_add", args=[self.kit.pk]),
                         {"cull_date": self.today.isoformat(), "cull_decision": "undecided", "cull_reason": "Narrow shoulders"})
        note = CullNote.objects.get()
        page = self.client.get(self.detail)
        self.assertContains(page, "Narrow shoulders")
        self.assertContains(page, "Add an evaluation")
        editing = self.client.get(self.detail + f"?cull={note.pk}")
        self.assertContains(editing, "Edit the evaluation from")
        self.assertContains(editing, reverse("rabbit_cull_edit", args=[note.pk]))
        self.assertContains(editing, '<option value="undecided" selected')
        self.client.post(reverse("rabbit_cull_edit", args=[note.pk]),
                         {"cull_date": self.today.isoformat(), "cull_decision": "cull", "cull_reason": "Narrow shoulders, poor fur"})
        note.refresh_from_db()
        self.assertEqual((note.decision, note.reason), ("cull", "Narrow shoulders, poor fur"))
        litter_page = self.client.get(reverse("litter_detail", args=[self.litter.pk]))
        self.assertContains(litter_page, 'data-kit-decision="cull"')
        self.assertContains(litter_page, "poor fur")
        self.client.post(reverse("rabbit_cull_delete", args=[note.pk]))
        self.assertFalse(CullNote.objects.exists())
        self.assertContains(self.client.get(reverse("litter_detail", args=[self.litter.pk])), "Evaluate")

    def test_bad_input(self):
        url = reverse("rabbit_cull_add", args=[self.kit.pk])
        for data, msg in (
            ({"cull_date": "", "cull_decision": "keep"}, "Please enter the date"),
            ({"cull_date": (self.today + datetime.timedelta(days=1)).isoformat(), "cull_decision": "keep"}, "in the future"),
            ({"cull_date": self.today.isoformat(), "cull_decision": "maybe"}, "keep, cull or undecided"),
        ):
            self.assertContains(self.client.post(url, data, follow=True), msg)
        self.assertFalse(CullNote.objects.exists())
        note = CullNote.objects.create(rabbit=self.kit, date=self.today, decision="keep")
        response = self.client.post(reverse("rabbit_cull_edit", args=[note.pk]), {"cull_date": "", "cull_decision": "keep"})
        self.assertRedirects(response, self.detail + f"?cull={note.pk}#culling", fetch_redirect_response=False)

    def test_owner_scope(self):
        note = CullNote.objects.create(rabbit=self.kit, date=self.today, decision="keep")
        self.client.force_login(user("x@example.com"))
        data = {"cull_date": self.today.isoformat(), "cull_decision": "cull"}
        self.assertEqual(self.client.post(reverse("rabbit_cull_add", args=[self.kit.pk]), data).status_code, 404)
        self.assertEqual(self.client.post(reverse("rabbit_cull_edit", args=[note.pk]), data).status_code, 404)
        self.assertEqual(self.client.post(reverse("rabbit_cull_delete", args=[note.pk])).status_code, 404)
