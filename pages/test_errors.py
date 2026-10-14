from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import HttpResponse
from django.template import loader
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import path

from pages import errors
from rabbit_herd.urls import urlpatterns as app_urlpatterns


def boom(request):
    raise RuntimeError("boom")


def forbidden(request):
    raise PermissionDenied


def bad(request):
    raise SuspiciousOperation("bad")


def plain_json_404(request):
    return HttpResponse('{"error": "missing"}', status=404, content_type="application/json")


urlpatterns = [
    path("boom/", boom),
    path("forbidden/", forbidden),
    path("bad/", bad),
    path("api-404/", plain_json_404),
] + app_urlpatterns
handler400 = "pages.errors.bad_request"
handler403 = "pages.errors.permission_denied"
handler404 = "pages.errors.page_not_found"


class DescribeTests(SimpleTestCase):
    def test_missing_litter_names_the_litter_and_goes_back_to_the_list(self):
        self.assertEqual(
            errors.describe(404, "/litters/431/"),
            ("Litter not found", "This litter may have been deleted or moved.", "/litters/"),
        )

    def test_missing_rabbit(self):
        heading, line, back = errors.describe(404, "/rabbits/12/edit/")
        self.assertEqual((heading, line, back), ("Rabbit not found", "This rabbit may have been deleted or moved.", "/rabbits/"))

    def test_unknown_page(self):
        self.assertEqual(errors.describe(404, "/nope/")[0], "Page not found")
        self.assertEqual(errors.describe(404, "/nope/")[2], "/")

    def test_403_keeps_its_heading_on_record_paths(self):
        self.assertEqual(errors.describe(403, "/litters/4/")[0], "You don't have access to this page")


class ErrorPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="keeper@example.com", password="pw-12345678")

    def assert_branded(self, response, status, heading):
        self.assertEqual(response.status_code, status)
        body = response.content.decode()
        self.assertIn(f'data-error-page="{status}"', body)
        self.assertIn(heading, body)
        self.assertIn(">Go to homepage<", body)
        self.assertIn("data-error-back", body)
        self.assertIn("/static/css/app.css", body)

    @override_settings(DEBUG=False)
    def test_missing_litter_404_signed_in(self):
        self.client.force_login(self.user)
        response = self.client.get("/litters/431/")
        self.assert_branded(response, 404, "Litter not found")
        self.assertIn("This litter may have been deleted or moved.", response.content.decode())
        self.assertIn('href="/litters/"', response.content.decode())

    @override_settings(DEBUG=False)
    def test_unknown_url_404(self):
        response = self.client.get("/no-such-page/")
        self.assert_branded(response, 404, "Page not found")

    @override_settings(DEBUG=True)
    def test_debug_still_shows_the_branded_404(self):
        self.client.force_login(self.user)
        response = self.client.get("/litters/431/")
        self.assert_branded(response, 404, "Litter not found")
        self.assertNotIn("Using the URLconf", response.content.decode())

    @override_settings(DEBUG=True)
    def test_debug_query_flag_shows_the_technical_404(self):
        response = self.client.get("/no-such-page/?debug=1")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("data-error-page", response.content.decode())

    @override_settings(DEBUG=True, SHOW_DEBUG_404=True)
    def test_setting_shows_the_technical_404(self):
        response = self.client.get("/no-such-page/")
        self.assertNotIn("data-error-page", response.content.decode())

    @override_settings(DEBUG=True, ROOT_URLCONF="pages.test_errors")
    def test_debug_leaves_non_html_404s_alone(self):
        response = self.client.get("/api-404/")
        self.assertEqual(response.content, b'{"error": "missing"}')

    @override_settings(DEBUG=False, ROOT_URLCONF="pages.test_errors")
    def test_403_and_400(self):
        self.assert_branded(self.client.get("/forbidden/"), 403, "access to this page")
        self.assert_branded(self.client.get("/bad/"), 400, "Something was wrong with that request")

    @override_settings(DEBUG=False)
    def test_csrf_failure_uses_the_branded_403(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post("/tasks/", {"title": "x"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("This form has expired", response.content.decode())


class ServerErrorTests(SimpleTestCase):
    def test_500_renders_with_an_empty_context_and_no_database(self):
        template = loader.get_template("500.html")
        with mock.patch("django.db.backends.utils.CursorWrapper.execute", side_effect=AssertionError("db used")):
            html = template.render({})
        self.assertIn('data-error-page="500"', html)
        self.assertIn("Something went wrong", html)
        self.assertIn('href="/">Go to homepage<', html)
        self.assertIn(">Back<", html)

    def test_500_uses_no_tags_that_need_context_or_settings(self):
        source = open(loader.get_template("500.html").origin.name).read()
        for tag in ("{% url", "{% static", "{% extends", "{% include", "{{ "):
            self.assertNotIn(tag, source)

    @override_settings(DEBUG=False, ROOT_URLCONF="pages.test_errors")
    def test_unhandled_exception_returns_the_500_page(self):
        self.client.raise_request_exception = False
        response = self.client.get("/boom/")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Something went wrong", response.content.decode())
