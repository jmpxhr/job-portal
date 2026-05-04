from typing import TYPE_CHECKING, override

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_enum import EnumField
from django_stubs_ext.db.models import TypedModelMeta

from server.common.models import TimeStampModelMixin

if TYPE_CHECKING:
    from django.utils.functional import _StrPromise

    from server.apps.accounts.models import JobSeeker
    from server.apps.company.models import Company


class Skill(models.Model):
    name = models.CharField(_('name'), max_length=100, unique=True)
    slug = models.SlugField(_('slug'), max_length=100, unique=True, blank=True)

    @override
    def __str__(self) -> str:
        return self.name

    @override
    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        if not self.slug:
            self.slug = self.name.lower().replace(' ', '-')
        super().save(*args, **kwargs)

    class Meta(TypedModelMeta):
        db_table = 'skills'
        ordering = ['name']
        verbose_name = _('skill')
        verbose_name_plural = _('skills')


class Job(TimeStampModelMixin):
    class ExperienceLevelEnum(models.IntegerChoices):
        NO_MATTER = 0, _("Doesn't matter")
        NO_EXPERIENCE = 1, _('No experience')
        ENTRY_LEVEL = 2, _('From 1 year to 3 years')
        MIDDLE_LEVEL = 3, _('From 3 to 6 years')
        HIGH_LEVEL = 4, _('More than 6 years')

    class WorkFormatEnum(models.IntegerChoices):
        REMOTE = 0, _('Remote')
        HYBRID = 1, _('Hybrid')
        ON_SITE = 2, _('On-site')

    class ScheduleEnum(models.IntegerChoices):
        FIXED = 0, _('Fixed hours')
        FLEXIBLE = 1, _('Flexible hours')

    class EmploymentTypeEnum(models.IntegerChoices):
        FULL_TIME = 0, _('Full-time')
        PART_TIME = 1, _('Part-time')
        INTERNSHIP = 2, _('Internship')

    company: models.ForeignKey['Company'] = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='jobs',
        verbose_name=_('company'),
    )
    title = models.CharField(_('title'), max_length=200)
    description = models.TextField(_('description'), blank=True, default='')
    experience_level = EnumField(
        ExperienceLevelEnum,
        default=ExperienceLevelEnum.ENTRY_LEVEL,
    )
    work_format = EnumField(WorkFormatEnum, default=WorkFormatEnum.REMOTE)
    schedule = EnumField(ScheduleEnum, default=ScheduleEnum.FLEXIBLE)
    employment_type = EnumField(
        EmploymentTypeEnum,
        default=EmploymentTypeEnum.FULL_TIME,
    )

    salary_min = models.PositiveIntegerField(
        _('salary min'),
        blank=True,
        null=True,
    )
    salary_max = models.PositiveIntegerField(
        _('salary max'),
        blank=True,
        null=True,
    )
    location = models.CharField(
        _('location'),
        max_length=150,
        blank=True,
        default='',
    )
    is_student_friendly = models.BooleanField(
        _('student friendly'),
        default=False,
    )
    is_active = models.BooleanField(_('active'), default=True)
    posted_at = models.DateTimeField(_('posted at'), auto_now_add=True)

    skills = models.ManyToManyField(
        Skill,
        blank=True,
        related_name='jobs',
        verbose_name=_('skills'),
    )

    @override
    def __str__(self) -> str:
        return f'{self.title} @ {self.company.name}'

    @property
    def salary_display(self) -> '_StrPromise | str':
        if self.salary_min and self.salary_max:
            return f'${self.salary_min} - ${self.salary_max}/month'
        if self.salary_min:
            return f'From ${self.salary_min}/month'
        if self.salary_max:
            return f'Up to ${self.salary_max}/month'
        return _('Salary not specified')

    @property
    def experience_level_label(self) -> '_StrPromise':
        return self.ExperienceLevelEnum(self.experience_level).label

    @property
    def work_format_label(self) -> '_StrPromise':
        return self.WorkFormatEnum(self.work_format).label

    @property
    def schedule_label(self) -> '_StrPromise':
        return self.ScheduleEnum(self.schedule).label

    @property
    def employment_type_label(self) -> '_StrPromise':
        return self.EmploymentTypeEnum(self.employment_type).label

    class Meta(TypedModelMeta):
        db_table = 'jobs'
        ordering = ['-posted_at']
        verbose_name = _('job')
        verbose_name_plural = _('jobs')
        indexes = [
            models.Index(fields=['experience_level']),
            models.Index(fields=['is_active', '-posted_at']),
        ]


class JobApplication(TimeStampModelMixin):
    class StatusEnum(models.IntegerChoices):
        PENDING = 0, _('Pending')
        REVIEWED = 1, _('Reviewed')
        ACCEPTED = 2, _('Accepted')
        REJECTED = 3, _('Rejected')

    job: models.ForeignKey['Job'] = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name=_('job'),
    )
    jobseeker: models.ForeignKey['JobSeeker'] = models.ForeignKey(
        'accounts.JobSeeker',
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name=_('job seeker'),
    )
    status = EnumField(StatusEnum, default=StatusEnum.PENDING)
    resume = models.FileField(
        _('resume'),
        upload_to='applications/resumes/',
        blank=True,
    )
    cover_letter = models.TextField(
        _('cover letter'),
        blank=True,
        default='',
    )
    employer_feedback = models.TextField(
        _('employer feedback'),
        blank=True,
        default='',
    )
    applied_at = models.DateTimeField(_('applied at'), auto_now_add=True)

    @override
    def __str__(self) -> str:
        return f'Application by {self.jobseeker} for {self.job}'

    @property
    def status_label(self) -> str:
        labels = {
            self.StatusEnum.PENDING: 'Pending',
            self.StatusEnum.REVIEWED: 'In Review',
            self.StatusEnum.ACCEPTED: 'Accepted',
            self.StatusEnum.REJECTED: 'Not Selected',
        }
        return labels.get(self.status, 'Unknown')

    @property
    def status_css_class(self) -> str:
        classes = {
            self.StatusEnum.PENDING: 'status-pending',
            self.StatusEnum.REVIEWED: 'status-review',
            self.StatusEnum.ACCEPTED: 'status-accepted',
            self.StatusEnum.REJECTED: 'status-rejected',
        }
        return classes.get(self.status, 'status-pending')

    class Meta(TypedModelMeta):
        db_table = 'job_applications'
        ordering = ['-applied_at']
        verbose_name = _('job application')
        verbose_name_plural = _('job applications')
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'jobseeker'],
                name='unique_job_application',
            ),
        ]


class SavedJob(TimeStampModelMixin):
    job: models.ForeignKey['Job'] = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='saved_by',
        verbose_name=_('job'),
    )
    jobseeker: models.ForeignKey['JobSeeker'] = models.ForeignKey(
        'accounts.JobSeeker',
        on_delete=models.CASCADE,
        related_name='saved_jobs',
        verbose_name=_('job seeker'),
    )
    saved_at = models.DateTimeField(_('saved at'), auto_now_add=True)

    @override
    def __str__(self) -> str:
        return f'{self.jobseeker} saved {self.job}'

    class Meta(TypedModelMeta):
        db_table = 'saved_jobs'
        ordering = ['-saved_at']
        verbose_name = _('saved job')
        verbose_name_plural = _('saved jobs')
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'jobseeker'],
                name='unique_saved_job',
            ),
        ]
