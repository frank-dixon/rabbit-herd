from django import forms
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.models import User


class SampleRecordForm(forms.Form):
    name = forms.CharField(help_text="The rabbit's name.")
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    notes = forms.CharField(required=False, widget=forms.Textarea)
    status = forms.ChoiceField(choices=[("doe", "Doe"), ("buck", "Buck")])
    archived = forms.BooleanField(required=False, label="Archived")
    born = forms.DateField(required=False)


class FieldPartialTests(SimpleTestCase):
    def test_each_control_renders_with_label_help_and_errors(self):
        form = SampleRecordForm(data={"email": "nope", "name": ""})
        self.assertFalse(form.is_valid())

        email = render_to_string("components/field.html", {"field": form["email"]})
        name = render_to_string("components/field.html", {"field": form["name"]})
        password = render_to_string("components/field.html", {"field": form["password"]})
        notes = render_to_string("components/field.html", {"field": form["notes"]})
        status = render_to_string("components/field.html", {"field": form["status"]})
        archived = render_to_string("components/field.html", {"field": form["archived"]})
        born = render_to_string("components/field.html", {"field": form["born"]})

        self.assertIn('type="email"', email)
        self.assertIn("valid email", email)
        self.assertIn("border-neutral-800", email)
        self.assertIn("id_name_helptext", name)
        self.assertIn("rabbit", name)
        self.assertIn("This field is required.", name)
        self.assertIn('type="password"', password)
        self.assertIn("<textarea", notes)
        self.assertIn("<select", status)
        self.assertIn("Doe", status)
        self.assertIn('type="checkbox"', archived)
        self.assertIn("Archived", archived)
        self.assertIn('type="date"', born)

    def test_form_partial_includes_fields_submit_and_next(self):
        request = RequestFactory().get("/accounts/login/")
        html = render_to_string(
            "components/form.html",
            {
                "form": SampleRecordForm(),
                "submit_label": "Save record",
                "include_next": True,
                "next": "/next/",
            },
            request=request,
        )

        self.assertIn("Save record", html)
        self.assertIn('type="submit"', html)
        self.assertIn('name="next"', html)
        self.assertIn('value="/next/"', html)
        self.assertIn('type="checkbox"', html)
        self.assertIn("csrfmiddlewaretoken", html)


class ComponentReferenceTests(TestCase):
    def test_anonymous_visitors_get_a_missing_page(self):
        response = self.client.get(reverse("components"))

        self.assertEqual(response.status_code, 404)

    def test_signed_in_non_staff_get_a_missing_page(self):
        user = User.objects.create_user(
            email="frank@example.com",
            password="Rabbit-Herd-Pass-1",
            is_active=True,
            email_confirmed=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("components"))

        self.assertEqual(response.status_code, 404)

    def test_staff_see_every_partial(self):
        user = User.objects.create_user(
            email="frank@example.com",
            password="Rabbit-Herd-Pass-1",
            is_active=True,
            email_confirmed=True,
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("components"))

        self.assertContains(response, "Components")
        self.assertContains(response, "Danger")
        self.assertContains(response, "bg-red-800")
        self.assertContains(response, "disabled")
        self.assertContains(response, 'aria-disabled="true"')
        self.assertContains(response, 'type="email"')
        self.assertContains(response, 'type="password"')
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, 'type="date"')
        self.assertContains(response, "<textarea")
        self.assertContains(response, "<select")
        self.assertContains(response, "valid email")
        self.assertContains(response, "Save record")
        self.assertContains(response, "Clover")
        self.assertContains(response, "Nothing here.")
        self.assertContains(response, "No rows yet.")
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, "{% include")

    @override_settings(DEBUG=True)
    def test_debug_opens_the_page_for_anonymous_visitors(self):
        response = self.client.get(reverse("components"))

        self.assertContains(response, "Components")


class AlertPartialTests(SimpleTestCase):
    def test_error_and_success_alerts(self):
        error = render_to_string(
            "components/alert.html",
            {"text": "That failed.", "tags": "error"},
        )
        success = render_to_string(
            "components/alert.html",
            {"text": "Saved.", "tags": "success"},
        )

        self.assertIn('role="alert"', error)
        self.assertIn("That failed.", error)
        self.assertIn("border-red-800", error)
        self.assertIn('role="status"', success)
        self.assertIn("Saved.", success)


class MessageDisplayTests(TestCase):
    def test_django_message_renders_as_an_alert(self):
        self.client.post(reverse("guest"))
        self.client.get(reverse("password_change"))

        home = self.client.get(reverse("index"))

        self.assertContains(home, "Guest sessions do not have a password.")
        self.assertContains(home, 'role="alert"')


