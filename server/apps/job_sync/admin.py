from django.contrib import admin

from server.apps.job_sync.models import ExternalJob, ExternalSource


@admin.register(ExternalSource)
class ExternalSourceAdmin(admin.ModelAdmin[ExternalSource]):
    list_display = (
        'company',
        'source_type',
        'external_url',
        'sync_status',
        'last_synced_at',
    )
    list_filter = ('source_type', 'sync_status')
    search_fields = ('company__name', 'external_url')
    raw_id_fields = ('company',)


@admin.register(ExternalJob)
class ExternalJobAdmin(admin.ModelAdmin[ExternalJob]):
    list_display = (
        'company',
        'external_id',
        'source_type',
        'status',
        'job',
        'created_at',
    )
    list_filter = ('source_type', 'status')
    search_fields = (
        'external_url',
        'external_id',
        'company__name',
    )
    raw_id_fields = ('company', 'job')
