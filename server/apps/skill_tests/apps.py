from typing import override

from django.apps import AppConfig


class SkillTestsConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'server.apps.skill_tests'
    verbose_name = 'Skill Tests'

    @override
    def ready(self) -> None:
        from server.apps.skill_tests import signals  # noqa: F401
