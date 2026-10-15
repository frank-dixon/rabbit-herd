from django.apps import AppConfig


class RabbitsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rabbits"

    def ready(self):
        from . import history

        history.connect()

        from . import derived

        derived.connect()
