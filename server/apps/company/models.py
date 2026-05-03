from typing import TYPE_CHECKING, override

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_enum import EnumField
from django_stubs_ext.db.models import TypedModelMeta

if TYPE_CHECKING:
    from server.apps.accounts.models import Recruiter


# Create your models here.
class Industry(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    @override
    def __str__(self) -> str:
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

    @override
    def __str__(self) -> str:
        return f'Company[{self.name}]'

    class Meta(TypedModelMeta):
        db_table = 'companies'
        verbose_name = _('Company')
        verbose_name_plural = _('Companies')
