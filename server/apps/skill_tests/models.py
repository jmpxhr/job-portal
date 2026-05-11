from typing import TYPE_CHECKING, override

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_enum import EnumField
from django_stubs_ext.db.models import TypedModelMeta

from server.common.models import TimeStampModelMixin

if TYPE_CHECKING:
    from server.apps.accounts.models import JobSeeker as JobSeekerType
    from server.apps.jobs.models import Skill as SkillType


class SkillTestDifficultyEnum(models.IntegerChoices):
    EASY = 0, _('Easy')
    MEDIUM = 1, _('Medium')
    HARD = 2, _('Hard')


class SkillTestStatusEnum(models.IntegerChoices):
    PENDING = 0, _('Pending')
    READY = 1, _('Ready')
    FAILED = 2, _('Failed')


class SkillTest(TimeStampModelMixin):
    skill: models.ForeignKey['SkillType'] = models.ForeignKey(
        'jobs.Skill',
        on_delete=models.CASCADE,
        related_name='skill_tests',
        verbose_name=_('skill'),
    )
    difficulty = EnumField(
        SkillTestDifficultyEnum,
        default=SkillTestDifficultyEnum.EASY,
        verbose_name=_('difficulty'),
    )
    status = EnumField(
        SkillTestStatusEnum,
        default=SkillTestStatusEnum.PENDING,
        verbose_name=_('status'),
    )
    questions = models.JSONField(
        _('questions'),
        blank=True,
        null=True,
        help_text=_(
            'Structured test questions: '
            '[{"question": str, "variants": [str], "correct_index": int}]',
        ),
    )
    language = models.CharField(
        _('language'),
        max_length=10,
        default='en',
        help_text=_('Language code for test questions (e.g. "en", "ru")'),
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
        # pyrefly: ignore [missing-attribute]
        return f'SkillTest[{self.skill.name} - {self.get_difficulty_display()}]'

    class Meta(TypedModelMeta):
        db_table = 'skill_tests'
        verbose_name = _('skill test')
        verbose_name_plural = _('skill tests')
        indexes = [
            models.Index(fields=['skill', 'difficulty']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['status']),
        ]


class SkillTestAttempt(TimeStampModelMixin):
    jobseeker: models.ForeignKey['JobSeekerType'] = models.ForeignKey(
        'accounts.JobSeeker',
        on_delete=models.CASCADE,
        related_name='skill_test_attempts',
        verbose_name=_('job seeker'),
    )
    skill_test: models.ForeignKey['SkillTest'] = models.ForeignKey(
        SkillTest,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name=_('skill test'),
    )
    answers = models.JSONField(
        _('answers'),
        help_text=_('{"question_index": chosen_variant_index}'),
    )
    score = models.PositiveIntegerField(
        _('score'),
        help_text=_('Percentage score (0-100)'),
    )
    passed = models.BooleanField(
        _('passed'),
        default=False,
    )

    @override
    def __str__(self) -> str:
        status = 'Passed' if self.passed else 'Failed'
        return f'Attempt[{self.jobseeker} - {status} ({self.score}%)]'

    class Meta(TypedModelMeta):
        db_table = 'skill_test_attempts'
        ordering = ['-created_at']
        verbose_name = _('skill test attempt')
        verbose_name_plural = _('skill test attempts')
        indexes = [
            models.Index(fields=['jobseeker', 'skill_test']),
        ]


class SkillVerification(TimeStampModelMixin):
    jobseeker: models.ForeignKey['JobSeekerType'] = models.ForeignKey(
        'accounts.JobSeeker',
        on_delete=models.CASCADE,
        related_name='skill_verifications',
        verbose_name=_('job seeker'),
    )
    skill: models.ForeignKey['SkillType'] = models.ForeignKey(
        'jobs.Skill',
        on_delete=models.CASCADE,
        related_name='verifications',
        verbose_name=_('skill'),
    )
    difficulty = EnumField(
        SkillTestDifficultyEnum,
        default=SkillTestDifficultyEnum.EASY,
        verbose_name=_('difficulty'),
    )
    best_score = models.PositiveIntegerField(
        _('best score'),
        help_text=_('Highest score achieved for this skill'),
    )
    verified_at = models.DateTimeField(
        _('verified at'),
        auto_now=True,
    )

    @override
    def __str__(self) -> str:
        return (
            f'Verification[{self.jobseeker} - {self.skill.name} '
            # pyrefly: ignore [missing-attribute]
            f'{self.get_difficulty_display()} ({self.best_score}%)]'
        )

    class Meta(TypedModelMeta):
        db_table = 'skill_verifications'
        verbose_name = _('skill verification')
        verbose_name_plural = _('skill verifications')
        constraints = [
            models.UniqueConstraint(
                fields=['jobseeker', 'skill'],
                name='unique_skill_verification_per_jobseeker',
            ),
        ]
