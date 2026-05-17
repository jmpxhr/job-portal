from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from server.apps.job_sync.models import (
    ExternalJob,
    ExternalJobStatusEnum,
    ExternalSource,
    SyncStatusEnum,
)
from server.apps.job_sync.parsers.base import BaseParser, ParsedJobData
from server.apps.job_sync.parsers.registry import get_parser
from server.apps.jobs.models import Job, Skill

if TYPE_CHECKING:
    from server.apps.company.models import Company

logger = logging.getLogger('django')

_NULLISH = {None, ''}


class JobSyncService:
    @staticmethod
    def create_external_source(
        company_id: int,
        source_type: int,
        external_url: str,
    ) -> ExternalSource:
        external_url = external_url.rstrip('/')
        source, _ = ExternalSource.objects.update_or_create(
            company_id=company_id,
            source_type=source_type,
            defaults={'external_url': external_url},
        )
        return source

    @staticmethod
    def sync_company_jobs(external_source_id: int) -> None:
        source = _get_source_or_fail(external_source_id)

        source.sync_status = SyncStatusEnum.IN_PROGRESS
        source.error_message = ''
        source.save(
            update_fields=[
                'sync_status',
                'error_message',
                'updated_at',
            ],
        )

        parser = get_parser(source.source_type)
        if parser is None:
            msg = f'No parser for source type: {source.source_type}'
            raise ValueError(msg)

        job_urls = parser.fetch_listing(source.external_url)
        logger.info(
            'Found %d jobs for company %s from %s',
            len(job_urls),
            source.company.name,
            source.external_url,
        )
        results = _process_all_urls(source, parser, job_urls)
        _mark_sync_completed(source, results)


def _get_source_or_fail(source_id: int) -> ExternalSource:
    try:
        return ExternalSource.objects.select_related(
            'company',
        ).get(pk=source_id)
    except ExternalSource.DoesNotExist:
        msg = f'ExternalSource {source_id} not found'
        raise ValueError(msg) from None


def _process_all_urls(
    source: ExternalSource,
    parser: BaseParser,
    job_urls: list[str],
) -> dict[str, int]:
    synced = 0
    skipped = 0
    failed = 0

    for url in job_urls:
        try:
            result = _process_job_url(source, url, parser)
            if result == 'synced':
                synced += 1
            elif result == 'skipped':
                skipped += 1
            else:
                failed += 1
        except Exception:
            failed += 1
            logger.exception('Failed to process job URL: %s', url)

    return {'synced': synced, 'skipped': skipped, 'failed': failed}


def _mark_sync_completed(
    source: ExternalSource,
    results: dict[str, int],
) -> None:
    source.sync_status = SyncStatusEnum.COMPLETED
    source.last_synced_at = timezone.now()
    source.save(
        update_fields=[
            'sync_status',
            'last_synced_at',
            'updated_at',
        ],
    )
    logger.info(
        'Sync completed for %s: synced=%d, skipped=%d, failed=%d',
        source.company.name,
        results['synced'],
        results['skipped'],
        results['failed'],
    )


def _process_job_url(
    source: ExternalSource,
    url: str,
    parser: BaseParser,
) -> str:
    url = url.rstrip('/')

    existing = ExternalJob.objects.filter(external_url=url).first()
    if existing and existing.status in {
        ExternalJobStatusEnum.SYNCED,
        ExternalJobStatusEnum.PENDING,
    }:
        return 'skipped'

    parsed = parser.parse_job_detail(url)
    if not parsed.title:
        if existing:
            existing.status = ExternalJobStatusEnum.FAILED
            existing.error_message = 'No title found'
            existing.save(
                update_fields=[
                    'status',
                    'error_message',
                    'updated_at',
                ],
            )
        return 'failed'

    job = _create_job_from_parsed(company=source.company, parsed=parsed)

    external_id = parsed.external_id or url.rstrip('/').split('/')[-1]
    ExternalJob.objects.update_or_create(
        external_url=url,
        defaults={
            'company': source.company,
            'external_source': source,
            'source_type': source.source_type,
            'external_id': external_id,
            'job': job,
            'raw_data': parsed.raw_data,
            'status': ExternalJobStatusEnum.SYNCED,
            'error_message': '',
        },
    )

    return 'synced'


def _build_job_defaults(parsed: ParsedJobData) -> dict[str, object]:
    defaults: dict[str, object] = {
        'title': parsed.title,
        'description': parsed.description or '',
    }
    optional_int_fields = [
        'salary_min',
        'salary_max',
        'experience_level',
        'work_format',
        'schedule',
        'employment_type',
    ]
    for field in optional_int_fields:
        val = getattr(parsed, field)
        if val is not None:
            defaults[field] = val
    if parsed.location not in _NULLISH:
        defaults['location'] = parsed.location
    return defaults


@transaction.atomic
def _create_job_from_parsed(
    company: Company,
    parsed: ParsedJobData,
) -> Job:
    defaults = _build_job_defaults(parsed)

    existing_job = (
        ExternalJob.objects
        .filter(
            external_url=parsed.external_url,
            status=ExternalJobStatusEnum.SYNCED,
        )
        .select_related('job')
        .first()
    )

    if existing_job and existing_job.job:
        job = existing_job.job
        for key, value in defaults.items():
            if value not in _NULLISH:
                setattr(job, key, value)
        job.save()
    else:
        job = Job.objects.create(company=company, **defaults)

    if parsed.skills:
        _sync_skills(job, parsed.skills)

    return job


def _sync_skills(job: Job, skill_names: list[str]) -> None:
    skill_objects: list[Skill] = []
    for skill_name in skill_names:
        skill, _ = Skill.objects.get_or_create(
            name__iexact=skill_name,
            defaults={'name': skill_name},
        )
        skill_objects.append(skill)
    job.skills.set(skill_objects)
