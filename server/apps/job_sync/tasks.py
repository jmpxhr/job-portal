import logging

from django.tasks import task

from server.apps.job_sync.models import ExternalSource, SyncStatusEnum
from server.apps.job_sync.services import JobSyncService

logger = logging.getLogger('django')


@task
def sync_external_jobs(external_source_id: int) -> None:
    try:
        JobSyncService.sync_company_jobs(external_source_id)
    except Exception:
        logger.exception(
            'Failed to sync external jobs for source_id=%s',
            external_source_id,
        )
        try:
            source = ExternalSource.objects.get(pk=external_source_id)
            source.sync_status = SyncStatusEnum.FAILED
            source.error_message = 'Sync failed unexpectedly'
            source.save(
                update_fields=[
                    'sync_status',
                    'error_message',
                    'updated_at',
                ],
            )
        except Exception:
            logger.exception(
                'Failed to update sync status for source_id=%s',
                external_source_id,
            )
