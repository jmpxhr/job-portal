from django.contrib import admin

from server.apps.skill_tests.models import (
    SkillTest,
    SkillTestAttempt,
    SkillVerification,
)


@admin.register(SkillTest)
class SkillTestAdmin(admin.ModelAdmin[SkillTest]):
    list_display = ('id', 'skill', 'difficulty', 'expires_at', 'created_at')
    list_filter = ('difficulty', 'created_at')
    search_fields = ('skill__name',)
    list_select_related = ('skill',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SkillTestAttempt)
class SkillTestAttemptAdmin(admin.ModelAdmin[SkillTestAttempt]):
    list_display = (
        'id',
        'jobseeker',
        'skill_test',
        'score',
        'passed',
        'created_at',
    )
    list_filter = ('passed', 'created_at')
    search_fields = ('jobseeker__user__email',)
    list_select_related = ('jobseeker__user', 'skill_test__skill')


@admin.register(SkillVerification)
class SkillVerificationAdmin(admin.ModelAdmin[SkillVerification]):
    list_display = (
        'id',
        'jobseeker',
        'skill',
        'difficulty',
        'best_score',
        'verified_at',
    )
    list_filter = ('difficulty', 'verified_at')
    search_fields = ('jobseeker__user__email', 'skill__name')
    list_select_related = ('jobseeker__user', 'skill')
