from channels.layers import get_channel_layer
from django.db.models import Sum

from server.apps.chat.models import ChatNotification


async def send_notification_update(user_id: int) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    unread_count = await _get_unread_count_async(user_id)
    await channel_layer.group_send(
        f'notifications_{user_id}',
        {
            'type': 'notification_update',
            'unread_count': unread_count,
        },
    )


def send_notification_update_sync(user_id: int) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    unread_count = _get_unread_count_sync(user_id)
    channel_layer.group_send(
        f'notifications_{user_id}',
        {
            'type': 'notification_update',
            'unread_count': unread_count,
        },
    )


async def _get_unread_count_async(user_id: int) -> int:
    from asgiref.sync import sync_to_async

    return await sync_to_async(_get_unread_count_sync)(user_id)


def _get_unread_count_sync(user_id: int) -> int:
    result = ChatNotification.objects.filter(
        user_id=user_id,
    ).aggregate(total=Sum('unread_count'))
    return result['total'] or 0