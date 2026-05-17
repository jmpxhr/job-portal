from typing import override

from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'server.apps.chat'
    verbose_name = 'Chat'

    @override
    def ready(self) -> None:
        from server.apps.chat import signals  # noqa: F401