class ListAndTablePartialTests(SimpleTestCase):
    def test_list_renders_items_and_an_empty_state(self):
        filled = render_to_string(
            "components/list.html",
            {"items": ["Clover", "Thistle"]},
        )
        empty = render_to_string(
            "components/list.html",
            {"items": [], "empty": "No rabbits yet."},
        )

        self.assertIn("<ul", filled)
        self.assertIn("Clover", filled)
        self.assertIn("Thistle", filled)
        self.assertIn("No rabbits yet.", empty)
        self.assertNotIn("<li class=\"px-3 py-2\">Clover", empty)

    def test_table_renders_rows_and_an_empty_state(self):
        filled = render_to_string(
            "components/table.html",
            {
                "columns": ["Name", "Sex"],
                "rows": [["Clover", "Doe"]],
            },
        )
        empty = render_to_string(
            "components/table.html",
            {"columns": ["Name", "Sex"], "rows": [], "empty": "No rows yet."},
        )

        self.assertIn("<table", filled)
        self.assertIn("Name", filled)
        self.assertIn("Clover", filled)
        self.assertIn("Doe", filled)
        self.assertIn("No rows yet.", empty)
        self.assertIn('colspan="2"', empty)


class CardPartialTests(SimpleTestCase):
    def test_card_renders_title_and_body(self):
        html = render_to_string(
            "components/card.html",
            {"title": "Clover", "body": "A doe."},
        )

        self.assertIn("<section", html)
        self.assertIn("Clover", html)
        self.assertIn("A doe.", html)
        self.assertIn("<h2", html)


class ButtonPartialTests(SimpleTestCase):
    def test_variants_render_as_buttons_and_links(self):
        primary = render_to_string(
            "components/button.html",
            {"label": "Save", "type": "submit", "variant": "primary"},
        )
        danger = render_to_string(
            "components/button.html",
            {"label": "Remove", "variant": "danger"},
        )
        link = render_to_string(
            "components/button.html",
            {"label": "Back", "href": "/back/", "variant": "secondary", "disabled": True},
        )

        self.assertIn("<button", primary)
        self.assertIn('type="submit"', primary)
        self.assertIn("bg-neutral-800", primary)
        self.assertIn("<button", danger)
        self.assertIn("bg-red-800", danger)
        self.assertIn("<a", link)
        self.assertNotIn("<button", link)
        self.assertIn('href="/back/"', link)
        self.assertIn('aria-disabled="true"', link)
        self.assertIn("opacity-50", link)

    def test_disabled_button_cannot_submit(self):
        html = render_to_string(
            "components/button.html",
            {"label": "Save", "type": "submit", "disabled": True},
        )

        self.assertIn("disabled", html)
        self.assertNotIn("<a", html)


class PageShellTests(TestCase):
    def test_public_and_auth_pages_use_the_shell(self):
        for url in ("/", reverse("login"), reverse("signup")):
            response = self.client.get(url)
            self.assertContains(response, "<header")
            self.assertContains(response, "<main")
            self.assertContains(response, "<footer")
            self.assertContains(response, 'href="/"')

    def test_signed_in_page_uses_the_shell(self):
        user = User.objects.create_user(
            email="frank@example.com",
            password="Rabbit-Herd-Pass-1",
            is_active=True,
            email_confirmed=True,
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertContains(response, "Activity</h1>")
        self.assertContains(response, "<header")
        self.assertContains(response, "<footer")


class CardFlowPartialTests(SimpleTestCase):
    def test_large_button_has_a_big_target_and_a_screen_reader_suffix(self):
        html = render_to_string(
            "components/button.html",
            {"label": "Remove", "sr_suffix": "relative 2", "size": "large", "type": "submit", "name": "action", "value": "remove-relative-1"},
        )
        self.assertIn("min-h-14", html)
        self.assertIn('<span class="sr-only"> relative 2</span>', html)
        self.assertIn('value="remove-relative-1"', html)

    def test_error_summary_counts_and_links_each_problem(self):
        one = render_to_string("components/error_summary.html", {"items": [{"anchor": "id_name", "message": "Add a name."}]})
        self.assertIn("Please check one thing before continuing:", one)
        self.assertIn('href="#id_name"', one)
        self.assertIn('role="alert"', one)
        two = render_to_string(
            "components/error_summary.html",
            {"items": [{"anchor": "a", "message": "One."}, {"anchor": "b", "message": "Two."}]},
        )
        self.assertIn("Please check these 2 things before continuing:", two)
        self.assertEqual(render_to_string("components/error_summary.html", {"items": []}).strip(), "")

    def test_choice_tiles_are_labelled_radios_with_hints(self):
        html = render_to_string(
            "components/choice_tiles.html",
            {
                "name": "sex",
                "legend": "Sex",
                "quiet": True,
                "tiles": [
                    {"value": "doe", "label": "Doe", "hint": "Female", "checked": True},
                    {"value": "buck", "label": "Buck", "hint": "Male", "checked": False},
                ],
                "errors": ["Choose one."],
            },
        )
        self.assertIn('<legend class="sr-only">Sex</legend>', html)
        self.assertIn('for="id_sex_0"', html)
        self.assertIn('value="doe" checked', html)
        self.assertIn("Female", html)
        self.assertIn('aria-describedby="id_sex_error"', html)

    def test_select_marks_the_chosen_option_inside_groups(self):
        html = render_to_string(
            "components/select.html",
            {"name": "purebred", "label": "Breed", "value": "2", "groups": [("ARBA recognized (2)", [("1", "Dutch"), ("2", "Rex")])], "placeholder": "Choose a breed…"},
        )
        self.assertIn('<optgroup label="ARBA recognized (2)">', html)
        self.assertIn('<option value="2" selected>Rex</option>', html)
        self.assertIn("Choose a breed…", html)
