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


class JobSeeker(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='jobseeker',
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
