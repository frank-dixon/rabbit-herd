"""The breed type card: picking Crossbred shows the mix rows on the same
card and the mix saves, with JavaScript on and off. Regression for a rabbit
whose breed was saved as "Unknown"."""

import datetime

from rabbits.models import Breed, Rabbit

from .harness import BrowserCase, both


class BreedTypeCard(BrowserCase):
    def legacy(self, name):
        return Rabbit.objects.create(owner=self.user, name=name, sex="doe", breed="Unknown", breed_type="", status="breeding",
                                            color="Black", birth_date=datetime.date(2024, 1, 1))

    @both
    def test_crossbred_mix_saves_from_the_breed_type_card(self, js):
        rex, dutch = (str(Breed.objects.get_or_create(name=n)[0].pk) for n in ("Rex", "Dutch"))
        self.rabbit = self.legacy(f"Pepper {js}")
        page = self.page(js=js)
        self.go(page, f"/rabbits/{self.rabbit.pk}/edit/breed-type/")
        page.get_by_label("Crossbred").check()
        bar = page.locator("[data-action-bar] button[value=next]")
        if not js:
            with page.expect_navigation():
                bar.click()
        self.assertEqual(page.get_by_text("Each rabbit is either purebred or crossbred").count(), 0, page.url)
        page.locator('[data-breed-section="crossbred"]').wait_for(state="visible")
        page.select_option('[name="cross-0-breed"]', rex)
        page.fill('[name="cross-0-percent"]', "50")
        page.select_option('[name="cross-1-breed"]', dutch)
        page.fill('[name="cross-1-percent"]', "50")
        with page.expect_navigation():
            bar.click()
        self.assertTrue(page.url.endswith(f"/rabbits/{self.rabbit.pk}/edit/"), page.url)
        self.assertIn("Crossbred", page.inner_text("main"))
        self.assertEqual(page.js_errors, [])
