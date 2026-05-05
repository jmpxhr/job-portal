from typing import TYPE_CHECKING, Any, override

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from server.apps.chat.models import ChatMessage, ChatNotification, ChatRoom
from server.apps.chat.utils import send_notification_update_sync
from server.apps.jobs.models import JobApplication
from server.common.types import AuthenticatedHttpRequest

if TYPE_CHECKING:
    from server.apps.accounts.models import User as UserType

User = get_user_model()


_select_related_company = (
    'application__job',
    'application__jobseeker__user',
    'application__jobseeker',
    'application__job__company',
    'application__job__company__recruiter__user',
)


class ChatListView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/chat-list.html'
    request: AuthenticatedHttpRequest  # pyrefly: ignore

    @override
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.account_type == User.AccountTypeEnum.JOBSEEKER:  # pyrefly: ignore
            rooms = (
                ChatRoom.objects
                .filter(
                    application__jobseeker__user=user,
                )
                .select_related(*_select_related_company)
                .prefetch_related('messages')
                .order_by('-updated_at')
            )
        elif user.account_type == User.AccountTypeEnum.COMPANY:  # pyrefly: ignore
            rooms = (
                ChatRoom.objects
                .filter(
                    application__job__company__recruiter__user=user,
                )
                .select_related(*_select_related_company)
                .prefetch_related('messages')
                .order_by('-updated_at')
            )
        else:
            rooms = ChatRoom.objects.none()

        notifications = ChatNotification.objects.filter(
            user=user,
        ).values('room_id', 'unread_count')
        unread_map = {n['room_id']: n['unread_count'] for n in notifications}

        rooms_with_data = []
        for room in rooms:
            last_message = (
                room.messages.order_by('-created_at').first()  # pyrefly: ignore
                if room.messages.exists()  # pyrefly: ignore
                else None
            )
            rooms_with_data.append({
                'room': room,
                'last_message': last_message,
                'unread_count': unread_map.get(room.pk, 0),
            })

        context['rooms_with_data'] = rooms_with_data
        context['total_unread'] = sum(unread_map.values())
        return context


