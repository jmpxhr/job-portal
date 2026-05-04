from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from server.apps.accounts.forms import UserChangeForm, UserCreationForm
from server.apps.accounts.models import (
    Education,
    Experience,
    JobSeeker,
    Recruiter,
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin[User]):
    form = UserChangeForm
    add_form = UserCreationForm
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
    ordering = ('id',)
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'account_type',
                    'is_active',
                    'password1',
                    'password2',
                ),
            },
        ),
    )

    fieldsets = (
        ('Credentials', {'fields': ('email', 'password')}),
        (
            'Personal info',
            {'fields': ('first_name', 'last_name', 'account_type')},
        ),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                ),
            },
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )


@admin.register(JobSeeker)
class JobSeekerAdmin(admin.ModelAdmin[JobSeeker]):
    list_display = ('id', 'user')
    search_fields = ('user__email',)


@admin.register(Recruiter)
class RecruiterAdmin(admin.ModelAdmin[JobSeeker]):
    list_display = ('id', 'user')
    search_fields = ('user__email',)


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin[Education]):
    list_display = (
        'id',
        'jobseeker',
        'institution_name',
        'level',
        'year_of_graduation',
    )
    list_filter = ('level',)
    search_fields = ('institution_name', 'faculty', 'specialization')


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin[Experience]):
    list_display = (
        'id',
        'jobseeker',
        'position',
        'company_name',
        'start_date',
        'end_date',
    )
    list_filter = ('company_name',)
    search_fields = ('position', 'company_name')
