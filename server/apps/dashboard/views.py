import contextlib
from http import HTTPStatus
from typing import Any, override

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q, QuerySet, Sum
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView
from weasyprint import HTML

from server.apps.accounts.models import (
    Education,
    Experience,
    JobSeeker,
    Language,
    Recruiter,
    User,
)
from server.apps.company.models import Company
from server.apps.dashboard import const
from server.apps.dashboard.forms import (
    ChangePasswordForm,
    EducationForm,
    ExperienceForm,
    JobPostForm,
    JobSeekerProfileForm,
    LanguageForm,
    PrivacySettingsForm,
    ResumeForm,
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
        context.update(_resume_context(jobseeker))
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


def _resume_context(jobseeker: JobSeeker) -> dict[str, Any]:
    return {
        'education_entries': Education.objects.filter(
            jobseeker=jobseeker,
        ).order_by('-year_of_graduation'),
        'experience_entries': Experience.objects.filter(
            jobseeker=jobseeker,
        ).order_by('-start_date'),
        'skills': jobseeker.skills.all().order_by('name'),
        'language_entries': Language.objects.filter(
            jobseeker=jobseeker,
        ).order_by('name'),
    }


class ResumeEditView(LoginRequiredMixin, View):
    form_template = 'dashboard/jobseeker/partials/resume-form.html'
    content_template = 'dashboard/jobseeker/partials/resume-content.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        form = ResumeForm(instance=jobseeker)
        context = {'form': form, 'jobseeker': jobseeker}
        return render(request, self.form_template, context)

    def post(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        clear_file = request.POST.get('clear_resume_file') == '1'
        form = ResumeForm(request.POST, request.FILES, instance=jobseeker)
        if form.is_valid():
            if clear_file and jobseeker.resume_file:
                jobseeker.resume_file.delete(save=False)
            form.save()
            context = {'jobseeker': jobseeker}
            context.update(_resume_context(jobseeker))
            response = render(request, self.content_template, context)
            response['HX-Trigger'] = 'resumeSaved'
            return response

        return render(
            request,
            self.form_template,
            {
                'form': form,
                'jobseeker': jobseeker,
            },
        )


class ResumePDFView(LoginRequiredMixin, View):
    template_name = 'dashboard/jobseeker/resume-pdf.html'

    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        context: dict[str, Any] = {
            'jobseeker': jobseeker,
        }
        context.update(_resume_context(jobseeker))
        html_string = render(
            request,
            self.template_name,
            context,
        ).content.decode('utf-8')
        pdf_file = HTML(string=html_string).write_pdf()
        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename = (
            f'{jobseeker.user.get_full_name().replace(" ", "_")}_Resume.pdf'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class ResumeFileDownloadView(LoginRequiredMixin, View):
    def get_jobseeker(self, user: Any) -> JobSeeker:
        return get_object_or_404(JobSeeker, user=user)

    def get(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        jobseeker = self.get_jobseeker(request.user)
        if not jobseeker.resume_file:
            raise Http404
        response = HttpResponse(
            jobseeker.resume_file.open('rb').read(),
            content_type='application/octet-stream',
        )
        response['Content-Disposition'] = (
            'attachment; '
            + f'filename="{jobseeker.resume_file.name.split("/")[-1]}"'  # type: ignore[union-attr]
        )
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
                skill = Skill.objects.filter(name__iexact=skill_name).first()
                if skill is None:
                    skill = Skill.objects.create(
                        name=skill_name,
                        slug=skill_name.lower().replace(' ', '-'),
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


class EmployerDashboardView(LoginRequiredMixin, View):
    template_name = 'dashboard/company/employer-dashboard.html'

    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    def get(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        company = self.get_company(request.user)
        if not company:
            raise Http404
        context = {'company': company}
        return render(request, self.template_name, context)


class PostVacancyView(LoginRequiredMixin, View):
    template_name = const.POST_VACANCY

    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    def get(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        company = self.get_company(request.user)
        if not company:
            raise Http404
        form = JobPostForm()
        context = {'form': form, 'company': company}
        return render(request, self.template_name, context)

    def post(self, request: AuthenticatedHttpRequest) -> HttpResponse:
        company = self.get_company(request.user)
        if not company:
            raise Http404
        form = JobPostForm(request.POST)
        is_draft = 'save_draft' in request.POST
        if form.is_valid():
            form.save(company=company, is_draft=is_draft)
            return redirect('dashboard:employer-dashboard')
        context = {'form': form, 'company': company}
        return render(request, self.template_name, context)


class EditVacancyView(LoginRequiredMixin, View):
    template_name = const.EDIT_VACANCY

    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    def get(self, request: AuthenticatedHttpRequest, pk: int) -> HttpResponse:
        company = self.get_company(request.user)
        if not company:
            raise Http404
        job = get_object_or_404(Job, pk=pk, company=company)
        form = JobPostForm(instance=job)
        context = {'form': form, 'company': company, 'job': job}
        return render(request, self.template_name, context)

    def post(
        self,
        request: AuthenticatedHttpRequest,
        pk: int,
    ) -> HttpResponse | HttpResponseRedirect:
        company = self.get_company(request.user)
        if not company:
            raise Http404
        job = get_object_or_404(Job, pk=pk, company=company)

        if 'delete' in request.POST:
            job.delete()
            return redirect('dashboard:post-vacancy')

        action = request.POST.get('action', 'publish')
        is_draft = action == 'save_draft'
        job_status = request.POST.get('job_status', 'active')
        if job_status == 'draft':
            is_draft = True

        form = JobPostForm(request.POST, instance=job)
        if form.is_valid():
            job = form.save(company=company, is_draft=is_draft)
            form = JobPostForm(instance=job)
            context = {
                'form': form,
                'company': company,
                'job': job,
                'success': True,
            }
            return render(request, self.template_name, context)
        context = {'form': form, 'company': company, 'job': job}
        return render(request, self.template_name, context)


class ManageVacanciesView(LoginRequiredMixin, View):
    template_name = const.MANAGE_VACANCIES
    paginate_by = 5

    STATUS_CHOICES: list[tuple[str, str]] = [
        ('', 'All Statuses'),
        ('active', 'Active'),
        ('draft', 'Draft'),
    ]

    EMPLOYMENT_TYPE_CHOICES: list[tuple[str, str]] = [
        ('', 'All Types'),
        ('0', 'Full-time'),
        ('1', 'Part-time'),
        ('2', 'Internship'),
    ]

    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    def get_queryset(self, company: Company) -> QuerySet[Job]:
        return (
            Job.objects
            .filter(company=company)
            .annotate(applications_count=Count('applications'))
            .order_by('-posted_at')
        )

    def apply_filters(
        self,
        qs: QuerySet[Job],
        status: str,
        employment_type: str,
        q: str,
    ) -> QuerySet[Job]:
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'draft':
            qs = qs.filter(is_active=False)

        if employment_type:
            with contextlib.suppress(ValueError):
                qs = qs.filter(employment_type=int(employment_type))

        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(description__icontains=q),
            )

        return qs

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:
        company = self.get_company(request.user)
        if not company:
            raise Http404

        status_filter = request.GET.get('status', '')
        employment_type_filter = request.GET.get('employment_type', '')
        q_filter = request.GET.get('q', '').strip()

        base_qs = (
            Job.objects
            .filter(company=company)
            .annotate(applications_count=Count('applications'))
        )

        active_count = base_qs.filter(is_active=True).count()
        draft_count = base_qs.filter(is_active=False).count()
        total_applicants_result = base_qs.aggregate(
            total=Sum('applications_count'),
        )
        total_applicants = total_applicants_result['total'] or 0

        filtered_qs = self.apply_filters(
            base_qs,
            status_filter,
            employment_type_filter,
            q_filter,
        )

        paginator = Paginator(filtered_qs, self.paginate_by)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'company': company,
            'stats': {
                'active_count': active_count,
                'draft_count': draft_count,
                'total_applicants': total_applicants,
            },
            'current_status': status_filter,
            'current_employment_type': employment_type_filter,
            'current_q': q_filter,
            'status_choices': self.STATUS_CHOICES,
            'employment_type_choices': self.EMPLOYMENT_TYPE_CHOICES,
        }

        if request.htmx:
            return render(
                request,
                self.template_name + '#vacancy_list',
                context,
            )

        return render(request, self.template_name, context)


class ToggleVacancyStatusView(LoginRequiredMixin, View):
    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    def post(
        self,
        request: AuthenticatedHttpRequest,
        pk: int,
    ) -> HttpResponseRedirect:
        company = self.get_company(request.user)
        if not company:
            raise Http404

        job = get_object_or_404(Job, pk=pk, company=company)
        job.is_active = not job.is_active
        job.save(update_fields=['is_active'])

        return redirect('dashboard:manage-vacancies')
