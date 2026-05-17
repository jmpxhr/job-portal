from django.contrib.auth.mixins import LoginRequiredMixin
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


class ExternalSourceView(LoginRequiredMixin, View):
    def get(self, request: HtmxRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        external_source = ExternalSource.objects.filter(
            company=company,
        ).first()

        context = {
            'company': company,
            'external_source': external_source,
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
            external_source = ExternalSource.objects.filter(
                company=company,
            ).first()
            context = {
                'company': company,
                'external_source': external_source,
                'error': 'Please enter a URL',
            }
            return render(request, const.EXTERNAL_SOURCE_FORM, context)

        source_type = get_source_type_from_url(external_url)
        if source_type is None:
            external_source = ExternalSource.objects.filter(
                company=company,
            ).first()
            context = {
                'company': company,
                'external_source': external_source,
                'error': 'Unsupported external resource URL',
            }
            return render(request, const.EXTERNAL_SOURCE_FORM, context)

        external_source = ExternalSource.objects.update_or_create(
            company=company,
            source_type=source_type,
            defaults={'external_url': external_url.rstrip('/')},
        )[0]

        context = {
            'company': company,
            'external_source': external_source,
            'success': 'External source saved',
        }
        return render(request, const.EXTERNAL_SOURCE_FORM, context)


class SyncJobsView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        if not CompanyService.can_edit(
            company,
            request.user,  # pyrefly: ignore
        ):
            return redirect('company:company-detail', pk=pk)

        external_source = get_object_or_404(
            ExternalSource,
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
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        company = get_object_or_404(Company, pk=pk)

        external_source = ExternalSource.objects.filter(
            company=company,
        ).first()

        synced_count = 0
        total_count = 0
        if external_source:
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
