from typing import TYPE_CHECKING, override

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_enum import EnumField
from django_stubs_ext.db.models import TypedModelMeta

from server.common.models import TimeStampModelMixin

if TYPE_CHECKING:
    from server.apps.accounts.models import JobSeeker as JobSeekerType
    from server.apps.jobs.models import Job as JobType


class JobAdviceStatusEnum(models.IntegerChoices):
    PENDING = 0, _('Pending')
    READY = 1, _('Ready')
    FAILED = 2, _('Failed')


class JobAdvice(TimeStampModelMixin):
    jobseeker: models.ForeignKey['JobSeekerType'] = models.ForeignKey(
        'accounts.JobSeeker',
        on_delete=models.CASCADE,
        related_name='job_advices',
        verbose_name=_('job seeker'),
    )
    job: models.ForeignKey['JobType'] = models.ForeignKey(
        'jobs.Job',
        on_delete=models.CASCADE,
        related_name='advices',
        verbose_name=_('job'),
    )
    status = EnumField(
        JobAdviceStatusEnum,
        default=JobAdviceStatusEnum.PENDING,
        verbose_name=_('status'),
    )
    advice = models.JSONField(
        _('advice'),
        blank=True,
        null=True,
        help_text=_(
            'Structured AI advice: '
            '{suitability, summary, matching_skills, missing_skills, '
            'strengths, areas_to_improve, recommendations}',
        ),
    )
    language = models.CharField(
        _('language'),
        max_length=10,
        default='en',
        help_text=_('Language code for advice (e.g. "en", "ru")'),
    )
    error_message = models.TextField(
        _('error message'),
        blank=True,
        default='',
    )
    expires_at = models.DateTimeField(
        _('expires at'),
        blank=True,
        null=True,
    )

    @override
    def __str__(self) -> str:
        return f'JobAdvice[{self.jobseeker} - {self.job}]'

    class Meta(TypedModelMeta):
        db_table = 'job_advices'
        verbose_name = _('job advice')
        verbose_name_plural = _('job advices')
        constraints = [
            models.UniqueConstraint(
                fields=['jobseeker', 'job'],
                name='unique_job_advice_per_jobseeker',
            ),
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['expires_at']),
        ]
