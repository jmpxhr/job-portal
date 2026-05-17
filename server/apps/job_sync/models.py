from typing import TYPE_CHECKING, override

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_enum import EnumField
from django_stubs_ext.db.models import TypedModelMeta

from server.common.models import TimeStampModelMixin

if TYPE_CHECKING:
    from server.apps.company.models import Company as CompanyType
    from server.apps.jobs.models import Job as JobType


class SourceTypeEnum(models.IntegerChoices):
    PRACA_BY = 0, 'praca.by'
    CAREER_HABR_COM = 1, 'career.habr.com'


class SyncStatusEnum(models.IntegerChoices):
    NEVER = 0, _('Never synced')
    IN_PROGRESS = 1, _('In progress')
    COMPLETED = 2, _('Completed')
    FAILED = 3, _('Failed')


class ExternalJobStatusEnum(models.IntegerChoices):
    PENDING = 0, _('Pending')
    SYNCED = 1, _('Synced')
    SKIPPED = 2, _('Skipped')
    FAILED = 3, _('Failed')


class ExternalSource(TimeStampModelMixin):
    company: models.ForeignKey['CompanyType'] = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='external_sources',
        verbose_name=_('company'),
    )
    source_type = EnumField(SourceTypeEnum, default=SourceTypeEnum.PRACA_BY)
    external_url = models.URLField(
        _('external url'),
        max_length=500,
        help_text=_(
            'URL of the company page on the external resource',
        ),
    )
    last_synced_at = models.DateTimeField(
        _('last synced at'),
        null=True,
        blank=True,
    )
    sync_status = EnumField(
        SyncStatusEnum,
        default=SyncStatusEnum.NEVER,
    )
    error_message = models.TextField(
        _('error message'),
        blank=True,
        default='',
    )

    @override
    def __str__(self) -> str:
        return f'{self.source_type}: {self.external_url}'

    class Meta(TypedModelMeta):
        db_table = 'external_sources'
        verbose_name = _('external source')
        verbose_name_plural = _('external sources')
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'source_type'],
                name='unique_company_source_type',
            ),
        ]


class ExternalJob(TimeStampModelMixin):
    company: models.ForeignKey['CompanyType'] = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='external_jobs',
        verbose_name=_('company'),
    )
    external_source: models.ForeignKey['ExternalSource'] = models.ForeignKey(
        ExternalSource,
        on_delete=models.CASCADE,
        related_name='external_jobs',
        verbose_name=_('external source'),
    )
    source_type = EnumField(
        SourceTypeEnum,
        default=SourceTypeEnum.PRACA_BY,
    )
    external_url = models.URLField(
        _('external url'),
        max_length=500,
    )
    external_id = models.CharField(
        _('external id'),
        max_length=100,
        db_index=True,
    )
    job: models.ForeignKey['JobType | None'] = models.ForeignKey(
        'jobs.Job',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='external_jobs',
        verbose_name=_('job'),
    )
    raw_data = models.JSONField(
        _('raw data'),
        blank=True,
        default=dict,
        help_text=_(
            'Raw parsed data from the external source',
        ),
    )
    status = EnumField(
        ExternalJobStatusEnum,
        default=ExternalJobStatusEnum.PENDING,
    )
    error_message = models.TextField(
        _('error message'),
        blank=True,
        default='',
    )

    @override
    def __str__(self) -> str:
        return f'{self.external_id}: {self.status}'

    class Meta(TypedModelMeta):
        db_table = 'external_jobs'
        verbose_name = _('external job')
        verbose_name_plural = _('external jobs')
        constraints = [
            models.UniqueConstraint(
                fields=['external_url'],
                name='unique_external_job_url',
            ),
        ]
