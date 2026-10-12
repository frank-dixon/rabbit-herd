"""The color card offers the breed's recognized colors."""

from django.test import TestCase
from django.urls import reverse

from . import flow, flow_forms
from .models import Rabbit
from .test_flow_rules import FlowTestMixin, breed_id

OTHER = flow_forms.OTHER_COLOR
SINGLE_NOTE = (
    "This is the only recognized color for the Creme d&#x27;Argent. "
    "If yours looks different, choose Another color."
)


def step(slug):
    return reverse("rabbit_flow_step", args=[slug])


class ColorRuleTests(FlowTestMixin, TestCase):
    def purebred(self, name, **changes):
        return self.draft(purebred=breed_id(name), **{"color": "", "color_choice": "", **changes})

    def color(self, draft):
        form = flow.bound_form("color", draft, self.user)
        self.assertTrue(form.is_valid(), form.errors)
        return form.cleaned_data["color"]

    def test_a_single_color_breed_has_its_color_chosen_already(self):
        self.assertEqual(self.color(self.purebred("Creme d'Argent")), "Creme")
        self.assertEqual(self.color(self.purebred("Florida White")), "White")

    def test_a_listed_color_is_saved_by_name(self):
        self.assertEqual(self.color(self.purebred("New Zealand", color_choice="Red")), "Red")
        # Text left in the Another color box does not override a listed choice.
        self.assertEqual(self.color(self.purebred("New Zealand", color_choice="Red", color="Broken red")), "Red")

    def test_a_breed_with_several_colors_needs_a_choice(self):
        self.assertEqual(
            self.errors("color", self.purebred("New Zealand")),
            {"color_choice": [
                "Each rabbit needs a coat color. Please choose one of the New Zealand colors, "
                "or choose Another color and describe it."
            ]},
        )

    def test_a_color_off_the_list_is_refused(self):
        self.assertEqual(
            self.errors("color", self.purebred("New Zealand", color_choice="Lilac")),
            {"color_choice": [
                "That color isn't one of the recognized New Zealand colors. "
                "Please choose a color from the list, or choose Another color and describe it."
            ]},
        )

    def test_another_color_needs_a_description(self):
        self.assertEqual(
            self.errors("color", self.purebred("Creme d'Argent", color_choice=OTHER)),
            {"color": ["Another color needs a short description. Please describe the coat, for example broken black."]},
        )
        self.assertEqual(self.color(self.purebred("Creme d'Argent", color_choice=OTHER, color="Broken orange")), "Broken orange")
        self.assertEqual(
            self.errors("color", self.purebred("Creme d'Argent", color_choice=OTHER, color="x" * 81)),
            {"color": ["A color can be up to 80 characters. Please shorten it."]},
        )

    def test_typing_a_listed_color_counts_as_that_color(self):
        self.assertEqual(self.color(self.purebred("New Zealand", color_choice=OTHER, color=" black ")), "Black")

    def test_older_free_text_still_works(self):
        self.assertEqual(self.color(self.purebred("New Zealand", color="blue")), "Blue")
        self.assertEqual(self.color(self.purebred("New Zealand", color="Fawn")), "Fawn")

    def test_crossbreds_and_any_color_breeds_describe_the_color(self):
        self.assertEqual(self.color(self.draft(purebred=breed_id("Holland Lop"), color="Broken tort")), "Broken tort")
        crossbred = self.draft(breed_type="crossbred", purebred="", color="")
        self.assertEqual(
            self.errors("color", crossbred),
            {"color": ["A coat color helps tell rabbits apart, so it's required. Please describe the color."]},
        )


class ColorCardViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(email="keeper@example.com", password="pw-for-tests-only")
        self.client.force_login(user)

    def answer(self, slug, **fields):
        return self.client.post(step(slug), {"action": "next", **fields})

    def to_color(self, breed=None, crossbred=False):
        self.answer("name", name="Hazel")
        self.answer("sex", sex="doe")
        self.answer("birth-date", birth_date="2024-05-01")
        self.answer("status", status="growing")
        if crossbred:
            self.answer("breed-type", breed_type="crossbred")
            response = self.answer("breed", **{
                "cross-0-breed": breed_id("Rex"), "cross-0-percent": "50",
                "cross-1-breed": breed_id("Dutch"), "cross-1-percent": "50",
            })
        else:
            self.answer("breed-type", breed_type="purebred")
            response = self.answer("breed", purebred=breed_id(breed))
        self.assertRedirects(response, step("color"))
        return self.client.get(step("color"))

    def save(self):
        self.answer("relatives")
        response = self.client.post(step("review"), {"action": "next"})
        self.assertEqual(response.status_code, 302)
        return Rabbit.objects.get(name="Hazel")

    def test_single_color_breed_shows_one_chosen_tile_and_the_note(self):
        page = self.to_color("Creme d'Argent")
        self.assertContains(page, SINGLE_NOTE)
        self.assertContains(page, 'name="color_choice" value="Creme" checked')
        self.assertContains(page, f'name="color_choice" value="{OTHER}"')
        self.assertContains(page, "Another color")
        self.assertContains(page, "grid-cols-1")
        self.assertRedirects(self.answer("color", color_choice="Creme"), step("relatives"))
        self.answer("relatives")
        review = self.client.get(step("review"))
        self.assertContains(review, "Creme")
        self.assertEqual(self.save().color, "Creme")

    def test_short_lists_are_tiles(self):
        page = self.to_color("New Zealand")
        self.assertContains(page, "These are the recognized colors for the New Zealand.")
        self.assertEqual(page.content.decode().count('type="radio" id="id_color_choice_'), 6)
        self.assertNotContains(page, " checked")

    def test_long_lists_are_a_select_with_another_color(self):
        page = self.to_color("Dutch")
        body = page.content.decode()
        self.assertIn('<select', body)
        self.assertIn('name="color_choice"', body)
        self.assertIn(f'<option value="{OTHER}"', body)
        self.assertIn('<option value="Steel gray"', body)
        self.answer("color", color_choice=OTHER, color="Broken black")
        self.assertEqual(self.save().color, "Broken black")

    def test_missing_choice_points_at_the_first_tile(self):
        self.to_color("New Zealand")
        response = self.answer("color")
        page = self.client.get(response["Location"])
        self.assertContains(page, 'href="#id_color_choice_0"')
        self.assertContains(page, "Please choose one of the New Zealand colors")

    def test_crossbreds_and_any_color_breeds_get_a_text_box(self):
        page = self.to_color(crossbred=True)
        self.assertContains(page, 'name="color" type="text"')
        self.assertNotContains(page, 'name="color_choice"')
        self.client.post(reverse("rabbit_flow_restart"))
        page = self.to_color("Holland Lop")
        self.assertContains(page, "The Holland Lop comes in many recognized colors")
        self.assertNotContains(page, 'name="color_choice"')


class BreedChangeTests(ColorCardViewTests):
    """After Back and a new breed, the color card keeps up."""

    def change_breed(self, name):
        self.client.post(step("color"), {"action": "back"})
        response = self.answer("breed", purebred=breed_id(name))
        self.assertRedirects(response, step("color"), fetch_redirect_response=False)
        return self.client.get(step("color"))

    def draft(self):
        return flow.load_draft(self.client.session)

    def test_an_unrecognized_color_is_cleared_with_a_note(self):
        self.to_color("New Zealand")
        self.answer("color", color_choice="Blue")
        page = self.change_breed("Creme d'Argent")
        self.assertContains(
            page,
            "Blue isn&#x27;t a recognized color for the Creme d&#x27;Argent, so it has been cleared. "
            "Please check the color below before you go on.",
        )
        self.assertContains(page, 'name="color_choice" value="Creme" checked')
        # The note shows once; a refresh is calm.
        self.assertNotContains(self.client.get(step("color")), 'id="color-cleared"')
        self.answer("color", color_choice="Creme")
        self.assertEqual(self.save().color, "Creme")

    def test_a_cleared_choice_on_a_list_must_be_chosen_again(self):
        self.to_color("New Zealand")
        self.answer("color", color_choice="Red")
        page = self.change_breed("Dutch")
        self.assertContains(page, "Red isn&#x27;t a recognized color for the Dutch")
        self.assertNotContains(page, " selected>")
        response = self.answer("color")
        self.assertContains(self.client.get(response["Location"]), "Please choose one of the Dutch colors")

    def test_a_color_the_new_breed_recognizes_stays(self):
        self.to_color("New Zealand")
        self.answer("color", color_choice="Blue")
        page = self.change_breed("Dutch")
        self.assertNotContains(page, 'id="color-cleared"')
        self.assertContains(page, '<option value="Blue" selected>')

    def test_another_color_text_is_kept(self):
        self.to_color("New Zealand")
        self.answer("color", color_choice=OTHER, color="Broken red")
        page = self.change_breed("Creme d'Argent")
        self.assertNotContains(page, 'id="color-cleared"')
        self.assertContains(page, f'name="color_choice" value="{OTHER}" checked')
        self.assertContains(page, 'value="Broken red"')
        self.answer("color", color_choice=OTHER, color="Broken red")
        self.assertEqual(self.save().color, "Broken red")

    def test_leftover_text_is_kept_but_not_chosen(self):
        self.to_color("New Zealand")
        self.answer("color", color_choice="Blue", color="Broken red")
        page = self.change_breed("Creme d'Argent")
        self.assertContains(page, 'name="color_choice" value="Creme" checked')
        self.assertNotContains(page, f'value="{OTHER}" checked')
        self.assertContains(page, 'value="Broken red"')

    def test_a_listed_color_carries_into_free_text(self):
        self.to_color("New Zealand")
        self.answer("color", color_choice="Blue")
        page = self.change_breed("Holland Lop")
        self.assertNotContains(page, 'id="color-cleared"')
        self.assertContains(page, 'name="color" type="text" value="Blue"')
        self.assertEqual(self.draft()["color_choice"], "")

    def test_jumping_ahead_after_a_breed_change_lands_on_the_color_card(self):
        self.to_color("New Zealand")
        self.answer("color", color_choice="Red")
        self.answer("relatives")
        self.client.post(step("review"), {"action": "back"})
        self.client.post(step("relatives"), {"action": "back"})
        self.change_breed("Dutch")
        response = self.client.get(step("review"))
        self.assertRedirects(response, step("color") + "?check=1", fetch_redirect_response=False)


