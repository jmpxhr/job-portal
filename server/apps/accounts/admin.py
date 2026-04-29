from django.contrib import admin

from server.apps.accounts.models import (
    JobSeeker,
    Recruiter,
    User,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin[User]):
    list_display = (
        'id',
        'email',
        'first_name',
        'last_name',
        'account_type',
        'is_active',
        'date_joined',
    )
    list_filter = ('is_active', 'account_type')
    search_fields = ('email', 'first_name', 'last_name')


@admin.register(JobSeeker)
class JobSeekerAdmin(admin.ModelAdmin[JobSeeker]):
    list_display = ('id', 'user')
    search_fields = ('user__email',)


@admin.register(Recruiter)
class RecruiterAdmin(admin.ModelAdmin[JobSeeker]):
    list_display = ('id', 'user')
    search_fields = ('user__email',)
