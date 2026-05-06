from django.urls import re_path

from server.apps.chat.consumers import ChatConsumer, NotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/room/(?P<room_pk>\d+)/$', ChatConsumer.as_asgi()),  # type: ignore[arg-type] # pyrefly: ignore
    re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),  # type: ignore[arg-type] # pyrefly: ignore
]
