from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, QuerySet, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from server.apps.company.models import Company
from server.apps.company.services import CompanyService
from server.apps.job_sync import const
from server.apps.job_sync.models import (
    ExternalJob,
    ExternalJobStatusEnum,
    ExternalSource,
    SyncStatusEnum,
)
from server.apps.job_sync.parsers.registry import get_source_type_from_url
from server.apps.job_sync.tasks import sync_external_jobs
from server.common.types import HtmxRequest

SUPPORTED_DOMAINS_HELP = 'Supported: praca.by, career.habr.com'


def _annotate_sources(
    queryset: QuerySet[ExternalSource],
) -> list[ExternalSource]:
    qs = queryset.annotate(
        total_count=Count('external_jobs'),
        synced_count=Count(
            'external_jobs',
            filter=Q(external_jobs__status=ExternalJobStatusEnum.SYNCED),
        ),
    )
    return list(qs)


def _get_sources(company: Company) -> list[ExternalSource]:
    return _annotate_sources(
        ExternalSource.objects.filter(
            company=company,
        ).order_by('source_type'),
    )


class ExternalSourceView(LoginRequiredMixin, View):
    def get(self, request: HtmxRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        context = {
            'company': company,
            'external_sources': _get_sources(company),
        }
        return render(request, const.EXTERNAL_SOURCE_FORM, context)

    def post(self, request: HtmxRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        external_url = request.POST.get('external_url', '').strip()

        if not external_url:
            context = {
                'company': company,
                'external_sources': _get_sources(company),
                'error': 'Please enter a URL',
            }
            return render(request, const.EXTERNAL_SOURCE_FORM, context)

        source_type = get_source_type_from_url(external_url)
        if source_type is None:
            context = {
                'company': company,
                'external_sources': _get_sources(company),
                'error': f'Unsupported URL. {SUPPORTED_DOMAINS_HELP}',
            }
            return render(request, const.EXTERNAL_SOURCE_FORM, context)

        ExternalSource.objects.update_or_create(
            company=company,
            source_type=source_type,
            defaults={'external_url': external_url.rstrip('/')},
        )

        context = {
            'company': company,
            'external_sources': _get_sources(company),
            'success': 'External source saved',
        }
        return render(request, const.EXTERNAL_SOURCE_FORM, context)


class SyncJobsView(LoginRequiredMixin, View):
    def post(
        self,
        request: HttpRequest,
        pk: int,
        source_id: int,
    ) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        external_source = get_object_or_404(
            ExternalSource,
            pk=source_id,
            company=company,
        )

        if external_source.sync_status == SyncStatusEnum.IN_PROGRESS:
            context = {
                'company': company,
                'external_source': external_source,
                'error': 'Sync is already in progress',
            }
            return render(request, const.SYNC_STATUS, context)

        external_source.sync_status = SyncStatusEnum.IN_PROGRESS
        external_source.save(update_fields=['sync_status', 'updated_at'])

        sync_external_jobs.enqueue(external_source.pk)

        context = {
            'company': company,
            'external_source': external_source,
        }
        return render(request, const.SYNC_STATUS, context)


class SyncStatusView(LoginRequiredMixin, View):
    def get(
        self,
        request: HttpRequest,
        pk: int,
        source_id: int,
    ) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        external_source = get_object_or_404(
            ExternalSource,
            pk=source_id,
            company=company,
        )

        jobs_qs = ExternalJob.objects.filter(
            external_source=external_source,
        )
        total_count = jobs_qs.count()
        synced_count = jobs_qs.filter(
            status=ExternalJobStatusEnum.SYNCED,
        ).count()

        context = {
            'company': company,
            'external_source': external_source,
            'synced_count': synced_count,
            'total_count': total_count,
        }
        return render(request, const.SYNC_STATUS, context)
