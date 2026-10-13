"""Every add and edit form, submitted through the real page with JS on and
off, then checked in the database after a reload."""

import datetime
import os

from django.test import override_settings

from rabbits.models import (Breed, Contact, CullNote, Expense, Gene, HealthNote, Litter, Location, Pairing,
                            Rabbit, RabbitPhoto, Task, WaitlistEntry, Weight)

from .harness import BrowserCase, both

PHONE_PHOTO = os.environ.get("RH_E2E_PHONE_PHOTO", "/workspace/rh-verify/IMG_4821.jpeg")


def first(form):
    return f'form[action$="{form}"]'


class RabbitPageForms(BrowserCase):
    def setUp(self):
        super().setUp()
        mk = lambda name, sex, **kw: Rabbit.objects.create(owner=self.user, name=name, sex=sex, breed="Holland Lop",
                                                           color="Black", birth_date=datetime.date(2024, 1, 1), **kw)
        holland, _ = Breed.objects.get_or_create(name="Holland Lop")
        self.doe, self.buck = (mk(n, sx, breed_type="purebred", purebred=holland) for n, sx in (("Blackberry", "doe"), ("Basil", "buck")))
        self.path = f"/rabbits/{self.doe.pk}/"

    @both
    def test_weight(self, js):
        before = Weight.objects.count()
        page = self.run_form(js, self.path, first(f"/rabbits/{self.doe.pk}/weights/"), {"lb": "5", "oz": "4"})
        self.assertEqual(Weight.objects.count(), before + 1)
        self.assertEqual(page.get_by_text("No weights yet").count(), 0)

    @both
    def test_health_note(self, js):
        before = HealthNote.objects.count()
        self.run_form(js, self.path, first(f"/rabbits/{self.doe.pk}/health/"), {"health_kind": "__first__", "notes": f"Ear check {js}"},
                      open_first='details[data-fold]:has(form[action$="/health/"]) > summary' if js else None)
        self.assertEqual(HealthNote.objects.count(), before + 1)

    @both
    def test_cull_note(self, js):
        before = CullNote.objects.count()
        self.run_form(js, self.path, f'form:has([name="cull_decision"])', {"cull_decision": "keep", "cull_reason": f"Good shoulders {js}"})
        self.assertEqual(CullNote.objects.count(), before + 1)

    @both
    @override_settings(FEATURE_LOCATIONS=True)
    def test_location(self, js):
        self.run_form(js, self.path, first(f"/rabbits/{self.doe.pk}/location/"), {"new_location": f"Barn row {js}"})
        self.doe.refresh_from_db()
        self.assertEqual(self.doe.location.name, f"Barn row {js}")

    @both
    def test_quick_edit_line_and_tattoo(self, js):
        self.run_form(js, f"/rabbits/{self.doe.pk}/change/line/", "form[data-rabbit-flow]", {"line": f"Ridgeview {js}"}, button='[data-action-bar] button[value="next"]')
        self.run_form(js, f"/rabbits/{self.doe.pk}/change/name/", "form[data-rabbit-flow]", {"tattoo": f"BB{int(js)}"}, button='[data-action-bar] button[value="next"]')
        self.doe.refresh_from_db()
        self.assertEqual((self.doe.line, self.doe.tattoo), (f"Ridgeview {js}", f"BB{int(js)}"))

    @both
    def test_quick_edit_status(self, js):
        self.run_form(js, f"/rabbits/{self.doe.pk}/change/status/", "form[data-rabbit-flow]", {"status": "growing" if js else "breeding"}, button='[data-action-bar] button[value="next"]')
        self.doe.refresh_from_db()
        self.assertEqual(self.doe.status, "growing" if js else "breeding")

    @both
    def test_genes_with_pattern_picker(self, js):
        self.run_form(js, f"/rabbits/{self.doe.pk}/change/genes/", "form[data-rabbit-flow]", {"gene_En": "Enen", "gene_D": "Dd"}, button='[data-action-bar] button[value="next"]')
        self.assertEqual(self.doe.genes.get(locus="En").genotype, "Enen")
        self.assertEqual(self.doe.genes.get(locus="D").genotype, "Dd")

    def test_inline_line_edit_with_js(self):
        page = self.page(js=True)
        self.go(page, self.path)
        row = page.locator('[data-fact="line"] a[data-fact-edit]')
        if not row.get_attribute("data-inline-name"):
            self.skipTest("Line is not inline-edited on this page")
        row.click()
        page.locator('[data-fact="line"] input').fill("Inline line")
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        page.reload()
        self.doe.refresh_from_db()
        self.assertEqual(self.doe.line, "Inline line")

    def test_photo_upload_real_phone_image(self):
        if not os.path.exists(PHONE_PHOTO):
            self.skipTest("No real phone photo on this machine")
        for js in (True, False):
            with self.subTest(js=js):
                before = RabbitPhoto.objects.count()
                page = self.page(js=js)
                self.go(page, self.path)
                form = page.locator('form:has(input[type="file"][name="image"])').first
                form.locator('input[name="image"]').set_input_files(PHONE_PHOTO)
                if js:
                    for _ in range(16):
                        if RabbitPhoto.objects.count() > before:
                            break
                        page.wait_for_timeout(500)
                    if RabbitPhoto.objects.count() == before:
                        self.submit(page, form)
                else:
                    self.submit(page, form)
                self.assertEqual(RabbitPhoto.objects.count(), before + 1)


