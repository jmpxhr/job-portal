from datetime import timedelta

from django.tasks import task
from django.utils import timezone

from server.apps.job_advice import const
from server.apps.job_advice.models import JobAdvice, JobAdviceStatusEnum
from server.apps.job_advice.services import JobAdviceGenerator


@task
def generate_job_advice(advice_id: int) -> None:
    try:
        advice = (
            JobAdvice.objects
            .select_related(
                'jobseeker',
                'job',
                'job__company',
                'job__company__industry',
            )
            .prefetch_related(
                'jobseeker__skills',
                'jobseeker__education',
                'jobseeker__experience',
                'jobseeker__languages',
                'job__skills',
            )
            .get(pk=advice_id)
        )
    except JobAdvice.DoesNotExist:
        return

    try:
        generator = JobAdviceGenerator()
        result = generator.generate(
            advice.jobseeker,
            advice.job,
            language=advice.language,
        )
        advice.advice = result
        advice.status = JobAdviceStatusEnum.READY
        advice.expires_at = timezone.now() + timedelta(
            days=const.ADVICE_CACHE_DAYS,
        )
        advice.save(
            update_fields=[
                'advice',
                'status',
                'expires_at',
                'updated_at',
            ],
        )
    except Exception as e:
        advice.status = JobAdviceStatusEnum.FAILED
        advice.error_message = str(e)[:500]
        advice.save(
            update_fields=[
                'status',
                'error_message',
                'updated_at',
            ],
        )
