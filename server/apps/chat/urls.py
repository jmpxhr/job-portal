from django.urls import path

from server.apps.chat import views

app_name = 'chat'

urlpatterns = [
    path(
        '',
        views.ChatListView.as_view(),
        name='list',
    ),
    path(
        'modal/',
        views.ChatListModalView.as_view(),
        name='list-modal',
    ),
    path(
        'unread-count/',
        views.UnreadCountView.as_view(),
        name='unread-count',
    ),
    path(
        'room/<int:pk>/',
        views.ChatRoomView.as_view(),
        name='room',
    ),
    path(
        'start/<int:application_pk>/',
        views.StartChatView.as_view(),
        name='start',
    ),
    path(
        'start-direct/<int:jobseeker_pk>/',
        views.StartDirectChatView.as_view(),
        name='start-direct',
    ),
    path(
        'room/<int:pk>/send/',
        views.SendMessageView.as_view(),
        name='send',
    ),
]
