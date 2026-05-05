from django.db import migrations


def create_chat_rooms_for_existing_applications(apps, schema_editor):
    JobApplication = apps.get_model('jobs', 'JobApplication')
    ChatRoom = apps.get_model('chat', 'ChatRoom')
    ChatNotification = apps.get_model('chat', 'ChatNotification')

    for app in JobApplication.objects.select_related(
        'jobseeker__user',
        'job__company__recruiter__user',
    ).all():
        room, created = ChatRoom.objects.get_or_create(application=app)
        if created:
            ChatNotification.objects.get_or_create(
                user=app.jobseeker.user,
                room=room,
                defaults={'unread_count': 0},
            )
            ChatNotification.objects.get_or_create(
                user=app.job.company.recruiter.user,
                room=room,
                defaults={'unread_count': 0},
            )


def reverse_chat_rooms(apps, schema_editor):
    ChatRoom = apps.get_model('chat', 'ChatRoom')
    ChatRoom.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
        ('jobs', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            create_chat_rooms_for_existing_applications,
            reverse_chat_rooms,
        ),
    ]