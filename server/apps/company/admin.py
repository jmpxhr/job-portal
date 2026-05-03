from django.contrib import admin

from server.apps.company.models import Company, Industry

# Register your models here.


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin[Company]):
    list_display = ('id', 'name', 'recruiter')
    search_fields = ('name', 'recruiter__user__email')


@admin.register(Industry)
class IndustryAdmin(admin.ModelAdmin[Industry]):
    list_display = ('id', 'name')
    search_fields = ('name',)
