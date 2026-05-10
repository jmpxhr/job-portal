import json
from logging import getLogger
from typing import Any, override

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import F

from server.apps.chat.models import (
    ChatMessage,
    ChatNotification,
    ChatRoom,
)
from server.apps.chat.utils import send_notification_update_sync
from server.apps.chat.views import _get_other_user, _user_has_room_access

logger = getLogger('django')


class ChatConsumer(AsyncWebsocketConsumer):
    @override
    async def connect(self) -> None:
        self.room_pk = self.scope['url_route']['kwargs']['room_pk']
        self.group_name = f'chat_{self.room_pk}'
        self.user = self.scope.get('user')

        if self.user is None or self.user.is_anonymous:
            await self.close()
            return

        has_access = await self._user_has_access()
        if not has_access:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )
        await self.accept()

    @override
    async def disconnect(self, code: int) -> None:
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    @override
    async def receive(self, text_data: str | None = None) -> None:  # type: ignore[override] # pyrefly: ignore
        if text_data is None:
            return

        data = json.loads(text_data)
        message_content = data.get('message', '').strip()
        if not message_content:
            return

        message = await self._save_message(message_content)
        await self._mark_as_read()

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat_message',
                'message_id': message.pk,
                'sender_id': self.user.pk,  # type: ignore[union-attr] # pyrefly: ignore
                'sender_name': await self._get_sender_name(),
                'content': message_content,
                'timestamp': message.created_at.isoformat(),
            },
        )

    async def chat_message(self, event: dict[str, Any]) -> None:
        await self.send(
            text_data=json.dumps({
                'message_id': event['message_id'],
                'sender_id': event['sender_id'],
                'sender_name': event['sender_name'],
                'content': event['content'],
                'timestamp': event['timestamp'],
            }),
        )

    @database_sync_to_async
    def _user_has_access(self) -> bool:
        try:
            room = ChatRoom.objects.select_related(
                'application__jobseeker__user',
                'application__job__company__recruiter__user',
                'jobseeker_user',
                'recruiter_user',
            ).get(pk=self.room_pk)
        except ChatRoom.DoesNotExist:
            return False
        return _user_has_room_access(room, self.user)  # type: ignore[arg-type]

    @database_sync_to_async
    def _save_message(self, content: str) -> ChatMessage:
        message = ChatMessage.objects.create(  # type: ignore[misc]
            room_id=self.room_pk,
            sender=self.user,
            content=content,
        )

        room = ChatRoom.objects.select_related(
            'application__jobseeker__user',
            'application__job__company__recruiter__user',
            'jobseeker_user',
            'recruiter_user',
        ).get(pk=self.room_pk)

        ChatNotification.objects.filter(
            user=self.user,
            room=room,
        ).update(unread_count=0)  # type: ignore[misc]

        other_user = _get_other_user(room, self.user)  # type: ignore[arg-type]
        ChatNotification.objects.filter(
            user=other_user,
            room=room,
        ).update(unread_count=F('unread_count') + 1)

        send_notification_update_sync(self.user.pk)  # type: ignore[union-attr] # pyrefly: ignore
        send_notification_update_sync(other_user.pk)

        return message

    @database_sync_to_async
    def _mark_as_read(self) -> None:
        ChatMessage.objects.filter(
            room_id=self.room_pk,
            is_read=False,
        ).exclude(sender=self.user).update(is_read=True)  # type: ignore[misc]

    @database_sync_to_async
    def _get_sender_name(self) -> str:
        return self.user.get_full_name() or self.user.email  # type: ignore[no-any-return, union-attr] # pyrefly: ignore


class NotificationConsumer(AsyncWebsocketConsumer):
    @override
    async def connect(self) -> None:
        self.user = self.scope.get('user')
        if self.user is None or self.user.is_anonymous:
            await self.close()
            return

        self.group_name = f'notifications_{self.user.pk}'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )
        await self.accept()

    @override
    async def disconnect(self, code: int) -> None:
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def notification_update(self, event: dict[str, Any]) -> None:
        await self.send(
            text_data=json.dumps({
                'type': 'notification_update',
                'unread_count': event['unread_count'],
            }),
        )
