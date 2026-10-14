import os
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from . import pwa
from .checks import css_problems


class BuiltCssCheckTests(SimpleTestCase):
    def tree(self, css):
        root = Path(tempfile.mkdtemp())
        (root / "assets").mkdir()
        (root / "static" / "css").mkdir(parents=True)
        (root / "assets" / "input.css").write_text("x")
        built = root / "static" / "css" / "app.css"
        built.write_text(css)
        os.utime(root / "assets" / "input.css", (1, 1))
        return root, built

    def test_stale_build_is_reported(self):
        root, _ = self.tree(".flex{display:flex}")
        problems = css_problems(root)
        self.assertIn("the built CSS has no --surface", problems)
        self.assertIn("the built CSS has no warm-b theme", problems)

    def test_source_newer_than_build_is_reported(self):
        from accounts.models import User
        css = "--surface .sr-only select:not([multiple]) [data-swipe] " + " ".join(f"data-theme={k}]" for k, _ in User.THEMES)
        root, built = self.tree(css)
        self.assertEqual(css_problems(root), [])
        os.utime(built, (1, 1))
        os.utime(root / "assets" / "input.css", (100, 100))
        self.assertEqual(css_problems(root), ["assets/*.css changed after the last build"])

    def test_missing_build_is_reported(self):
        root = Path(tempfile.mkdtemp())
        self.assertIn("Run npm run build", css_problems(root)[0])

    def test_current_build_passes_when_built(self):
        if not (Path(settings.BASE_DIR) / "static" / "css" / "app.css").exists():
            self.skipTest("CSS not built here")
        self.assertEqual(css_problems(), [])


class ServiceWorkerVersionTests(TestCase):
    def test_version_changes_when_css_contents_change(self):
        first = self.client.get(reverse("pwa_service_worker")).content
        with mock.patch.object(pwa, "shell_fingerprint", return_value="rebuilt"):
            second = self.client.get(reverse("pwa_service_worker")).content
        version = lambda body: next(line for line in body.split(b"\n") if line.startswith(b"const VERSION"))
        self.assertNotEqual(version(first), version(second))