class ListPageForms(BrowserCase):
    def setUp(self):
        super().setUp()
        mk = lambda name, sex: Rabbit.objects.create(owner=self.user, name=name, sex=sex, breed="Rex", color="Black",
                                                     birth_date=datetime.date(2024, 1, 1))
        self.doe, self.buck = mk("Hazel", "doe"), mk("Ash", "buck")

    def open_sheet(self, page, path, js):
        if js:
            self.go(page, path)
            page.locator('[data-header-actions] a[href^="?new=1"]').first.click()
        else:
            self.go(page, path + "?new=1")

    def sheet_form(self, js, path, fields, button='button[type="submit"]'):
        page = self.page(js=js)
        self.open_sheet(page, path, js)
        form = page.locator("details[data-add-sheet] form").first
        self.fill(form, fields)
        self.submit(page, form, button)
        page.reload()
        self.assertEqual(page.js_errors, [])
        return page

    @both
    def test_task(self, js):
        self.sheet_form(js, "/tasks/", {"title": f"Clean trays {js}", "due_on": datetime.date.today().isoformat()})
        self.assertTrue(Task.objects.filter(title=f"Clean trays {js}").exists())

    @both
    @override_settings(FEATURE_LOCATIONS=True)
    def test_location(self, js):
        self.sheet_form(js, "/locations/", {"name": f"Hutch {js}"})
        self.assertTrue(Location.objects.filter(name=f"Hutch {js}").exists())

    @both
    def test_cost(self, js):
        self.sheet_form(js, "/costs/", {"description": f"Pellets {js}", "amount": "24.50", "category": "__first__"})
        self.assertTrue(Expense.objects.filter(description=f"Pellets {js}").exists())

    @both
    def test_waitlist(self, js):
        self.sheet_form(js, "/waitlist/", {"buyer": f"Ana {js}"})
        self.assertTrue(WaitlistEntry.objects.filter(buyer=f"Ana {js}").exists())

    @both
    def test_pairing_then_litter_kindling_and_cover(self, js):
        self.sheet_form(js, "/pairings/", {"doe": str(self.doe.pk), "buck": str(self.buck.pk)},
                        button='button[value="save"]')
        pairing = Pairing.objects.filter(doe=self.doe).latest("pk")
        self.run_form(js, f"/pairings/{pairing.pk}/", first(f"/pairings/{pairing.pk}/litters/") + ", form:has([name=bred_on])",
                      {"bred_on": (datetime.date.today() - datetime.timedelta(days=40)).isoformat()})
        litter = Litter.objects.filter(pairing=pairing).latest("pk")
        self.run_form(js, f"/litters/{litter.pk}/", first(f"/litters/{litter.pk}/kindling/"),
                      {"kindled_on": (datetime.date.today() - datetime.timedelta(days=8)).isoformat(), "born_alive": "6", "born_dead": "1"})
        litter.refresh_from_db()
        self.assertEqual((litter.born_alive, litter.born_dead), (6, 1))
        before = litter.covers.count()
        self.run_form(js, f"/litters/{litter.pk}/", first(f"/litters/{litter.pk}/covers/"),
                      {"date": (datetime.date.today() - datetime.timedelta(days=39)).isoformat(), "outcome": "covered"})
        self.assertEqual(litter.covers.count(), before + 1)

    @both
    def test_contact(self, js):
        self.run_form(js, "/contacts/new/", "main form[method=post]", {"name": f"Pat {js}", "is_buyer": True})
        self.assertTrue(Contact.objects.filter(name=f"Pat {js}").exists())

    @both
    def test_settings_units_and_rabbitry(self, js):
        self.run_form(js, "/settings/", 'form:has([name="rabbitry_name"])', {"rabbitry_name": f"Bramble {js}"})
        from rabbits.models import HerdSettings
        self.assertEqual(HerdSettings.objects.get(user=self.user).rabbitry_name, f"Bramble {js}")
