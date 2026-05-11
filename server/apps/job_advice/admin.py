from django.contrib import admin

from server.apps.job_advice.models import JobAdvice


@admin.register(JobAdvice)
class JobAdviceAdmin(admin.ModelAdmin[JobAdvice]):
    list_display = ('id', 'jobseeker', 'job', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('jobseeker__user__email', 'job__title')
    list_select_related = ('jobseeker__user', 'job')
    readonly_fields = ('created_at', 'updated_at')
