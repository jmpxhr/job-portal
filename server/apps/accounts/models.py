import secrets
from typing import Any, ClassVar, override

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_enum import EnumField
from django_stubs_ext.db.models import TypedModelMeta

from server.common.models import TimeStampModelMixin


class UserManager(BaseUserManager['User']):
    def create_user(
        self,
        email: str,
        password: str,
        **extra_fields: dict[str, Any],
    ) -> 'User':
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(
        self,
        email: str,
        password: str,
        **extra_fields: Any,
    ) -> 'User':
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class AccountTypeEnum(models.IntegerChoices):
        EMPTY = 0, 'Empty'
        JOBSEEKER = 1, 'Job Seeker'
        COMPANY = 2, 'Company'

    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    email = models.EmailField(_('email address'), unique=True, blank=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_(
            'Designates whether the user can log into this admin site.',
        ),
    )
    is_active = models.BooleanField(
        _('active'),
        default=False,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.',
        ),
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    account_type = EnumField(
        AccountTypeEnum,
        default=AccountTypeEnum.EMPTY,
    )
    email_verification_code = models.CharField(
        max_length=6,
        blank=True,
        default='',
    )
    email_verification_sent_at = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    @override
    def __str__(self) -> str:
        return f'User[id={self.pk}]'

    def get_full_name(self) -> str:
        return f'{self.first_name} {self.last_name}'

    def generate_verification_code(self) -> str:
        code = f'{secrets.randbelow(1000000):06d}'
        self.email_verification_code = code
        self.email_verification_sent_at = timezone.now()
        self.save(
            update_fields=[
                'email_verification_code',
                'email_verification_sent_at',
            ],
        )
        return code

    class Meta(TypedModelMeta):
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')


class JobSeeker(TimeStampModelMixin):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='jobseeker',
    )
    title = models.CharField(
        _('title'),
        max_length=150,
        blank=True,
        default='',
    )
    phone = models.CharField(
        _('phone'),
        max_length=30,
        blank=True,
        default='',
    )
    location = models.CharField(
        _('location'),
        max_length=150,
        blank=True,
        default='',
    )
    about = models.TextField(
        _('about'),
        blank=True,
        default='',
    )
    avatar = models.ImageField(
        _('avatar'),
        upload_to='jobseeker/avatars/',
        blank=True,
        default='',
    )
    skills = models.ManyToManyField(
        'jobs.Skill',
        blank=True,
        related_name='jobseekers',
        verbose_name=_('skills'),
    )
    profile_visible = models.BooleanField(
        _('profile visible'),
        default=True,
    )
    resume_public = models.BooleanField(
        _('resume public'),
        default=True,
    )
    resume_objective = models.TextField(
        _('resume objective'),
        blank=True,
        default='',
    )

    @override
    def __str__(self) -> str:
        return f'JobSeeker[{self.user.email}]'

    class Meta(TypedModelMeta):
        db_table = 'jobseekers'
        verbose_name = _('job seeker')
        verbose_name_plural = _('job seekers')


class Recruiter(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='recruiter',
    )

    @override
    def __str__(self) -> str:
        return f'Recruiter[{self.user.email}]'

    class Meta(TypedModelMeta):
        db_table = 'recruiters'
        verbose_name = _('recruiter')
        verbose_name_plural = _('recruiters')


class Education(TimeStampModelMixin):
    class EducationLevelEnum(models.IntegerChoices):
        AVERAGE = 0, _('Average')
        SECONDARY_SPECIAL = 1, _('Secondary special')
        UNFINISHED_HIGHER = 2, _('Unfinished higher education')
        HIGHER = 3, _('Higher')
        BACHELOR = 4, _('Bachelor')
        MASTER = 5, _('Master')
        CANDIDATE_OF_SCIENCES = 6, _('Candidate of Sciences')
        DOCTOR_OF_SCIENCE = 7, _('Doctor of Science')

    jobseeker: models.ForeignKey['JobSeeker'] = models.ForeignKey(
        JobSeeker,
        on_delete=models.CASCADE,
        related_name='education',
        verbose_name=_('job seeker'),
    )
    level = EnumField(
        EducationLevelEnum,
        default=EducationLevelEnum.AVERAGE,
    )
    institution_name = models.CharField(
        _('institution name'),
        max_length=200,
    )
    faculty = models.CharField(
        _('faculty'),
        max_length=200,
        blank=True,
        default='',
    )
    specialization = models.CharField(
        _('specialization'),
        max_length=200,
        blank=True,
        default='',
    )
    year_of_graduation = models.PositiveIntegerField(
        _('year of graduation'),
        blank=True,
        null=True,
    )

    @override
    def __str__(self) -> str:
        return f'{self.institution_name} ({self.get_level_label()})'

    def get_level_label(self) -> str:
        return str(self.EducationLevelEnum(self.level).label)

    class Meta(TypedModelMeta):
        db_table = 'education'
        ordering = ['-year_of_graduation']
        verbose_name = _('education')
        verbose_name_plural = _('education')


class Language(TimeStampModelMixin):
    class LanguageLevelEnum(models.IntegerChoices):
        BASIC = 0, _('Basic')
        INTERMEDIATE = 1, _('Intermediate')
        FLUENT = 2, _('Fluent')
        NATIVE = 3, _('Native')

    jobseeker: models.ForeignKey['JobSeeker'] = models.ForeignKey(
        JobSeeker,
        on_delete=models.CASCADE,
        related_name='languages',
        verbose_name=_('job seeker'),
    )
    name = models.CharField(
        _('language'),
        max_length=100,
    )
    proficiency = EnumField(
        LanguageLevelEnum,
        default=LanguageLevelEnum.INTERMEDIATE,
    )

    @override
    def __str__(self) -> str:
        return f'{self.name} ({self.get_proficiency_label()})'

    def get_proficiency_label(self) -> str:
        return str(self.LanguageLevelEnum(self.proficiency).label)

    class Meta(TypedModelMeta):
        db_table = 'languages'
        ordering = ['name']
        verbose_name = _('language')
        verbose_name_plural = _('languages')


class Experience(TimeStampModelMixin):
    jobseeker: models.ForeignKey['JobSeeker'] = models.ForeignKey(
        JobSeeker,
        on_delete=models.CASCADE,
        related_name='experience',
        verbose_name=_('job seeker'),
    )
    position = models.CharField(
        _('position'),
        max_length=200,
    )
    company_name = models.CharField(
        _('company name'),
        max_length=200,
    )
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(
        _('end date'),
        blank=True,
        null=True,
    )
    description = models.TextField(
        _('description'),
        blank=True,
        default='',
    )

    @override
    def __str__(self) -> str:
        return f'{self.position} at {self.company_name}'

    @property
    def is_current(self) -> bool:
        return self.end_date is None

    class Meta(TypedModelMeta):
        db_table = 'experience'
        ordering = ['-start_date']
        verbose_name = _('experience')
        verbose_name_plural = _('experience')
