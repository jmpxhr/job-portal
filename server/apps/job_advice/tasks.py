import logging
from datetime import timedelta

from django.tasks import task
from django.utils import timezone

from server.apps.job_advice import const
from server.apps.job_advice.models import JobAdvice, JobAdviceStatusEnum
from server.apps.job_advice.services import (
    SUITABILITY_HIGH,
    SUITABILITY_MEDIUM,
    JobAdviceGenerator,
)

logger = logging.getLogger('django')


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
        return

    _try_auto_apply(advice)


def _try_auto_apply(advice: JobAdvice) -> None:
    from server.apps.jobs.models import JobApplication

    jobseeker = advice.jobseeker
    if not jobseeker.is_active_search:
        return

    suitability = (advice.advice or {}).get('suitability', '').lower()
    threshold = jobseeker.auto_apply_threshold

    meets_threshold = suitability == SUITABILITY_HIGH or (
        threshold == SUITABILITY_MEDIUM and suitability == SUITABILITY_MEDIUM
    )
    if not meets_threshold:
        return

    if not advice.job.is_active:
        return

    if JobApplication.objects.filter(
        job=advice.job,
        jobseeker=jobseeker,
    ).exists():
        return

    JobApplication.objects.create(
        job=advice.job,
        jobseeker=jobseeker,
        cover_letter=jobseeker.auto_apply_cover_letter,
        is_auto_applied=True,
    )
    logger.info(
        'Auto-applied jobseeker=%s to job=%s (suitability=%s)',
        jobseeker.pk,
        advice.job.pk,
        suitability,
    )


@task
def auto_match_jobseeker(jobseeker_id: int) -> None:
    from server.apps.accounts.models import JobSeeker
    from server.apps.jobs.models import Job, JobApplication

    try:
        jobseeker = JobSeeker.objects.get(pk=jobseeker_id)
    except JobSeeker.DoesNotExist:
        return

    if not jobseeker.is_active_search:
        return

    existing_advice_job_ids = set(
        JobAdvice.objects.filter(jobseeker=jobseeker).values_list(
            'job_id',
            flat=True,
        ),
    )
    existing_application_job_ids = set(
        JobApplication.objects.filter(jobseeker=jobseeker).values_list(
            'job_id',
            flat=True,
        ),
    )
    excluded_job_ids = existing_advice_job_ids | existing_application_job_ids
    active_jobs = Job.objects.filter(is_active=True).exclude(
        pk__in=excluded_job_ids,
    )
    for job in active_jobs:
        advice = JobAdvice.objects.create(
            jobseeker=jobseeker,
            job=job,
            language=jobseeker.lang,
        )
        generate_job_advice.enqueue(advice.pk)

    logger.info(
        'Enqueued auto-match for jobseeker=%s, %d jobs to process',
        jobseeker.pk,
        active_jobs.count(),
    )


@task
def auto_match_new_job(job_id: int) -> None:
    from server.apps.accounts.models import JobSeeker
    from server.apps.jobs.models import Job

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        return

    if not job.is_active:
        return

    active_seekers = JobSeeker.objects.filter(
        is_active_search=True,
        user__is_active=True,
    )

    existing = set(
        JobAdvice.objects.filter(job=job).values_list(
            'jobseeker_id',
            flat=True,
        ),
    )

    for jobseeker in active_seekers:
        if jobseeker.pk in existing:
            continue

        advice = JobAdvice.objects.create(
            jobseeker=jobseeker,
            job=job,
            language=jobseeker.lang,
        )
        generate_job_advice.enqueue(advice.pk)

    logger.info(
        'Enqueued auto-match for new job=%s, %d active seekers',
        job.pk,
        active_seekers.count(),
    )
