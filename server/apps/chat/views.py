from typing import TYPE_CHECKING, Any, override

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from server.apps.accounts.models import JobSeeker, Recruiter
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

_select_related_direct = (
    'jobseeker_user',
    'jobseeker_user__jobseeker',
    'recruiter_user',
    'recruiter_user__recruiter',
    'recruiter_user__recruiter__company',
)


def _get_other_user(room: ChatRoom, user: 'UserType') -> 'UserType':
    if room.application_id:
        if user == room.application.jobseeker.user:
            return room.application.job.company.recruiter.user
        return room.application.jobseeker.user
    if user == room.jobseeker_user:
        return room.recruiter_user  # type: ignore[return-value]
    return room.jobseeker_user  # type: ignore[return-value]


def _user_has_room_access(room: ChatRoom, user: 'UserType') -> bool:
    if room.application_id:
        if user == room.application.jobseeker.user:
            return True
        try:
            return user == room.application.job.company.recruiter.user
        except Exception:
            return False
    return user in (room.jobseeker_user, room.recruiter_user)


def _get_user_rooms(user: 'UserType') -> list[ChatRoom]:
    app_rooms = (
        ChatRoom.objects
        .filter(application__isnull=False)
        .select_related(*_select_related_company)
    )
    direct_rooms = (
        ChatRoom.objects
        .filter(application__isnull=True)
        .select_related(*_select_related_direct)
    )

    if user.account_type == User.AccountTypeEnum.JOBSEEKER:  # pyrefly: ignore
        app_rooms = app_rooms.filter(
            application__jobseeker__user=user,
        )
        direct_rooms = direct_rooms.filter(jobseeker_user=user)
    elif user.account_type == User.AccountTypeEnum.COMPANY:  # pyrefly: ignore
        app_rooms = app_rooms.filter(
            application__job__company__recruiter__user=user,
        )
        direct_rooms = direct_rooms.filter(recruiter_user=user)
    else:
        return []

    all_room_ids = list(app_rooms.values_list('pk', flat=True)) + list(
        direct_rooms.values_list('pk', flat=True),
    )
    if not all_room_ids:
        return []

    return list(
        ChatRoom.objects
        .filter(pk__in=all_room_ids)
        .select_related(*_select_related_company, *_select_related_direct)
        .prefetch_related('messages')
        .order_by('-updated_at')
    )


class ChatListView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/chat-list.html'
    request: AuthenticatedHttpRequest  # pyrefly: ignore

    @override
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user

        rooms = _get_user_rooms(user)

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
                'other_user': _get_other_user(room, user),
            })

        context['rooms_with_data'] = rooms_with_data
        context['total_unread'] = sum(unread_map.values())
        return context


class ChatListModalView(LoginRequiredMixin, View):
    request: AuthenticatedHttpRequest  # pyrefly: ignore

    def get(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        user = request.user

        rooms = _get_user_rooms(user)

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
                'other_user': _get_other_user(room, user),
            })

        return render(
            request,
            'chat/chat-list-partial.html',
            {
                'rooms_with_data': rooms_with_data,
            },
        )


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
                'jobseeker_user',
                'recruiter_user',
            ),
            pk=pk,
        )

        if not _user_has_room_access(room, user):
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

        other_user = _get_other_user(room, user)
        job = room.application.job if room.application_id else None  # pyrefly: ignore

        return render(
            request,
            'chat/chat-modal.html',
            {
                'room': room,
                'messages': messages,
                'other_user': other_user,
                'job': job,
                'user': user,
            },
        )


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


class StartDirectChatView(LoginRequiredMixin, View):
    request: AuthenticatedHttpRequest  # pyrefly: ignore

    def get(
        self,
        request: AuthenticatedHttpRequest,
        jobseeker_pk: int,
    ) -> HttpResponse:
        user = request.user

        jobseeker = get_object_or_404(JobSeeker, pk=jobseeker_pk)

        try:
            recruiter = user.recruiter  # pyrefly: ignore
        except Recruiter.DoesNotExist:
            raise Http404

        if jobseeker.user == user:
            raise Http404

        room, _created = ChatRoom.objects.get_or_create(
            application__isnull=True,
            jobseeker_user=jobseeker.user,
            recruiter_user=user,
            defaults={
                'jobseeker_user': jobseeker.user,
                'recruiter_user': user,
            },
        )

        ChatNotification.objects.get_or_create(
            user=jobseeker.user,
            room=room,
            defaults={'unread_count': 0},
        )
        ChatNotification.objects.get_or_create(
            user=user,
            room=room,
            defaults={'unread_count': 0},
        )

        return JsonResponse({'room_pk': room.pk})


class SendMessageView(LoginRequiredMixin, View):
    request: AuthenticatedHttpRequest  # pyrefly: ignore

    def post(self, request: AuthenticatedHttpRequest, pk: int) -> HttpResponse:
        room = get_object_or_404(ChatRoom, pk=pk)

        if not _user_has_room_access(room, request.user):
            raise Http404

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

        other_user = _get_other_user(room, request.user)
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