from http import HTTPStatus
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView

from server.apps.accounts.models import JobSeeker
from server.apps.jobs.models import Job, SavedJob
from server.common.types import HtmxRequest


class HomePageView(TemplateView):
    template_name = 'dashboard/index.html'

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
    paginate_by = 10

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

    def delete(self, request: HtmxRequest, pk: int) -> HttpResponse:

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
