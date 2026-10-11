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
