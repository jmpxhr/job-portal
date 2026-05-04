from django.contrib import admin

from server.apps.jobs.models import Job, JobApplication, SavedJob, Skill


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin[Skill]):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Job)
class JobAdmin(admin.ModelAdmin[Job]):
    list_display = (
        'title',
        'company',
        'experience_level_label',
        'salary_display',
        'location',
        'is_active',
        'posted_at',
    )
    list_filter = (
        'experience_level',
        'work_format',
        'is_student_friendly',
        'is_active',
        'posted_at',
    )
    search_fields = ('title', 'description', 'company__name')
    filter_horizontal = ('skills',)
    date_hierarchy = 'posted_at'
    list_select_related = ('company',)


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin[JobApplication]):
    list_display = ('job', 'jobseeker', 'status', 'applied_at')
    list_filter = ('status', 'applied_at')
    search_fields = ('job__title', 'jobseeker__user__email')
    list_select_related = ('job', 'jobseeker__user')


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin[SavedJob]):
    list_display = ('job', 'jobseeker', 'saved_at')
    search_fields = ('job__title', 'jobseeker__user__email')
    list_select_related = ('job', 'jobseeker__user')
