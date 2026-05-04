from http import HTTPStatus
from typing import Any, override

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView

from server.apps.accounts.models import Education, Experience, JobSeeker, Language
from server.apps.dashboard.forms import (
    ChangePasswordForm,
    EducationForm,
    ExperienceForm,
    JobSeekerProfileForm,
    LanguageForm,
    PrivacySettingsForm,
    SkillAddForm,
)
from server.apps.jobs.models import Job, JobApplication, SavedJob, Skill
from server.common.types import (
    AuthenticatedHtmxRequest,
    AuthenticatedHttpRequest,
    HtmxRequest,
)


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


class CandidateProfileView(LoginRequiredMixin, View):
    template_name = 'dashboard/jobseeker/profile.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        base_qs = JobApplication.objects.filter(
            jobseeker=jobseeker,
            job__is_active=True,
        )
        context: dict[str, Any] = {
            'jobseeker': jobseeker,
            'total_applications': base_qs.count(),
            'saved_jobs_count': SavedJob.objects.filter(
                jobseeker=jobseeker,
                job__is_active=True,
            ).count(),
            'reviewed_count': base_qs.filter(
                status=JobApplication.StatusEnum.REVIEWED,
            ).count(),
            'accepted_count': base_qs.filter(
                status=JobApplication.StatusEnum.ACCEPTED,
            ).count(),
        }
        context.update(_education_list_context(jobseeker))
        context.update(_experience_list_context(jobseeker))
        context.update(_skill_list_context(jobseeker))
        context.update(_language_list_context(jobseeker))
        context['form'] = PrivacySettingsForm(instance=jobseeker)
        context['password_form'] = ChangePasswordForm(user=request.user)

        return render(request, self.template_name, context)


