import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.admin.sites import site
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from rabbits.models import Rabbit

MEDIA_ROOT = Path(tempfile.mkdtemp())


def make_user(email):
    return User.objects.create_user(
        email=email,
        password="Rabbit-Herd-Pass-1",
        is_active=True,
        email_confirmed=True,
    )


def rabbit_fields(**overrides):
    data = {
        "name": "Clover",
        "sex": Rabbit.Sex.DOE,
        "breed": "Dutch",
        "color": "Black",
        "birth_date": "2024-03-01",
        "status": Rabbit.Status.BREEDING,
    }
    data.update(overrides)
    return data


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RabbitRecordTests(TestCase):
    def setUp(self):
        self.owner = make_user("frank@example.com")
        self.other = make_user("other@example.com")
        self.client.force_login(self.owner)

    def test_anonymous_visitor_is_sent_to_sign_in(self):
        self.client.logout()

        response = self.client.get(reverse("rabbit_list"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('rabbit_list')}",
        )

    def clover(self):
        return Rabbit.objects.create(owner=self.owner, **rabbit_fields())

    def test_add_a_rabbit_opens_the_card_flow(self):
        listing = self.client.get(reverse("rabbit_list"))
        self.assertContains(listing, f'href="{reverse("rabbit_create")}"')
        self.assertRedirects(
            self.client.get(reverse("rabbit_create")),
            reverse("rabbit_flow_step", args=["name"]),
        )
        self.assertEqual(self.client.post(reverse("rabbit_create"), rabbit_fields()).status_code, 405)
        self.assertEqual(Rabbit.objects.count(), 0)

    def test_add_a_rabbit_resumes_an_unfinished_draft(self):
        self.client.post(reverse("rabbit_flow_step", args=["name"]), {"name": "Hazel", "action": "next"})
        self.assertRedirects(
            self.client.get(reverse("rabbit_create")),
            reverse("rabbit_flow_step", args=["sex"]),
        )

    def test_owner_can_edit_a_rabbit(self):
        rabbit = self.clover()

        card = lambda slug: reverse("rabbit_edit_step", args=[rabbit.pk, slug])
        self.client.post(card("name"), {"name": "Clover 2", "action": "next"})
        self.client.post(card("status"), {"status": Rabbit.Status.SOLD, "action": "next"})
        edited = self.client.post(reverse("rabbit_edit", args=[rabbit.pk]), {"action": "save"})
        self.assertRedirects(edited, reverse("rabbit_detail", args=[rabbit.pk]))
        rabbit.refresh_from_db()
        self.assertEqual(rabbit.name, "Clover 2")
        self.assertEqual(rabbit.status, Rabbit.Status.SOLD)

        detail = self.client.get(reverse("rabbit_detail", args=[rabbit.pk]))
        self.assertContains(detail, "Clover 2")
        self.assertContains(detail, "Sold")
        self.assertContains(detail, "Dutch")

    def test_users_only_see_their_own_rabbits(self):
        own = Rabbit.objects.create(
            owner=self.owner,
            name="Clover",
            sex=Rabbit.Sex.DOE,
            breed="Dutch",
            color="Black",
            birth_date="2024-03-01",
            status=Rabbit.Status.BREEDING,
        )
        hidden = Rabbit.objects.create(
            owner=self.other,
            name="Hidden",
            sex=Rabbit.Sex.BUCK,
            breed="Rex",
            color="White",
            birth_date="2024-04-01",
            status=Rabbit.Status.GROWING,
        )

        listing = self.client.get(reverse("rabbit_list"))
        self.assertContains(listing, "Clover")
        self.assertNotContains(listing, "Hidden")

        self.assertEqual(self.client.get(reverse("rabbit_detail", args=[hidden.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("rabbit_edit", args=[hidden.pk])).status_code, 404)
        self.assertEqual(
            self.client.post(reverse("rabbit_archive", args=[hidden.pk])).status_code,
            404,
        )
        hidden.refresh_from_db()
        self.assertIsNone(hidden.archived_at)

        self.client.force_login(self.other)
        other_list = self.client.get(reverse("rabbit_list"))
        self.assertContains(other_list, "Hidden")
        self.assertNotContains(other_list, "Clover")
        self.assertEqual(self.client.get(reverse("rabbit_detail", args=[own.pk])).status_code, 404)

    def test_archive_hides_the_rabbit_and_restore_brings_it_back(self):
        rabbit = Rabbit.objects.create(
            owner=self.owner,
            name="Clover",
            sex=Rabbit.Sex.DOE,
            breed="Dutch",
            color="Black",
            birth_date="2024-03-01",
            status=Rabbit.Status.CULLED,
        )

        archived = self.client.post(reverse("rabbit_archive", args=[rabbit.pk]))
        self.assertRedirects(archived, reverse("rabbit_list"))
        rabbit.refresh_from_db()
        self.assertIsNotNone(rabbit.archived_at)
        self.assertEqual(Rabbit.objects.count(), 1)

        active = self.client.get(reverse("rabbit_list"))
        self.assertNotContains(active, "Open Clover")
        self.assertContains(active, "No rabbits yet.")

        stored = self.client.get(reverse("rabbit_archived"))
        self.assertContains(stored, "Clover")
        self.assertContains(stored, "Culled")

        restored = self.client.post(reverse("rabbit_restore", args=[rabbit.pk]))
        self.assertRedirects(restored, reverse("rabbit_detail", args=[rabbit.pk]))
        rabbit.refresh_from_db()
        self.assertIsNone(rabbit.archived_at)
        # A culled rabbit comes back to the Former tab, not the active herd.
        self.assertContains(self.client.get(reverse("rabbit_list"), {"tab": "former"}), "Clover")
        self.assertContains(self.client.get(reverse("rabbit_archived")), "No archived rabbits.")

    def test_form_rejects_a_missing_name_and_a_future_birth_date(self):
        rabbit = self.clover()
        card = lambda slug: reverse("rabbit_edit_step", args=[rabbit.pk, slug])
        missing = self.client.post(card("name"), {"name": "", "action": "next"}, follow=True)
        self.assertContains(missing, "Add a name or ear tag.")

        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        future = self.client.post(card("birth-date"), {"birth_date": tomorrow, "action": "next"}, follow=True)
        self.assertContains(future, "The birth date can&#x27;t be in the future.")
        saved = self.client.post(reverse("rabbit_edit", args=[rabbit.pk]), {"action": "save"})
        self.assertRedirects(saved, card("name") + "?check=1")
        rabbit.refresh_from_db()
        self.assertEqual((rabbit.name, rabbit.birth_date.isoformat()), ("Clover", "2024-03-01"))

    def test_admin_cannot_delete_a_rabbit(self):
        self.assertFalse(site._registry[Rabbit].has_delete_permission(None))
