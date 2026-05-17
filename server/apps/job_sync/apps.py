from typing import override

from django.apps import AppConfig


class JobSyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'server.apps.job_sync'
    verbose_name = 'Job Sync'

    @override
    def ready(self) -> None:
        import server.apps.job_sync.parsers.habr_career  # noqa: F401
        import server.apps.job_sync.parsers.praca_by  # noqa: F401
