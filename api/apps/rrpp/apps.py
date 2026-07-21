from django.apps import AppConfig


class RrppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.rrpp'
    verbose_name = 'RRPP'

    def ready(self):
        import apps.rrpp.signals  # noqa: F401
