from typing import override

from django.apps import AppConfig


class JobsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'server.apps.jobs'
    verbose_name = 'Jobs'

    @override
    def ready(self) -> None:
        from server.apps.jobs import signals  # noqa: F401, PLC0415
