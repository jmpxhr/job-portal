from typing import Any, override

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import DetailView, ListView

from server.apps.accounts.models import JobSeeker, User
from server.apps.jobs import const, filters
from server.apps.jobs.models import Job, SavedJob
from server.common.types import AuthenticatedHttpRequest


class JobListView(ListView[Job]):
    model = Job
    template_name = const.JOBS_LIST
    context_object_name = 'jobs'
    paginate_by = 10

    @override
    def get_queryset(self) -> Any:
        queryset = (
            Job.objects
            .filter(is_active=True)
            .select_related('company')
            .prefetch_related('skills')
        )
        self.job_filter = filters.JobFilter(self.request.GET, queryset=queryset)
        return self.job_filter.qs

    @override
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['filter'] = self.job_filter
        context['employment_type_choices'] = Job.EmploymentTypeEnum.choices
        context['work_format_choices'] = Job.WorkFormatEnum.choices
        context['experience_level_choices'] = Job.ExperienceLevelEnum.choices
        context['sort_choices'] = [
            ('recent', 'Most recent'),
            ('salary_high', 'Salary: High to Low'),
            ('salary_low', 'Salary: Low to High'),
        ]
        context['current_sort'] = self.request.GET.get('sort', 'recent')
        context['current_salary_from'] = self.request.GET.get('salary_from', '')
        context['current_employment_types'] = self.request.GET.getlist(
            'employment_type',
        )
        context['current_work_formats'] = self.request.GET.getlist(
            'work_format',
        )
        context['current_experience_levels'] = self.request.GET.getlist(
            'experience_level',
        )
        context['search_query'] = self.request.GET.get('q', '')
        context['location_query'] = self.request.GET.get('location', '')
        return context

    @override
    def render_to_response(
        self,
        context: dict[str, Any],
        **response_kwargs: Any,
    ) -> HttpResponse:
        if getattr(self.request, 'htmx', False):
            return render(
                self.request,
                const.JOBS_LIST_PARTIAL,
                context,
            )
        return super().render_to_response(context, **response_kwargs)


class JobDetailView(DetailView[Job]):
    model = Job
    template_name = const.JOB_DETAIL
    context_object_name = 'job'

    @override
    def get_queryset(self) -> Any:
        return (
            Job.objects
            .filter(is_active=True)
            .select_related('company')
            .prefetch_related('skills')
        )

    @override
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        job = self.object
        similar_jobs = (
            Job.objects
            .filter(is_active=True)
            .exclude(pk=job.pk)
            .select_related('company')
            .prefetch_related('skills')
        )
        # Prioritize same shared skills
        similar_jobs = (
            similar_jobs
            .filter(
                Q(skills__in=job.skills.all()),
            )
            .annotate(
                similarity=Count('id', distinct=True),
            )
            .order_by('-similarity', '-posted_at')[:3]
        )
        context['similar_jobs'] = similar_jobs

        is_saved = False
        if (
            self.request.user.is_authenticated
            and self.request.user.account_type == User.AccountTypeEnum.JOBSEEKER  # pyrefly: ignore
        ):
            is_saved = SavedJob.objects.filter(
                job=job,
                jobseeker__user=self.request.user,
            ).exists()
        context['is_saved'] = is_saved
        return context


class SavedJobToggleView(LoginRequiredMixin, View):
    def post(self, request: AuthenticatedHttpRequest, pk: int) -> HttpResponse:
        job = get_object_or_404(Job, pk=pk, is_active=True)
        try:
            jobseeker = JobSeeker.objects.get(user=request.user)
        except JobSeeker.DoesNotExist:
            raise Http404 from None

        saved = SavedJob.objects.filter(job=job, jobseeker=jobseeker).first()
        if saved:
            saved.delete()
            is_saved = False
        else:
            SavedJob.objects.create(job=job, jobseeker=jobseeker)
            is_saved = True

        context = {
            'job': job,
            'is_saved': is_saved,
        }
        return render(
            request,
            'jobs/partials/save-button-partial.html',
            context,
        )
