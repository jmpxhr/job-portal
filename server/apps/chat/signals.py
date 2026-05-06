from django.db.models.signals import post_save
from django.dispatch import receiver

from server.apps.jobs.models import JobApplication

from .models import ChatNotification, ChatRoom


@receiver(post_save, sender=JobApplication)
def create_chat_room(
    sender: type[JobApplication],
    instance: JobApplication,
    created: bool,  # noqa: FBT001
    **kwargs: object,
) -> None:
    if created:
        room = ChatRoom.objects.create(application=instance)
        ChatNotification.objects.bulk_create([
            ChatNotification(
                user=instance.jobseeker.user,
                room=room,
                unread_count=0,
            ),
            ChatNotification(
                user=instance.job.company.recruiter.user,
                room=room,
                unread_count=0,
            ),
        ])