class ReconcileRuleTests(FlowTestMixin, TestCase):
    def test_reconcile(self):
        nz, creme, lop = breed_id("New Zealand"), breed_id("Creme d'Argent"), breed_id("Holland Lop")
        draft = self.draft(purebred=creme, color_choice="Blue", color="")
        self.assertIn("Blue isn't a recognized color for the Creme d'Argent", flow.reconcile_color(draft))
        self.assertEqual(draft["color_choice"], flow_forms.NO_COLOR)
        self.assertEqual(flow.draft_color(draft), "Creme")
        self.assertEqual(flow.reconcile_color(draft), "", "a second look changes nothing")
        draft = self.draft(purebred=nz, color_choice=OTHER, color="Broken red")
        self.assertEqual(flow.reconcile_color(draft), "")
        self.assertEqual((draft["color_choice"], draft["color"]), (OTHER, "Broken red"))
        draft = self.draft(purebred=lop, color_choice="Blue", color="")
        self.assertEqual(flow.reconcile_color(draft), "")
        self.assertEqual((draft["color_choice"], draft["color"]), ("", "Blue"))


class OffStandardMarkTests(ColorCardViewTests):
    """Off-standard colors are marked on the review and detail pages."""

    NOTE = "(not a recognized color for this breed)"

    def finish(self):
        self.answer("relatives")
        review = self.client.get(step("review"))
        return review, self.save()

    def test_another_color_is_marked(self):
        self.to_color("Creme d'Argent")
        self.answer("color", color_choice=OTHER, color="Broken orange")
        review, rabbit = self.finish()
        self.assertContains(review, f"Broken orange {self.NOTE}")
        self.assertIs(rabbit.color_is_standard, False)
        self.assertEqual(rabbit.color, "Broken orange")
        detail = self.client.get(reverse("rabbit_detail", args=[rabbit.pk]))
        self.assertContains(detail, f"Broken orange {self.NOTE}")

    def test_a_recognized_color_is_not_marked(self):
        self.to_color("Creme d'Argent")
        self.answer("color", color_choice="Creme")
        review, rabbit = self.finish()
        self.assertNotContains(review, self.NOTE)
        self.assertIs(rabbit.color_is_standard, True)
        self.assertNotContains(self.client.get(reverse("rabbit_detail", args=[rabbit.pk])), self.NOTE)

    def test_typing_a_recognized_color_is_not_marked(self):
        self.to_color("New Zealand")
        self.answer("color", color_choice=OTHER, color="red")
        review, rabbit = self.finish()
        self.assertNotContains(review, self.NOTE)
        self.assertEqual((rabbit.color, rabbit.color_is_standard), ("Red", True))

    def test_free_text_colors_are_not_judged(self):
        self.to_color("Holland Lop")
        self.answer("color", color="Broken tort")
        review, rabbit = self.finish()
        self.assertNotContains(review, self.NOTE)
        self.assertIsNone(rabbit.color_is_standard)

    def test_editing_to_a_listed_color_clears_the_mark(self):
        self.to_color("Creme d'Argent")
        self.answer("color", color_choice=OTHER, color="Broken orange")
        _, rabbit = self.finish()
        self.client.post(reverse("rabbit_edit_step", args=[rabbit.pk, "color"]), {
            "color_choice": "Creme", "color": "", "action": "next",
        })
        self.client.post(reverse("rabbit_edit", args=[rabbit.pk]), {"action": "save"})
        rabbit.refresh_from_db()
        self.assertEqual(rabbit.color, "Creme")
        self.assertIs(rabbit.color_is_standard, True)
        self.assertNotContains(self.client.get(reverse("rabbit_detail", args=[rabbit.pk])), self.NOTE)

    def test_saving_other_fields_keeps_the_mark(self):
        self.to_color("Creme d'Argent")
        self.answer("color", color_choice=OTHER, color="Broken orange")
        _, rabbit = self.finish()
        self.client.post(reverse("rabbit_edit_step", args=[rabbit.pk, "status"]), {
            "status": "breeding", "action": "next",
        })
        self.client.post(reverse("rabbit_edit", args=[rabbit.pk]), {"action": "save"})
        rabbit.refresh_from_db()
        self.assertEqual(rabbit.status, "breeding")
        self.assertIs(rabbit.color_is_standard, False)
