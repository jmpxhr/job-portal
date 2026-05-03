from typing import Any

from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic import DetailView, ListView

from server.apps.jobs import const, filters
from server.apps.jobs.models import Job


class JobListView(ListView):
    model = Job
    template_name = const.JOBS_LIST
    context_object_name = 'jobs'
    paginate_by = 10

    def get_queryset(self) -> Any:
        queryset = (
            Job.objects
            .filter(is_active=True)
            .select_related('company')
            .prefetch_related('skills')
        )
        self.job_filter = filters.JobFilter(self.request.GET, queryset=queryset)
        return self.job_filter.qs

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


class JobDetailView(DetailView):
    model = Job
    template_name = const.JOB_DETAIL
    context_object_name = 'job'

    def get_queryset(self) -> Any:
        return (
            Job.objects
            .filter(is_active=True)
            .select_related('company')
            .prefetch_related('skills')
        )

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
        return context
