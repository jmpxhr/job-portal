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
        EMPLOYER = 1, 'Employer'
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
        default=True,
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

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    @override
    def __str__(self) -> str:
        return f'User[id={self.pk}]'

    class Meta(TypedModelMeta):
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')


class JobSeeker(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    class Meta(TypedModelMeta):
        db_table = 'jobseekers'
        verbose_name = _('job seeker')
        verbose_name_plural = _('job seekers')


class Industry(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'industries'
        ordering = ['name']
        verbose_name_plural = 'Industries'


class Company(models.Model):
    class CompanySizeEnum(models.IntegerChoices):
        SMALL = 0, '1-50 employees'
        MEDIUM = 1, '51-200 employees'
        LARGE = 2, '201-500 employees'
        XLARGE = 3, '500+ employees'

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    industry = models.ForeignKey(
        Industry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    email = models.EmailField(unique=False, blank=True)
    size = EnumField(CompanySizeEnum, default=CompanySizeEnum.SMALL)
    website = models.CharField(max_length=150, blank=True)

    class Meta(TypedModelMeta):
        db_table = 'companies'
        verbose_name = _('Company')
        verbose_name_plural = _('Companies')
