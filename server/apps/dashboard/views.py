from http import HTTPStatus
from typing import Any, override

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView

from server.apps.accounts.models import JobSeeker
from server.apps.jobs.models import Job, JobApplication, SavedJob
from server.common.types import AuthenticatedHttpRequest, HtmxRequest


class HomePageView(TemplateView):
    template_name = 'dashboard/index.html'

    @override
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['latest_jobs'] = (
            Job.objects
            .filter(is_active=True)
            .select_related('company')
            .prefetch_related('skills')
            .order_by('-posted_at')[:3]
        )
        return context


class SavedJobsView(LoginRequiredMixin, View):
    template_name = 'dashboard/jobseeker/saved-jobs.html'
    paginate_by = 5

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get_queryset(self, jobseeker: JobSeeker) -> QuerySet[SavedJob]:
        sort = self.request.GET.get('sort', 'recent')
        order_map: dict[str, str] = {
            'recent': '-saved_at',
            'oldest': 'saved_at',
            'salary_high': '-job__salary_max',
            'salary_low': 'job__salary_min',
        }
        order_by = order_map.get(sort, '-saved_at')
        return (
            SavedJob.objects
            .filter(jobseeker=jobseeker, job__is_active=True)
            .select_related('job', 'job__company')
            .prefetch_related('job__skills')
            .order_by(order_by)
        )

    def get(self, request: HtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        queryset = self.get_queryset(jobseeker)

        paginator = Paginator(queryset, self.paginate_by)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        total_saved = paginator.count

        context = {
            'page_obj': page_obj,
            'saved_jobs': page_obj,
            'total_saved': total_saved,
            'current_sort': request.GET.get('sort', 'recent'),
            'sort_choices': [
                ('recent', 'Recently Saved'),
                ('oldest', 'Oldest First'),
                ('salary_high', 'Salary: High to Low'),
                ('salary_low', 'Salary: Low to High'),
            ],
        }

        if request.htmx:
            return render(
                request,
                self.template_name + '#job_cards',
                context,
            )

        return render(request, self.template_name, context)

    def delete(
        self,
        request: AuthenticatedHttpRequest,
        pk: int,
    ) -> HttpResponse:
        try:
            jobseeker = JobSeeker.objects.get(user=request.user)
        except JobSeeker.DoesNotExist:
            raise Http404 from None

        saved_job = get_object_or_404(
            SavedJob,
            pk=pk,
            jobseeker=jobseeker,
        )
        saved_job.delete()

        return HttpResponse(status=HTTPStatus.OK)


class MyApplicationsView(LoginRequiredMixin, View):
    template_name = 'dashboard/jobseeker/my-applications.html'
    paginate_by = 5

    STATUS_CHOICES: list[tuple[str, str]] = [
        ('', 'All Applications'),
        ('pending', 'Pending'),
        ('reviewed', 'In Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    STATUS_FILTER_MAP: dict[str, int] = {
        'pending': JobApplication.StatusEnum.PENDING,
        'reviewed': JobApplication.StatusEnum.REVIEWED,
        'accepted': JobApplication.StatusEnum.ACCEPTED,
        'rejected': JobApplication.StatusEnum.REJECTED,
    }

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get_queryset(
        self,
        jobseeker: JobSeeker,
        status_filter: str,
    ) -> QuerySet[JobApplication]:
        qs = (
            JobApplication.objects
            .filter(jobseeker=jobseeker, job__is_active=True)
            .select_related('job', 'job__company')
            .prefetch_related('job__skills')
            .order_by('-applied_at')
        )
        if status_filter in self.STATUS_FILTER_MAP:
            qs = qs.filter(status=self.STATUS_FILTER_MAP[status_filter])
        return qs

    def get(self, request: HtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        status_filter = request.GET.get('status', '')
        queryset = self.get_queryset(jobseeker, status_filter)

        paginator = Paginator(queryset, self.paginate_by)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        base_qs = JobApplication.objects.filter(
            jobseeker=jobseeker,
            job__is_active=True,
        )
        total_applications = base_qs.count()
        pending_count = base_qs.filter(
            status=JobApplication.StatusEnum.PENDING,
        ).count()
        reviewed_count = base_qs.filter(
            status=JobApplication.StatusEnum.REVIEWED,
        ).count()
        accepted_count = base_qs.filter(
            status=JobApplication.StatusEnum.ACCEPTED,
        ).count()
        rejected_count = base_qs.filter(
            status=JobApplication.StatusEnum.REJECTED,
        ).count()

        context = {
            'page_obj': page_obj,
            'applications': page_obj,
            'total_applications': total_applications,
            'pending_count': pending_count,
            'reviewed_count': reviewed_count,
            'accepted_count': accepted_count,
            'rejected_count': rejected_count,
            'current_status': status_filter,
            'status_choices': self.STATUS_CHOICES,
        }

        if request.htmx:
            return render(
                request,
                self.template_name + '#application_list',
                context,
            )

        return render(request, self.template_name, context)


class ApplicationDetailView(LoginRequiredMixin, View):
    template_name = 'dashboard/jobseeker/partials/application-detail-modal.html'

    def get(self, request: AuthenticatedHttpRequest, pk: int) -> HttpResponse:
        try:
            jobseeker = JobSeeker.objects.get(user=request.user)
        except JobSeeker.DoesNotExist:
            raise Http404 from None

        application = get_object_or_404(
            JobApplication.objects.select_related(
                'job',
                'job__company',
            ).prefetch_related('job__skills'),
            pk=pk,
            jobseeker=jobseeker,
        )

        context = {
            'application': application,
        }
        return render(request, self.template_name, context)