class ChatListModalView(LoginRequiredMixin, View):
    request: AuthenticatedHttpRequest  # pyrefly: ignore

    def get(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        user = request.user

        if user.account_type == User.AccountTypeEnum.JOBSEEKER:  # pyrefly: ignore
            rooms = (
                ChatRoom.objects
                .filter(
                    application__jobseeker__user=user,
                )
                .select_related(*_select_related_company)
                .prefetch_related('messages')
                .order_by('-updated_at')
            )
        elif user.account_type == User.AccountTypeEnum.COMPANY:  # pyrefly: ignore
            rooms = (
                ChatRoom.objects
                .filter(
                    application__job__company__recruiter__user=user,
                )
                .select_related(*_select_related_company)
                .prefetch_related('messages')
                .order_by('-updated_at')
            )
        else:
            rooms = ChatRoom.objects.none()

        notifications = ChatNotification.objects.filter(
            user=user,
        ).values('room_id', 'unread_count')
        unread_map = {n['room_id']: n['unread_count'] for n in notifications}

        rooms_with_data = []
        for room in rooms:
            last_message = (
                room.messages.order_by('-created_at').first()  # pyrefly: ignore
                if room.messages.exists()  # pyrefly: ignore
                else None
            )
            rooms_with_data.append({
                'room': room,
                'last_message': last_message,
                'unread_count': unread_map.get(room.pk, 0),
            })

        return render(request, 'chat/chat-list-partial.html', {
            'rooms_with_data': rooms_with_data,
        })


class UnreadCountView(LoginRequiredMixin, View):
    request: AuthenticatedHttpRequest  # pyrefly: ignore

    def get(self, request: AuthenticatedHttpRequest) -> JsonResponse:
        return JsonResponse({'unread_count': get_unread_count(request.user)})


class ChatRoomView(LoginRequiredMixin, View):
    request: AuthenticatedHttpRequest  # pyrefly: ignore

    def get(self, request: AuthenticatedHttpRequest, pk: int) -> HttpResponse:
        user = request.user

        room = get_object_or_404(
            ChatRoom.objects.select_related(
                'application__job',
                'application__jobseeker__user',
                'application__jobseeker',
                'application__job__company',
                'application__job__company__recruiter__user',
            ),
            pk=pk,
        )

        if not self._user_has_access(room, user):
            raise Http404

        ChatMessage.objects.filter(
            room=room,
            is_read=False,
        ).exclude(sender=user).update(is_read=True)

        ChatNotification.objects.filter(
            user=user,
            room=room,
        ).update(unread_count=0)

        send_notification_update_sync(user.pk)

        messages = room.messages.select_related('sender').order_by('created_at')  # pyrefly: ignore

        if user == room.application.jobseeker.user:
            other_user = room.application.job.company.recruiter.user
        else:
            other_user = room.application.jobseeker.user

        return render(request, 'chat/chat-modal.html', {
            'room': room,
            'messages': messages,
            'other_user': other_user,
            'job': room.application.job,
            'user': user,
        })

    def _user_has_access(self, room: ChatRoom, user: 'UserType') -> bool:
        if user == room.application.jobseeker.user:
            return True
        try:
            return user == room.application.job.company.recruiter.user
        except Exception:
            return False


class StartChatView(LoginRequiredMixin, View):
    request: AuthenticatedHttpRequest  # pyrefly: ignore

    def get(
        self,
        request: AuthenticatedHttpRequest,
        application_pk: int,
    ) -> HttpResponse:
        user = request.user

        application = get_object_or_404(
            JobApplication.objects.select_related(
                'jobseeker__user',
                'job__company__recruiter__user',
            ),
            pk=application_pk,
        )

        if not self._has_access(application, user):
            raise Http404

        room, _created = ChatRoom.objects.get_or_create(
            application=application,
        )

        ChatNotification.objects.get_or_create(
            user=application.jobseeker.user,
            room=room,
            defaults={'unread_count': 0},
        )
        ChatNotification.objects.get_or_create(
            user=application.job.company.recruiter.user,
            room=room,
            defaults={'unread_count': 0},
        )

        return JsonResponse({'room_pk': room.pk})

    def _has_access(
        self,
        application: 'JobApplication',
        user: 'UserType',
    ) -> bool:
        if user == application.jobseeker.user:
            return True
        try:
            return user == application.job.company.recruiter.user
        except Exception:
            return False


class SendMessageView(LoginRequiredMixin, View):
    request: AuthenticatedHttpRequest  # pyrefly: ignore

    def post(self, request: AuthenticatedHttpRequest, pk: int) -> HttpResponse:
        room = get_object_or_404(
            ChatRoom.objects.select_related(
                'application__jobseeker__user',
                'application__job__company__recruiter__user',
            ),
            pk=pk,
        )
        content = request.POST.get('content', '').strip()

        if not content:
            return redirect('chat:list')

        ChatMessage.objects.create(
            room=room,
            sender=request.user,
            content=content,
        )

        ChatNotification.objects.filter(
            user=request.user,
            room=room,
        ).update(unread_count=0)

        other_user = (
            room.application.job.company.recruiter.user
            if request.user == room.application.jobseeker.user
            else room.application.jobseeker.user
        )
        ChatNotification.objects.filter(
            user=other_user,
            room=room,
        ).update(unread_count=F('unread_count') + 1)

        send_notification_update_sync(request.user.pk)
        send_notification_update_sync(other_user.pk)

        return redirect('chat:list')


def get_unread_count(user: 'UserType') -> int:
    result = ChatNotification.objects.filter(
        user=user,
    ).aggregate(total=Sum('unread_count'))
    return result['total'] or 0