"""Welcome guide and samples: add, hide, clear. Real records survive."""

from django.urls import reverse

from e2e.harness import BrowserCase, both
from rabbits.models import Rabbit
from rabbits.samples import add_samples, clear_samples, sample_count


class SampleGuideTests(BrowserCase):
    def setUp(self):
        super().setUp()
        self.real = Rabbit.objects.create(
            owner=self.user, name="Clover", sex=Rabbit.Sex.DOE, breed="Californian",
            color="White", birth_date="2025-01-01", status=Rabbit.Status.BREEDING)

    def _reset(self):
        clear_samples(self.user)
        self.user.show_samples = True
        self.user.guide_step = ""
        self.user.guide_dismissed_at = None
        self.user.save(update_fields=["show_samples", "guide_step", "guide_dismissed_at"])

    @both
    def test_add_hide_and_clear_keeps_real(self, js):
        self._reset()
        page = self.page(js=js)
        self.go(page, reverse("rabbit_list"))
        btn = page.locator("[data-guide=add-samples]")
        if btn.count():
            with page.expect_navigation(wait_until="load", timeout=15000):
                btn.first.click()
        else:
            add_samples(self.user, "rabbits")
        self.assertGreater(sample_count(self.user), 0)
        self.assertTrue(Rabbit.objects.filter(owner=self.user, name="Maple", is_sample=True).exists())
        self.go(page, reverse("rabbit_list"))
        self.assertIn("Sample", page.content())
        self.user.show_samples = False
        self.user.save(update_fields=["show_samples"])
        self.go(page, reverse("rabbit_list"))
        self.assertEqual(page.locator("[data-guide=add-samples]").count(), 0)
        n = sample_count(self.user)
        self.assertEqual(clear_samples(self.user), n)
        self.assertEqual(sample_count(self.user), 0)
        self.assertTrue(Rabbit.objects.filter(owner=self.user, pk=self.real.pk).exists())
        self.assertFalse(page.js_errors)

    @both
    def test_settings_section_renders(self, js):
        self._reset()
        page = self.page(js=js)
        self.go(page, reverse("account"))
        self.assertIn("Welcome guide and samples", page.content())
        self.assertIn("Show samples", page.content())
        self.assertFalse(page.js_errors)
