from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pages"

    def ready(self):
        from . import checks  # noqa: F401
        from .middleware import connect_login_signal

        connect_login_signal()