class EditProfileView(LoginRequiredMixin, View):
    form_template = 'dashboard/jobseeker/partials/edit-profile.html'
    overview_template = 'dashboard/jobseeker/partials/profile-overview.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        form = JobSeekerProfileForm(instance=jobseeker)
        context = {'form': form, 'jobseeker': jobseeker}
        return render(request, self.form_template, context)

    def post(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        form = JobSeekerProfileForm(
            request.POST,
            request.FILES,
            instance=jobseeker,
        )
        if form.is_valid():
            form.save()
            base_qs = JobApplication.objects.filter(
                jobseeker=jobseeker,
                job__is_active=True,
            )
            context = {
                'jobseeker': jobseeker,
                'total_applications': base_qs.count(),
                'saved_jobs_count': SavedJob.objects.filter(
                    jobseeker=jobseeker,
                    job__is_active=True,
                ).count(),
                'reviewed_count': base_qs.filter(
                    status=JobApplication.StatusEnum.REVIEWED,
                ).count(),
                'accepted_count': base_qs.filter(
                    status=JobApplication.StatusEnum.ACCEPTED,
                ).count(),
            }
            response = render(request, self.overview_template, context)
            response['HX-Trigger'] = 'profileSaved'
            return response

        context = {'form': form, 'jobseeker': jobseeker}
        return render(request, self.form_template, context)


def _education_list_context(jobseeker: JobSeeker) -> dict[str, Any]:
    return {
        'education_entries': Education.objects.filter(
            jobseeker=jobseeker,
        ).order_by('-year_of_graduation'),
    }


class EducationCreateView(LoginRequiredMixin, View):
    form_template = 'dashboard/jobseeker/partials/education-form.html'
    list_template = 'dashboard/jobseeker/partials/education-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        form = EducationForm()
        context = {'form': form}
        return render(request, self.form_template, context)

    def post(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        form = EducationForm(request.POST)
        if form.is_valid():
            education = form.save(commit=False)
            education.jobseeker = jobseeker
            education.save()
            context = _education_list_context(jobseeker)
            response = render(request, self.list_template, context)
            response['HX-Trigger'] = 'educationSaved'
            return response

        context = {'form': form}
        return render(request, self.form_template, context)


class EducationUpdateView(LoginRequiredMixin, View):
    form_template = 'dashboard/jobseeker/partials/education-form.html'
    list_template = 'dashboard/jobseeker/partials/education-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest, pk: int) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        education = get_object_or_404(Education, pk=pk, jobseeker=jobseeker)
        form = EducationForm(instance=education)
        context = {'form': form}
        return render(request, self.form_template, context)

    def post(self, request: AuthenticatedHtmxRequest, pk: int) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        education = get_object_or_404(Education, pk=pk, jobseeker=jobseeker)
        form = EducationForm(request.POST, instance=education)
        if form.is_valid():
            form.save()
            context = _education_list_context(jobseeker)
            response = render(request, self.list_template, context)
            response['HX-Trigger'] = 'educationSaved'
            return response

        context = {'form': form}
        return render(request, self.form_template, context)


class EducationDeleteView(LoginRequiredMixin, View):
    list_template = 'dashboard/jobseeker/partials/education-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def delete(
        self,
        request: AuthenticatedHtmxRequest,
        pk: int,
    ) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        education = get_object_or_404(Education, pk=pk, jobseeker=jobseeker)
        education.delete()
        context = _education_list_context(jobseeker)
        response = render(request, self.list_template, context)
        response['HX-Trigger'] = 'educationSaved'
        return response


def _experience_list_context(jobseeker: JobSeeker) -> dict[str, Any]:
    return {
        'experience_entries': Experience.objects.filter(
            jobseeker=jobseeker,
        ).order_by('-start_date'),
    }


class ExperienceCreateView(LoginRequiredMixin, View):
    form_template = 'dashboard/jobseeker/partials/experience-form.html'
    list_template = 'dashboard/jobseeker/partials/experience-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        form = ExperienceForm()
        context = {'form': form}
        return render(request, self.form_template, context)

    def post(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        form = ExperienceForm(request.POST)
        if form.is_valid():
            experience = form.save(commit=False)
            experience.jobseeker = jobseeker
            experience.save()
            context = _experience_list_context(jobseeker)
            response = render(request, self.list_template, context)
            response['HX-Trigger'] = 'experienceSaved'
            return response

        context = {'form': form}
        return render(request, self.form_template, context)


class ExperienceUpdateView(LoginRequiredMixin, View):
    form_template = 'dashboard/jobseeker/partials/experience-form.html'
    list_template = 'dashboard/jobseeker/partials/experience-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest, pk: int) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        experience = get_object_or_404(Experience, pk=pk, jobseeker=jobseeker)
        form = ExperienceForm(instance=experience)
        context = {'form': form}
        return render(request, self.form_template, context)

    def post(self, request: AuthenticatedHtmxRequest, pk: int) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        experience = get_object_or_404(Experience, pk=pk, jobseeker=jobseeker)
        form = ExperienceForm(request.POST, instance=experience)
        if form.is_valid():
            form.save()
            context = _experience_list_context(jobseeker)
            response = render(request, self.list_template, context)
            response['HX-Trigger'] = 'experienceSaved'
            return response

        context = {'form': form}
        return render(request, self.form_template, context)


class ExperienceDeleteView(LoginRequiredMixin, View):
    list_template = 'dashboard/jobseeker/partials/experience-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def delete(
        self,
        request: AuthenticatedHtmxRequest,
        pk: int,
    ) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        experience = get_object_or_404(Experience, pk=pk, jobseeker=jobseeker)
        experience.delete()
        context = _experience_list_context(jobseeker)
        response = render(request, self.list_template, context)
        response['HX-Trigger'] = 'experienceSaved'
        return response


def _skill_list_context(jobseeker: JobSeeker) -> dict[str, Any]:
    return {
        'skills': jobseeker.skills.all().order_by('name'),
    }


def _language_list_context(jobseeker: JobSeeker) -> dict[str, Any]:
    return {
        'language_entries': Language.objects.filter(
            jobseeker=jobseeker,
        ).order_by('name'),
    }


class LanguageCreateView(LoginRequiredMixin, View):
    form_template = 'dashboard/jobseeker/partials/language-form.html'
    list_template = 'dashboard/jobseeker/partials/language-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        form = LanguageForm()
        context = {'form': form}
        return render(request, self.form_template, context)

    def post(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        form = LanguageForm(request.POST)
        if form.is_valid():
            language = form.save(commit=False)
            language.jobseeker = jobseeker
            language.save()
            context = _language_list_context(jobseeker)
            response = render(request, self.list_template, context)
            response['HX-Trigger'] = 'languageSaved'
            return response

        context = {'form': form}
        return render(request, self.form_template, context)


class LanguageUpdateView(LoginRequiredMixin, View):
    form_template = 'dashboard/jobseeker/partials/language-form.html'
    list_template = 'dashboard/jobseeker/partials/language-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest, pk: int) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        language = get_object_or_404(Language, pk=pk, jobseeker=jobseeker)
        form = LanguageForm(instance=language)
        context = {'form': form}
        return render(request, self.form_template, context)

    def post(self, request: AuthenticatedHtmxRequest, pk: int) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        language = get_object_or_404(Language, pk=pk, jobseeker=jobseeker)
        form = LanguageForm(request.POST, instance=language)
        if form.is_valid():
            form.save()
            context = _language_list_context(jobseeker)
            response = render(request, self.list_template, context)
            response['HX-Trigger'] = 'languageSaved'
            return response

        context = {'form': form}
        return render(request, self.form_template, context)


class LanguageDeleteView(LoginRequiredMixin, View):
    list_template = 'dashboard/jobseeker/partials/language-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def delete(
        self,
        request: AuthenticatedHtmxRequest,
        pk: int,
    ) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        language = get_object_or_404(Language, pk=pk, jobseeker=jobseeker)
        language.delete()
        context = _language_list_context(jobseeker)
        response = render(request, self.list_template, context)
        response['HX-Trigger'] = 'languageSaved'
        return response


class SkillAddView(LoginRequiredMixin, View):
    form_template = 'dashboard/jobseeker/partials/skill-add.html'
    list_template = 'dashboard/jobseeker/partials/skill-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        form = SkillAddForm()
        context = {'form': form}
        return render(request, self.form_template, context)

    def post(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        form = SkillAddForm(request.POST)
        if form.is_valid():
            for skill_name in form.cleaned_data['names']:
                skill, _ = Skill.objects.get_or_create(
                    name=skill_name,
                    defaults={'slug': skill_name.lower().replace(' ', '-')},
                )
                jobseeker.skills.add(skill)
            context = _skill_list_context(jobseeker)
            response = render(request, self.list_template, context)
            response['HX-Trigger'] = 'skillSaved'
            return response

        context = {'form': form}
        return render(request, self.form_template, context)


class SkillRemoveView(LoginRequiredMixin, View):
    list_template = 'dashboard/jobseeker/partials/skill-list.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def delete(
        self,
        request: AuthenticatedHtmxRequest,
        pk: int,
    ) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        skill = get_object_or_404(Skill, pk=pk)
        jobseeker.skills.remove(skill)
        context = _skill_list_context(jobseeker)
        response = render(request, self.list_template, context)
        response['HX-Trigger'] = 'skillSaved'
        return response


class SkillSearchView(LoginRequiredMixin, View):
    def get(self, request: AuthenticatedHtmxRequest) -> JsonResponse:
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse([], safe=False)
        skills = (
            Skill.objects
            .filter(name__icontains=query)
            .values('id', 'name')
            .order_by('name')[:10]
        )
        return JsonResponse(list(skills), safe=False)


class PrivacySettingsView(LoginRequiredMixin, View):
    template_name = 'dashboard/jobseeker/partials/settings-privacy.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        form = PrivacySettingsForm(instance=jobseeker)
        context = {'form': form, 'jobseeker': jobseeker}
        return render(request, self.template_name, context)

    def post(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        form = PrivacySettingsForm(request.POST, instance=jobseeker)
        if form.is_valid():
            form.save()
            form = PrivacySettingsForm(instance=jobseeker)
            context = {'form': form, 'jobseeker': jobseeker, 'success': True}
            return render(request, self.template_name, context)

        context = {'form': form, 'jobseeker': jobseeker}
        return render(request, self.template_name, context)


class ChangePasswordView(LoginRequiredMixin, View):
    template_name = 'dashboard/jobseeker/partials/settings-password.html'

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        form = ChangePasswordForm(user=request.user)
        context = {'password_form': form}
        return render(request, self.template_name, context)

    def post(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        form = ChangePasswordForm(request.POST, user=request.user)
        if form.is_valid():
            request.user.set_password(form.cleaned_data['new_password'])
            request.user.save(update_fields=['password'])
            context = {
                'password_form': ChangePasswordForm(user=request.user),
                'success': True,
            }
            return render(request, self.template_name, context)

        context = {'password_form': form}
        return render(request, self.template_name, context)
