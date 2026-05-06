from typing import TYPE_CHECKING, override

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_stubs_ext.db.models import TypedModelMeta

from server.common.models import TimeStampModelMixin

if TYPE_CHECKING:
    from server.apps.accounts.models import User as UserType
    from server.apps.jobs.models import JobApplication


class ChatRoom(TimeStampModelMixin):
    application: models.OneToOneField['JobApplication'] = models.OneToOneField(
        'jobs.JobApplication',
        on_delete=models.CASCADE,
        related_name='chat_room',
        verbose_name=_('application'),
    )

    @override
    def __str__(self) -> str:
        return f'ChatRoom[{self.application_id}]'  # pyrefly: ignore

    @property
    def other_user_unread_count(self) -> int:
        return (
            self.notifications.aggregate(  # pyrefly: ignore
                total=models.Sum('unread_count'),
            )['total']
            or 0
        )

    class Meta(TypedModelMeta):
        db_table = 'chat_rooms'
        verbose_name = _('chat room')
        verbose_name_plural = _('chat rooms')


class ChatMessage(TimeStampModelMixin):
    room: models.ForeignKey['ChatRoom'] = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('chat room'),
    )
    sender: models.ForeignKey['UserType'] = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='chat_messages',
        verbose_name=_('sender'),
    )
    content = models.TextField(_('content'))
    is_read = models.BooleanField(_('is read'), default=False)

    @override
    def __str__(self) -> str:
        return f'Message[{self.pk}] in Room[{self.room_id}]'

    class Meta(TypedModelMeta):
        db_table = 'chat_messages'
        ordering = ['created_at']
        verbose_name = _('chat message')
        verbose_name_plural = _('chat messages')


class ChatNotification(models.Model):
    user: models.ForeignKey['UserType'] = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='chat_notifications',
        verbose_name=_('user'),
    )
    room: models.ForeignKey['ChatRoom'] = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('chat room'),
    )
    unread_count = models.PositiveIntegerField(_('unread count'), default=0)

    @override
    def __str__(self) -> str:
        return (
            f'Notification[{self.user_id} in Room[{self.room_id}]]: '  # pyrefly: ignore
            f'{self.unread_count}'
        )

    class Meta(TypedModelMeta):
        db_table = 'chat_notifications'
        verbose_name = _('chat notification')
        verbose_name_plural = _('chat notifications')
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'room'],
                name='unique_user_room_notification',
            ),
        ]
