from django.contrib import admin

from server.apps.company.models import (
    Benefit,
    Company,
    Industry,
    StudentProgram,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin[Company]):
    list_display = (
        'id',
        'name',
        'recruiter',
        'industry',
        'size',
    )
    search_fields = ('name', 'recruiter__user__email')
    list_filter = ('industry', 'size')
    filter_horizontal = ('benefits',)


@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin[Industry]):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Benefit)
class BenefitAdmin(admin.ModelAdmin[Benefit]):
    list_display = ('id', 'name', 'icon_class')
    search_fields = ('name',)


@admin.register(StudentProgram)
class StudentProgramAdmin(admin.ModelAdmin[StudentProgram]):
    list_display = ('title', 'company', 'status')
    list_filter = ('status',)
    raw_id_fields = ('company',)
