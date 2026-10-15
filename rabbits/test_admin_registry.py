"""Every model is in the admin, or deliberately left out, and every admin page loads."""

from django.apps import apps
from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

# Django internals with no use in the herd admin.
EXEMPT = {"auth.permission", "contenttypes.contenttype", "sessions.session"}
READ_ONLY = {"rabbits.historyentry", "rabbits.syncop", "admin.logentry"}


class AdminRegistryTests(TestCase):
    def test_every_model_registered_or_exempt(self):
        missing = [
            m._meta.label_lower for m in apps.get_models()
            if m._meta.label_lower not in EXEMPT and not admin.site.is_registered(m)
        ]
        self.assertEqual(missing, [])

    def test_admin_pages_load_and_system_tables_read_only(self):
        user = User.objects.create_superuser(email="root@example.com", password="pw-for-tests-1")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        for model, model_admin in admin.site._registry.items():
            label = model._meta.label_lower
            info = (model._meta.app_label, model._meta.model_name)
            with self.subTest(model=label):
                self.assertEqual(self.client.get(reverse("admin:%s_%s_changelist" % info)).status_code, 200)
                if label in READ_ONLY:
                    request = self.client.get("/").wsgi_request
                    request.user = user
                    self.assertFalse(model_admin.has_add_permission(request))
                    self.assertFalse(model_admin.has_change_permission(request))
                    self.assertFalse(model_admin.has_delete_permission(request))
                elif model_admin.has_add_permission(type("R", (), {"user": user})()):
                    self.assertEqual(self.client.get(reverse("admin:%s_%s_add" % info)).status_code, 200)

    def test_rabbit_delete_still_blocked(self):
        from rabbits.models import Rabbit
        self.assertFalse(admin.site._registry[Rabbit].has_delete_permission(None))
