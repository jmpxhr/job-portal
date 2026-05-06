from server.apps.chat.views import get_unread_count


def unread_messages(request: object) -> dict[str, int]:
    if hasattr(request, 'user') and request.user.is_authenticated:
        return {'unread_messages_count': get_unread_count(request.user)}
    return {'unread_messages_count': 0}
