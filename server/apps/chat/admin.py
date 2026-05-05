from django.contrib import admin

from server.apps.chat.models import (
    ChatMessage,
    ChatNotification,
    ChatRoom,
)

admin.site.register(ChatRoom)
admin.site.register(ChatMessage)
admin.site.register(ChatNotification)