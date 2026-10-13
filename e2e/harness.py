"""End-to-end harness: a live server plus a real Chromium, driven twice per
case (JavaScript on and off). Each case opens a page, fills a form through
the UI, submits it, reloads, and checks the database.

Run: python manage.py test e2e   (skips cleanly if Playwright's browser is missing)."""

import datetime
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


@tag("e2e")
class BrowserCase(StaticLiveServerTestCase):
    viewport = {"width": 1280, "height": 900}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if sync_playwright is None:
            raise cls.skipException("Playwright is not installed")
        cls._pw = sync_playwright().start()
        try:
            cls.browser = cls._pw.chromium.launch()
        except Exception as error:  # pragma: no cover
            cls._pw.stop()
            raise cls.skipException(f"No browser: {error}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._pw.stop()
        super().tearDownClass()

    def setUp(self):
        self.user = get_user_model().objects.create_user(email="e2e@example.com", password="pw-e2e-only-123")

    def page(self, js=True, width=None):
        """A signed-in page. The session cookie comes from Django's own login."""
        self.client.force_login(self.user)
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        context = self.browser.new_context(
            java_script_enabled=js, service_workers="block", reduced_motion="reduce",
            viewport={"width": width or self.viewport["width"], "height": self.viewport["height"]},
        )
        context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": cookie, "url": self.live_server_url}])
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.js_errors = errors
        self.addCleanup(context.close)
        return page

    def go(self, page, path):
        page.goto(self.live_server_url + path)
        page.wait_for_load_state("load")

    def fill(self, form, fields):
        """Fill named fields: selects by value (or "__first__"), checkboxes and
        radios by value, everything else by typing."""
        for name, value in fields.items():
            field = form.locator(f'[name="{name}"]')
            if field.count() > 1:
                kind = field.first.get_attribute("type")
                if kind in ("radio", "checkbox"):
                    form.locator(f'[name="{name}"][value="{value}"]').check(force=True)
                    continue
                field = field.last if not field.first.is_visible() else field.first
            else:
                field = field.first
            tag_name = field.evaluate("el => el.tagName")
            kind = field.get_attribute("type")
            if tag_name == "SELECT":
                if value == "__first__":
                    value = field.evaluate("el => [...el.options].find(o => o.value)?.value || ''")
                field.select_option(value)
            elif kind in ("checkbox", "radio"):
                field.check(force=True) if value else field.uncheck(force=True)
            elif kind == "file":
                field.set_input_files(value)
            else:
                field.fill(str(value))

    def submit(self, page, form, button=None):
        target = form.locator(button) if button else form.locator('button[type="submit"], input[type="submit"]').last
        with page.expect_navigation(wait_until="load", timeout=15000):
            target.first.scroll_into_view_if_needed(timeout=5000)
            target.first.click()

    def run_form(self, js, path, form_selector, fields, button=None, open_first=None):
        page = self.page(js=js)
        self.go(page, path)
        if open_first:
            page.locator(open_first).first.click()
        form = page.locator(form_selector).first
        # Forms often live in folded <details>; open every ancestor fold.
        form.evaluate("f => { for (let d = f.closest('details'); d; d = d.parentElement && d.parentElement.closest('details')) d.open = true; }")
        self.fill(form, fields)
        self.submit(page, form, button)
        page.reload()
        self.assertEqual(page.js_errors, [], f"JS errors on {path}")
        return page


def both(test):
    """Run a test body with JS on, then off."""
    def run(self):
        for js in (True, False):
            with self.subTest(js=js):
                test(self, js)
    run.__name__ = test.__name__
    return run


TODAY = datetime.date.today
