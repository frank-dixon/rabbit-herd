import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from . import flow
from .models import Breed, Rabbit


def step(slug):
    return reverse("rabbit_flow_step", args=[slug])


def breed_id(name):
    return str(Breed.objects.get(name=name).pk)


class CardFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="keeper@example.com", password="pw-for-tests-only")
        self.client.force_login(self.user)
        self.juniper = Rabbit.objects.create(
            owner=self.user, name="Juniper", sex="doe", breed="Holland Lop", color="Black",
            birth_date=datetime.date(2023, 4, 12),
        )
        self.pepper = Rabbit.objects.create(
            owner=self.user, name="Pepper", sex="buck", breed="Mini Lop", color="Broken chocolate",
            birth_date=datetime.date(2024, 3, 8),
        )

    def answer(self, slug, **fields):
        return self.client.post(step(slug), dict(fields, action=fields.pop("action", "next")))

    def fails(self, slug, **fields):
        """Post a card that should not pass, and open the page that shows why."""
        response = self.answer(slug, **fields)
        self.assertRedirects(response, step(slug) + "?check=1", fetch_redirect_response=False)
        return self.client.get(response["Location"])

    def walk_to_breed(self, breed_type="purebred"):
        self.answer("name", name="Hazel")
        self.answer("sex", sex="doe")
        self.answer("birth-date", birth_date="2024-05-01")
        self.answer("status", status="growing")
        return self.answer("breed-type", breed_type=breed_type)

    def choose_breed(self, name="Holland Lop", color="Fawn"):
        """Answer the breed card, then the color card that follows it."""
        self.assertRedirects(self.answer("breed", purebred=breed_id(name)), step("color"))
        return self.answer("color", color=color)

    def draft(self):
        return flow.load_draft(self.client.session)

    def test_every_card_needs_a_signed_in_keeper(self):
        anonymous = Client()
        for url in (step("name"), step("review"), reverse("rabbit_flow_done", args=[self.juniper.pk])):
            response = anonymous.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn(reverse("login"), response["Location"])
        response = anonymous.post(reverse("rabbit_flow_restart"))
        self.assertIn(reverse("login"), response["Location"])

    def test_posts_need_a_csrf_token(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(step("name"), {"name": "Hazel", "action": "next"}).status_code, 403)
        page = strict.get(step("name"))
        token = page.context["csrf_token"]
        self.assertEqual(
            strict.post(step("name"), {"name": "Hazel", "action": "next", "csrfmiddlewaretoken": str(token)}).status_code,
            302,
        )

    def test_first_card_uses_the_approved_copy_and_big_controls(self):
        response = self.client.get(step("name"))
        self.assertContains(response, "What is this rabbit&#x27;s name or ear tag?")
        self.assertContains(response, "Use whatever you go by to tell this rabbit apart.")
        self.assertContains(response, "Question 1 of 9")
        self.assertContains(response, '<label class="sr-only" for="id_name">Name or ear tag</label>', html=False)
        self.assertContains(response, "min-h-14")
        self.assertContains(response, "Start over")
        self.assertNotContains(response, 'value="back"')

    def test_next_checks_the_card_and_shows_the_error_summary(self):
        response = self.fails("name", name="  ")
        self.assertEqual(self.draft()["step"], "name")
        self.assertContains(response, "Please check one thing before continuing:")
        self.assertContains(response, 'href="#id_name"')
        self.assertContains(response, "Each rabbit needs a name or an ear tag. Please add one.")
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'aria-describedby="id_name_error"')

    def test_answers_carry_into_later_questions_and_survive_a_reload(self):
        self.assertRedirects(self.answer("name", name="Hazel"), step("sex"))
        response = self.client.get(step("sex"))
        self.assertContains(response, "Is Hazel a doe or a buck?")
        self.assertContains(response, "Female")
        self.answer("sex", sex="doe")
        # A fresh request reads the draft back from the session.
        self.assertContains(self.client.get(step("name")), 'value="Hazel"')
        self.assertContains(self.client.get(step("sex")), 'value="doe" checked')

    def test_back_keeps_typing_without_checking(self):
        self.answer("name", name="Hazel")
        response = self.answer("sex", action="back")
        self.assertRedirects(response, step("name"))
        self.answer("name", name="", action="back")
        self.assertEqual(self.draft()["name"], "")

    def test_a_later_card_sends_people_back_to_the_first_missing_answer(self):
        response = self.client.get(step("breed"))
        self.assertRedirects(response, step("name") + "?check=1", fetch_redirect_response=False)
        page = self.client.get(step("name") + "?check=1")
        self.assertContains(page, "Each rabbit needs a name or an ear tag. Please add one.")

    def test_color_comes_right_after_the_breed(self):
        self.assertEqual(
            flow.SLUGS,
            ["name", "sex", "birth-date", "status", "breed-type", "breed", "color", "relatives", "review"],
        )
        self.walk_to_breed("purebred")
        self.assertRedirects(self.answer("breed", purebred=breed_id("Creme d'Argent")), step("color"))
        self.assertRedirects(self.answer("color", color="Creme"), step("relatives"))
        # The color card waits for a breed.
        self.client.post(reverse("rabbit_flow_restart"))
        self.walk_to_breed("purebred")
        self.assertRedirects(self.client.get(step("color")), step("breed") + "?check=1", fetch_redirect_response=False)

    def test_unknown_cards_are_missing(self):
        self.assertEqual(self.client.get(step("pedigree")).status_code, 404)

    def test_the_birth_date_uses_the_native_picker_and_refuses_the_future(self):
        self.answer("name", name="Hazel")
        self.answer("sex", sex="doe")
        page = self.client.get(step("birth-date"))
        self.assertContains(page, 'type="date"')
        self.assertContains(page, f'max="{timezone.localdate().isoformat()}"')
        tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        response = self.fails("birth-date", birth_date=tomorrow)
        self.assertContains(
            response,
            "The birth date can&#x27;t be in the future. Please pick today or an earlier date.",
        )

    def test_purebred_shows_one_grouped_select(self):
        self.walk_to_breed("purebred")
        page = self.client.get(step("breed"))
        self.assertContains(page, "Which breed is Hazel?")
        self.assertContains(page, 'optgroup label="ARBA recognized (53)"')
        self.assertContains(page, 'optgroup label="Other recognized breeds (33)"')
        self.assertContains(page, "https://arba.net/recognized-breeds/")
        self.assertNotContains(page, "Breeds in the mix")

    def test_crossbred_rows_add_remove_and_total_without_javascript(self):
        self.walk_to_breed("crossbred")
        page = self.client.get(step("breed"))
        self.assertContains(page, "Which breeds make up Hazel&#x27;s mix?")
        self.assertContains(page, "Total so far: 0%. Add 100% more to reach 100%.")
        self.assertNotContains(page, 'value="remove-cross-0"')
        rex, dutch, lop = breed_id("Rex"), breed_id("Dutch"), breed_id("Mini Lop")
        response = self.answer(
            "breed", action="add-cross",
            **{"cross-0-breed": rex, "cross-0-percent": "50", "cross-1-breed": dutch, "cross-1-percent": "30"},
        )
        self.assertRedirects(response, step("breed") + "#id_cross-2-breed", fetch_redirect_response=False)
        page = self.client.get(step("breed"))
        self.assertContains(page, "Total so far: 80%. Add 20% more to reach 100%.")
        self.assertContains(page, 'value="remove-cross-2"')
        response = self.fails(
            "breed",
            **{"cross-0-breed": rex, "cross-0-percent": "50", "cross-1-breed": dutch, "cross-1-percent": "30",
               "cross-2-breed": lop, "cross-2-percent": "30"},
        )
        self.assertContains(
            response,
            "The shares need to add up to exactly 100%, and right now they add up to 110%. Please adjust the shares.",
        )
        self.assertContains(response, "That&#x27;s 10% over, so lower a share.")
        self.answer("breed", action="remove-cross-2")
        self.assertEqual(len(self.draft()["cross"]), 2)
        response = self.answer(
            "breed", **{"cross-0-breed": rex, "cross-0-percent": "70", "cross-1-breed": dutch, "cross-1-percent": "30"},
        )
        self.assertRedirects(response, step("color"))

    def test_a_repeated_breed_in_the_mix_is_added_together(self):
        self.walk_to_breed("crossbred")
        rex, dutch = breed_id("Rex"), breed_id("Dutch")
        self.answer("breed", action="add-cross")
        response = self.answer(
            "breed",
            **{"cross-0-breed": rex, "cross-0-percent": "25", "cross-1-breed": dutch, "cross-1-percent": "50",
               "cross-2-breed": rex, "cross-2-percent": "25"},
        )
        self.assertRedirects(response, step("color"))
        self.assertEqual(self.draft()["cross"], [{"breed": rex, "percent": "50"}, {"breed": dutch, "percent": "50"}])

    def test_relatives_hide_a_taken_dam_and_reject_a_second_one(self):
        self.walk_to_breed("purebred")
        self.choose_breed()
        page = self.client.get(step("relatives"))
        self.assertContains(page, "No relatives added yet. You can add some now or skip this step.")
        self.assertContains(page, ">Skip this step<")
        self.answer("relatives", action="add-relative")
        self.answer(
            "relatives", action="add-relative",
            **{"relatives-0-relationship": "dam", "relatives-0-ref": f"h:{self.juniper.pk}"},
        )
        page = self.client.get(step("relatives"))
        self.assertContains(page, ">Next<")
        second = page.content.decode().split('id="id_relatives-1-relationship"')[1].split("</select>")[0]
        self.assertNotIn('value="dam"', second)
        self.assertIn('value="sire"', second)
        # A crafted post still meets the server's rule and its message.
        response = self.fails(
            "relatives",
            **{"relatives-0-relationship": "dam", "relatives-0-ref": f"h:{self.juniper.pk}",
               "relatives-1-relationship": "dam", "relatives-1-new_name": "Ridgeview Thistle"},
        )
        self.assertContains(
            response,
            "A rabbit can have only one dam, and Relative 1 is already listed as the dam. Choose a different relationship here.",
        )

    def test_the_dam_must_be_a_doe(self):
        self.walk_to_breed("purebred")
        self.choose_breed()
        self.answer("relatives", action="add-relative")
        response = self.fails(
            "relatives", **{"relatives-0-relationship": "dam", "relatives-0-ref": f"h:{self.pepper.pk}"},
        )
        self.assertContains(response, "The dam has to be a doe. Pepper is a buck, so pick a doe here.")

    def test_full_entry_saves_and_clears_the_draft(self):
        self.walk_to_breed("purebred")
        self.choose_breed()
        self.answer("relatives", action="add-relative")
        self.answer(
            "relatives",
            **{"relatives-0-relationship": "sire", "relatives-0-new_name": "Oak Hollow Major",
               "relatives-0-new_details": "Tag OH-4"},
        )
        review = self.client.get(step("review"))
        self.assertContains(review, "Please check Hazel&#x27;s details")
        self.assertContains(review, "Sire (father): Oak Hollow Major (Tag OH-4)")
        self.assertContains(review, ">Save Hazel<")
        response = self.answer("review")
        rabbit = Rabbit.objects.get(name="Hazel")
        self.assertRedirects(response, reverse("rabbit_flow_done", args=[rabbit.pk]))
        done = self.client.get(response["Location"])
        self.assertContains(done, "Hazel has been added to your herd.")
        self.assertContains(done, "Breed: Holland Lop.")
        self.assertContains(done, "View the herd")
        self.assertNotIn(flow.SESSION_KEY, self.client.session)
        detail = self.client.get(reverse("rabbit_detail", args=[rabbit.pk]))
        self.assertContains(detail, "Sire (father): Oak Hollow Major (Tag OH-4)")

    def test_save_rechecks_everything_and_returns_to_the_problem(self):
        self.walk_to_breed("purebred")
        self.choose_breed()
        self.answer("relatives", action="add-relative")
        self.answer(
            "relatives", **{"relatives-0-relationship": "dam", "relatives-0-ref": f"h:{self.juniper.pk}"},
        )
        # Juniper changes sex after the card was accepted.
        Rabbit.objects.filter(pk=self.juniper.pk).update(sex="buck")
        response = self.client.get(step("review"))
        self.assertRedirects(response, step("relatives") + "?check=1", fetch_redirect_response=False)
        self.assertFalse(Rabbit.objects.filter(name="Hazel").exists())

    def test_autosave_stores_typing_and_returns_no_content(self):
        response = self.client.post(step("name"), {"name": "Haz", "action": "save"}, HTTP_X_AUTOSAVE="1")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.draft()["name"], "Haz")

    def test_start_over_clears_the_draft(self):
        self.answer("name", name="Hazel")
        response = self.client.post(reverse("rabbit_flow_restart"))
        self.assertRedirects(response, step("name"))
        self.assertEqual(self.draft()["name"], "")
        self.assertEqual(self.client.get(reverse("rabbit_flow_restart")).status_code, 405)

    def test_another_keepers_rabbit_cannot_be_opened_or_linked(self):
        other = get_user_model().objects.create_user(email="other@example.com", password="pw-for-tests-only")
        theirs = Rabbit.objects.create(
            owner=other, name="Theirs", sex="doe", breed="Rex", color="Red", birth_date=datetime.date(2023, 1, 1),
        )
        self.assertEqual(self.client.get(reverse("rabbit_flow_done", args=[theirs.pk])).status_code, 404)
        self.walk_to_breed("purebred")
        self.choose_breed()
        self.answer("relatives", action="add-relative")
        page = self.client.get(step("relatives"))
        self.assertNotContains(page, "Theirs")
        response = self.fails(
            "relatives", **{"relatives-0-relationship": "dam", "relatives-0-ref": f"h:{theirs.pk}"},
        )
        self.assertContains(response, "That rabbit is no longer in your list. Please choose again.")
