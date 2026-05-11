from typing import Any, override

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import (
    Case,
    Count,
    F,
    IntegerField,
    Q,
    QuerySet,
    Value,
    When,
)
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView, ListView

from server.apps.accounts.models import JobSeeker, User
from server.apps.jobs import const, filters, services
from server.apps.jobs.forms import JobApplicationForm
from server.apps.jobs.models import Job, JobApplication, SavedJob
from server.common.types import AuthenticatedHttpRequest, HtmxRequest


class JobListView(ListView[Job]):
    model = Job
    template_name = const.JOBS_LIST
    context_object_name = 'jobs'
    paginate_by = 10
    request: HtmxRequest  # pyrefly: ignore

    @override
    def get_queryset(self) -> QuerySet[Job]:  # noqa: C901
        queryset = Job.objects.filter(is_active=True).select_related('company')

        self.is_jobseeker = False
        user = self.request.user

        if (
            user.is_authenticated
            and hasattr(user, 'account_type')
            and user.account_type == User.AccountTypeEnum.JOBSEEKER
        ):
            try:
                jobseeker = JobSeeker.objects.get(user=user)
                skill_ids = list(jobseeker.skills.values_list('id', flat=True))
                self.is_jobseeker = True

                if skill_ids:
                    queryset = queryset.annotate(
                        total_skills=Count('skills', distinct=True),
                        matching_skills=Count(
                            'skills',
                            filter=Q(skills__in=skill_ids),
                            distinct=True,
                        ),
                    ).annotate(
                        match_score=Case(
                            When(total_skills=0, then=Value(0)),
                            default=F('matching_skills')
                            * 100
                            / F('total_skills'),
                            output_field=IntegerField(),
                        ),
                    )
                else:
                    queryset = queryset.annotate(
                        match_score=Value(0, output_field=IntegerField()),
                    )
            except JobSeeker.DoesNotExist:
                pass

        self.job_filter = filters.JobFilter(self.request.GET, queryset=queryset)
        qs = self.job_filter.qs

        if self.is_jobseeker:
            min_match = self.request.GET.get('match_score')
            if min_match:
                try:
                    min_match_int = int(min_match)
                    if min_match_int > 0:
                        qs = qs.filter(match_score__gte=min_match_int)
                except (ValueError, TypeError):
                    pass

        return qs.prefetch_related('skills')

    @override
    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['filter'] = self.job_filter
        context['employment_type_choices'] = Job.EmploymentTypeEnum.choices
        context['work_format_choices'] = Job.WorkFormatEnum.choices
        context['experience_level_choices'] = Job.ExperienceLevelEnum.choices
        sort_choices = [
            ('recent', _('Most recent')),
            ('salary_high', _('Salary: High to Low')),
            ('salary_low', _('Salary: Low to High')),
        ]
        if self.is_jobseeker:
            sort_choices.append(('match_score', _('Best Match')))
        context['sort_choices'] = sort_choices
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
        context['current_company'] = self.request.GET.get('company', '')
        context['is_jobseeker'] = self.is_jobseeker
        context['current_match_score'] = self.request.GET.get('match_score', '')
        return context

    @override
    def render_to_response(
        self,
        context: dict[str, Any],
        **response_kwargs: Any,
    ) -> HttpResponse:
        if self.request.htmx:
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
    def get(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        self.object = self.get_object()
        services.record_job_view(self.object, request)
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

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
        has_applied = False
        has_resume = False
        apply_form = None

        if (
            self.request.user.is_authenticated
            and self.request.user.account_type == User.AccountTypeEnum.JOBSEEKER  # pyrefly: ignore
        ):
            try:
                jobseeker = JobSeeker.objects.get(user=self.request.user)
                is_saved = SavedJob.objects.filter(
                    job=job,
                    jobseeker=jobseeker,
                ).exists()
                has_applied = JobApplication.objects.filter(
                    job=job,
                    jobseeker=jobseeker,
                ).exists()
                has_resume = bool(jobseeker.resume_objective)
                if not has_applied:
                    apply_form = JobApplicationForm()
            except JobSeeker.DoesNotExist:
                pass

        context['is_saved'] = is_saved
        context['has_applied'] = has_applied
        context['has_resume'] = has_resume
        context['apply_form'] = apply_form
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


class ApplyForJobView(LoginRequiredMixin, View):
    def post(self, request: AuthenticatedHttpRequest, pk: int) -> HttpResponse:
        job = get_object_or_404(Job, pk=pk, is_active=True)
        try:
            jobseeker = JobSeeker.objects.get(user=request.user)
        except JobSeeker.DoesNotExist:
            raise Http404 from None

        if JobApplication.objects.filter(job=job, jobseeker=jobseeker).exists():
            context = {'job': job, 'has_applied': True}
            return render(
                request,
                const.JOB_APPLY_SUCCESS_PARTIAL,
                context,
            )

        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            cover_letter = form.cleaned_data['cover_letter']
            resume_file = form.cleaned_data.get('resume_file')

            application = JobApplication(
                job=job,
                jobseeker=jobseeker,
                cover_letter=cover_letter,
            )
            if resume_file:
                application.resume = resume_file
                application.save()
                resume_file.seek(0)
            else:
                application.save()

            context = {'job': job, 'has_applied': True}
            return render(
                request,
                const.JOB_APPLY_SUCCESS_PARTIAL,
                context,
            )

        context = {
            'job': job,
            'form': form,
            'has_applied': False,
            'has_resume': bool(jobseeker.resume_objective),
        }
        return render(
            request,
            const.JOB_APPLY_FORM_PARTIAL,
            context,
        )
