from django.db.models.signals import post_save
from django.dispatch import receiver

from server.apps.job_advice.tasks import auto_match_new_job
from server.apps.jobs.models import Job


@receiver(post_save, sender=Job)
def trigger_auto_match_on_new_job(
    sender: type[Job],
    instance: Job,
    created: bool,  # noqa: FBT001
    **kwargs: object,
) -> None:
    if created and instance.is_active:
        auto_match_new_job.enqueue(instance.pk)
