from django import forms
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
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

        self.assertContains(response, "You're in.")
        self.assertContains(response, "<header")
        self.assertContains(response, "<footer")
