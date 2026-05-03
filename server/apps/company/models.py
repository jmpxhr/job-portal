from typing import TYPE_CHECKING, override

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_enum import EnumField
from django_stubs_ext.db.models import TypedModelMeta

from server.common.models import TimeStampModelMixin

if TYPE_CHECKING:
    from server.apps.accounts.models import Recruiter


class Industry(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    @override
    def __str__(self) -> str:
        return self.name

    class Meta(TypedModelMeta):
        db_table = 'industries'
        ordering = ['name']
        verbose_name_plural = 'Industries'


class Benefit(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon_class = models.CharField(
        max_length=100,
        blank=True,
        default='bi-check-circle-fill',
    )

    @override
    def __str__(self) -> str:
        return self.name

    class Meta(TypedModelMeta):
        db_table = 'benefits'
        ordering = ['name']


class StudentProgram(TimeStampModelMixin):
    class ProgramStatusEnum(models.IntegerChoices):
        APPLICATIONS_OPEN = 0, 'Applications Open'
        STARTING_SOON = 1, 'Starting Soon'
        ONGOING = 2, 'Ongoing'
        CLOSED = 3, 'Closed'

    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        related_name='student_programs',
    )
    title = models.CharField(_('program title'), max_length=200)
    description = models.TextField(
        _('description'), blank=True, default='',
    )
    status = EnumField(
        ProgramStatusEnum,
        default=ProgramStatusEnum.APPLICATIONS_OPEN,
    )
    url = models.URLField(_('program URL'), blank=True, default='')

    @override
    def __str__(self) -> str:
        return f'{self.title} ({self.company.name})'

    class Meta(TypedModelMeta):
        db_table = 'student_programs'
        ordering = ['-created_at']
        verbose_name = _('Student Program')
        verbose_name_plural = _('Student Programs')


class Company(models.Model):
    class CompanySizeEnum(models.IntegerChoices):
        SMALL = 0, '1-50 employees'
        MEDIUM = 1, '51-200 employees'
        LARGE = 2, '201-500 employees'
        XLARGE = 3, '500+ employees'

    recruiter: models.OneToOneField['Recruiter'] = models.OneToOneField(
        'accounts.Recruiter',
        on_delete=models.CASCADE,
        related_name='company',
    )
    name = models.CharField(_('company name'), max_length=150, blank=True)
    industry = models.ForeignKey(
        Industry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    email = models.EmailField(_('company email'), unique=False, blank=True)
    size = EnumField(CompanySizeEnum, default=CompanySizeEnum.SMALL)
    website = models.CharField(max_length=150, blank=True)
    description = models.TextField(_('about company'), blank=True, default='')
    logo = models.ImageField(
        _('company logo'),
        upload_to='company/logos/',
        blank=True,
        default='',
    )
    cover_image = models.ImageField(
        _('cover image'),
        upload_to='company/covers/',
        blank=True,
        default='',
    )
    founded_year = models.PositiveIntegerField(
        _('founded year'),
        null=True,
        blank=True,
    )
    phone = models.CharField(
        _('phone number'), max_length=30, blank=True, default='',
    )
    headquarters = models.CharField(
        _('headquarters'),
        max_length=150,
        blank=True,
        default='',
    )
    linkedin_url = models.URLField(
        _('LinkedIn URL'), blank=True, default='',
    )
    telegram_url = models.URLField(
        _('Telegram URL'), blank=True, default='',
    )
    hr_contact_name = models.CharField(
        _('HR contact name'), max_length=150, blank=True, default='',
    )
    hr_contact_position = models.CharField(
        _('HR contact position'),
        max_length=150,
        blank=True,
        default='',
    )
    hr_contact_email = models.EmailField(
        _('HR contact email'), blank=True, default='',
    )
    benefits = models.ManyToManyField(
        Benefit, blank=True, related_name='companies',
    )

    @override
    def __str__(self) -> str:
        return f'Company[{self.name}]'

    @property
    def size_label(self) -> str:
        return self.CompanySizeEnum(self.size).label

    @property
    def initial(self) -> str:
        return (self.name or '?')[0].upper()

    @property
    def open_jobs_count(self) -> int:
        return 0

    @property
    def display_size(self) -> str:
        return self.CompanySizeEnum(self.size).label

    def get_first_letter(self) -> str:
        return (self.name or '')[:1].upper()

    class Meta(TypedModelMeta):
        db_table = 'companies'
        verbose_name = _('Company')
        verbose_name_plural = _('Companies')
        ordering = ['name']
