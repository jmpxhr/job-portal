import contextlib
import json
from datetime import date, timedelta
from http import HTTPStatus
from logging import getLogger
from typing import Any, override

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import (
    Case,
    Count,
    IntegerField,
    Q,
    QuerySet,
    Sum,
    Value,
    When,
)
from django.db.models.functions import TruncDay
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView
from weasyprint import HTML

from server.apps.accounts.filters import JobSeekerFilter
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
from server.apps.skill_tests.models import SkillVerification
from server.common.types import (
    AuthenticatedHtmxRequest,
    AuthenticatedHttpRequest,
    HtmxRequest,
)

logger = getLogger('django')


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
        context['active_jobs_count'] = Job.objects.filter(
            is_active=True,
        ).count()
        context['companies_count'] = Company.objects.count()
        context['students_count'] = JobSeeker.objects.count()
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
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    STATUS_FILTER_MAP: dict[str, int] = {
        'pending': JobApplication.StatusEnum.PENDING,
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

    verifications = SkillVerification.objects.filter(
        jobseeker=jobseeker,
    ).select_related('skill')
    return {
        'skills': jobseeker.skills.all().order_by('name'),
        'skill_verifications': verifications,
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
        form = ResumeForm(request.POST, instance=jobseeker)
        if form.is_valid():
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


class CandidateResumePDFView(LoginRequiredMixin, View):
    template_name = 'dashboard/jobseeker/resume-pdf.html'

    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    def get(
        self,
        request: AuthenticatedHttpRequest,
        pk: int,
    ) -> HttpResponse:
        company = self.get_company(request.user)
        if not company:
            raise Http404

        jobseeker = get_object_or_404(
            JobSeeker.objects.select_related('user'),
            pk=pk,
        )

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

        now = timezone.now()
        week_ago = now - timedelta(days=7)

        active_jobs_count = company.jobs.filter(is_active=True).count()  # pyrefly: ignore

        base_app_qs = JobApplication.objects.filter(job__company=company)
        total_applicants = base_app_qs.count()
        new_applicants_count = base_app_qs.filter(
            applied_at__gte=week_ago,
        ).count()
        pending_applicants_count = base_app_qs.filter(
            status=JobApplication.StatusEnum.PENDING,
        ).count()

        recent_applications = base_app_qs.select_related(
            'jobseeker__user',
            'job',
        ).order_by('-applied_at')[:5]

        thirty_days_ago = now - timedelta(days=30)
        trends_qs = (
            base_app_qs
            .filter(applied_at__gte=thirty_days_ago)
            .annotate(day=TruncDay('applied_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        trend_days = {
            entry['day'].date(): entry['count'] for entry in trends_qs
        }
        trend_labels = []
        trend_data = []
        current = thirty_days_ago.date()
        end = now.date()
        while current <= end:
            trend_labels.append(current.strftime('%b %d'))
            trend_data.append(trend_days.get(current, 0))
            current += timedelta(days=1)
        application_trends_labels = json.dumps(trend_labels)
        application_trends_data = json.dumps(trend_data)

        emp_type_labels_map = {
            k: str(v) for k, v in Job.EmploymentTypeEnum.choices
        }
        category_qs = (
            company.jobs  # pyrefly: ignore
            .filter(is_active=True)
            .values('employment_type')
            .annotate(count=Count('id'))
            .order_by('employment_type')
        )
        jobs_by_category_labels = json.dumps([
            emp_type_labels_map.get(entry['employment_type'], 'Other')
            for entry in category_qs
        ])
        jobs_by_category_data = json.dumps([
            entry['count'] for entry in category_qs
        ])

        skills_qs = (
            Skill.objects
            .filter(jobs__company=company, jobs__is_active=True)
            .values('name')
            .annotate(count=Count('jobs'))
            .order_by('-count')[:10]
        )
        jobs_by_skill_labels = json.dumps([
            entry['name']  # type: ignore[index]
            for entry in skills_qs
        ])
        jobs_by_skill_data = json.dumps([entry['count'] for entry in skills_qs])  # type: ignore[index]

        job_views_count = (
            company.jobs.aggregate(  # pyrefly: ignore
                total=Sum('views_count'),
            )['total']
            or 0
        )

        context = {
            'company': company,
            'active_jobs_count': active_jobs_count,
            'total_applicants': total_applicants,
            'new_applicants_count': new_applicants_count,
            'pending_applicants_count': pending_applicants_count,
            'job_views_count': job_views_count,
            'recent_applications': recent_applications,
            'application_trends_labels': application_trends_labels,
            'application_trends_data': application_trends_data,
            'jobs_by_category_labels': jobs_by_category_labels,
            'jobs_by_category_data': jobs_by_category_data,
            'jobs_by_skill_labels': jobs_by_skill_labels,
            'jobs_by_skill_data': jobs_by_skill_data,
        }
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

        base_qs = Job.objects.filter(company=company).annotate(
            applications_count=Count('applications'),
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


def _compute_match_score(jobseeker: JobSeeker, job: Job) -> int:
    job_skills = set(job.skills.values_list('id', flat=True))
    if not job_skills:
        return 0
    candidate_skills = set(jobseeker.skills.values_list('id', flat=True))
    matching = job_skills & candidate_skills
    return round((len(matching) / len(job_skills)) * 100)


class ApplicantsListView(LoginRequiredMixin, View):
    template_name = const.APPLICANTS_LIST
    paginate_by = 10

    STATUS_CHOICES: list[tuple[str, str]] = [
        ('', _('All')),
        ('0', _('New')),
        ('2', _('Accepted')),
        ('3', _('Rejected')),
    ]

    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    def get_queryset(self, company: Company) -> QuerySet[JobApplication]:
        return (
            JobApplication.objects
            .filter(job__company=company)
            .select_related('job', 'jobseeker', 'jobseeker__user')
            .prefetch_related('jobseeker__skills', 'job__skills')
            .order_by('-applied_at')
        )

    def get(self, request: AuthenticatedHtmxRequest) -> HttpResponse:  # noqa: C901
        company = self.get_company(request.user)
        if not company:
            raise Http404

        job_filter = request.GET.get('job_id', '').strip()
        status_filter = request.GET.get('status', '').strip()

        base_qs = (
            JobApplication.objects
            .filter(job__company=company)
            .select_related('job', 'jobseeker', 'jobseeker__user')
            .prefetch_related('jobseeker__skills', 'job__skills')
        )

        filtered_qs = base_qs
        if job_filter:
            with contextlib.suppress(ValueError):
                filtered_qs = filtered_qs.filter(job_id=int(job_filter))

        if status_filter:
            with contextlib.suppress(ValueError):
                filtered_qs = filtered_qs.filter(status=int(status_filter))

        filtered_qs = filtered_qs.order_by('-applied_at')

        total_count = filtered_qs.count()
        new_count = filtered_qs.filter(
            status=JobApplication.StatusEnum.PENDING,
        ).count()
        accepted_count = filtered_qs.filter(
            status=JobApplication.StatusEnum.ACCEPTED,
        ).count()
        rejected_count = filtered_qs.filter(
            status=JobApplication.StatusEnum.REJECTED,
        ).count()

        jobs_list = (
            Company.objects  # pyrefly: ignore
            .prefetch_related('jobs')
            .get(pk=company.pk)
            .jobs.annotate(applications_count=Count('applications'))
            .order_by('-posted_at')
        )

        paginator = Paginator(filtered_qs, self.paginate_by)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        match_score_cache: dict[int, int] = {}
        for app in page_obj:
            if app.job_id not in match_score_cache:
                match_score_cache[app.job_id] = _compute_match_score(
                    app.jobseeker,
                    app.job,
                )
            app.match_score = match_score_cache[app.job_id]  # type: ignore[attr-defined]

        context = {
            'page_obj': page_obj,
            'company': company,
            'stats': {
                'total': total_count,
                'new': new_count,
                'accepted': accepted_count,
                'rejected': rejected_count,
            },
            'jobs_list': jobs_list,
            'current_job': job_filter,
            'current_status': status_filter,
            'status_choices': self.STATUS_CHOICES,
        }

        if request.htmx:
            return render(
                request,
                self.template_name + '#applicant_list',
                context,
            )

        return render(request, self.template_name, context)


class UpdateApplicationStatusView(LoginRequiredMixin, View):
    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    def post(
        self,
        request: AuthenticatedHtmxRequest,
        pk: int,
    ) -> HttpResponse | HttpResponseRedirect:
        company = self.get_company(request.user)
        if not company:
            raise Http404

        application = get_object_or_404(
            JobApplication,
            pk=pk,
            job__company=company,
        )

        new_status = request.POST.get('status')
        if new_status is not None:
            try:
                status_value = int(new_status)
                if status_value in dict(JobApplication.StatusEnum.choices):
                    application.status = status_value
                    application.save(update_fields=['status'])
            except ValueError:
                pass

        if request.htmx:
            return HttpResponse(status=HTTPStatus.OK)

        return redirect('dashboard:applicants-list')


class UpdateApplicationFeedbackView(LoginRequiredMixin, View):
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

        application = get_object_or_404(
            JobApplication,
            pk=pk,
            job__company=company,
        )

        feedback = request.POST.get('employer_feedback', '')
        application.employer_feedback = feedback
        application.save(update_fields=['employer_feedback'])

        return redirect('dashboard:candidate-view', pk=pk)


class CandidateView(LoginRequiredMixin, View):
    template_name = const.CANDIDATE_VIEW

    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    def get(
        self,
        request: AuthenticatedHttpRequest,
        pk: int,
    ) -> HttpResponse:
        company = self.get_company(request.user)
        if not company:
            raise Http404

        application = get_object_or_404(
            JobApplication.objects.select_related(
                'job',
                'jobseeker',
                'jobseeker__user',
            ).prefetch_related(
                'jobseeker__skills',
                'job__skills',
                'jobseeker__education',
                'jobseeker__experience',
                'jobseeker__languages',
            ),
            pk=pk,
            job__company=company,
        )

        jobseeker = application.jobseeker
        job = application.job
        match_score = _compute_match_score(jobseeker, job)
        if match_score >= 70:
            skill_match_level = 'High'
        elif match_score >= 40:
            skill_match_level = 'Medium'
        else:
            skill_match_level = 'Low'

        education = jobseeker.education.all().order_by('-year_of_graduation')
        experience = jobseeker.experience.all().order_by('-start_date')
        languages = jobseeker.languages.all().order_by('name')
        skills = jobseeker.skills.all().order_by('name')

        skill_verifications = SkillVerification.objects.filter(
            jobseeker=jobseeker,
        ).select_related('skill')

        context = {
            'application': application,
            'jobseeker': jobseeker,
            'job': job,
            'match_score': match_score,
            'skill_match_level': skill_match_level,
            'education': education,
            'experience': experience,
            'languages': languages,
            'skills': skills,
            'skill_verifications': skill_verifications,
            'status_choices': JobApplication.StatusEnum.choices,
        }

        return render(request, self.template_name, context)


class BrowseCandidateProfileView(LoginRequiredMixin, View):
    template_name = const.BROWSE_CANDIDATE_PROFILE

    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    def get(
        self,
        request: AuthenticatedHttpRequest,
        pk: int,
    ) -> HttpResponse:
        company = self.get_company(request.user)
        if not company:
            raise Http404

        jobseeker = get_object_or_404(
            JobSeeker.objects.select_related('user').prefetch_related(
                'skills',
                'education',
                'experience',
                'languages',
            ),
            pk=pk,
            profile_visible=True,
        )

        match_score = 0
        skill_match_level = ''
        job = None

        job_id = request.GET.get('job_id', '')
        if job_id:
            try:
                job = Job.objects.get(pk=int(job_id), company=company)
                match_score = _compute_match_score(jobseeker, job)
                if match_score >= 70:
                    skill_match_level = 'High'
                elif match_score >= 40:
                    skill_match_level = 'Medium'
                else:
                    skill_match_level = 'Low'
            except (ValueError, Job.DoesNotExist):
                pass

        education = jobseeker.education.all().order_by('-year_of_graduation')  # pyrefly: ignore
        experience = jobseeker.experience.all().order_by('-start_date')  # pyrefly: ignore

        languages = jobseeker.languages.all().order_by('name')  # pyrefly: ignore

        skills = jobseeker.skills.all().order_by('name')

        skill_verifications = SkillVerification.objects.filter(
            jobseeker=jobseeker,
        ).select_related('skill')

        context = {
            'jobseeker': jobseeker,
            'job': job,
            'match_score': match_score,
            'skill_match_level': skill_match_level,
            'education': education,
            'experience': experience,
            'languages': languages,
            'skills': skills,
            'skill_verifications': skill_verifications,
            'company': company,
        }

        return render(request, self.template_name, context)


class BrowseCandidatesView(LoginRequiredMixin, View):
    template_name = const.BROWSE_CANDIDATES
    paginate_by = 12

    SORT_CHOICES: list[tuple[str, str]] = [
        ('recent', _('Most Recent')),
        ('name', _('Name (A-Z)')),
        ('match_score', _('Match Score')),
    ]

    EXPERIENCE_CHOICES: list[tuple[str, str]] = [
        ('0', _("Doesn't matter")),
        ('1', _('No experience')),
        ('2', _('From 1 year to 3 years')),
        ('3', _('From 3 to 6 years')),
        ('4', _('More than 6 years')),
    ]

    def get_company(self, user: User) -> Company | None:
        try:
            return user.recruiter.company  # pyrefly: ignore
        except (Recruiter.DoesNotExist, Company.DoesNotExist):
            return None

    EXP_RANGES: dict[str, tuple[float, float]] = {
        '2': (1.0, 3.0),
        '3': (3.0, 6.0),
        '4': (6.0, 9999.0),
    }

    def apply_experience_filter(
        self,
        qs: QuerySet[JobSeeker],
        experience_level: str,
    ) -> QuerySet[JobSeeker]:
        if not experience_level or experience_level == '0':
            return qs

        if experience_level == '1':
            return qs.filter(experience__isnull=True).distinct()

        if experience_level not in self.EXP_RANGES:
            return qs

        min_yr, max_yr = self.EXP_RANGES[experience_level]
        today = timezone.now().date()

        matching_ids: list[int] = []
        candidates = qs.filter(experience__isnull=False).distinct()
        for js in candidates:
            total_years = self._calc_total_years(js, today)
            if min_yr <= total_years < max_yr:
                matching_ids.append(js.pk)

        return qs.filter(pk__in=matching_ids)

    @staticmethod
    def _calc_total_years(jobseeker: JobSeeker, today: date) -> float:
        total_days = 0
        for exp in jobseeker.experience.all():  # pyrefly: ignore
            end = exp.end_date or today
            total_days += max(0, (end - exp.start_date).days)
        return total_days / 365.25

    def get(
        self,
        request: AuthenticatedHtmxRequest,
    ) -> HttpResponse:
        company = self.get_company(request.user)
        if not company:
            raise Http404

        jobseeker_qs = (
            JobSeeker.objects
            .filter(profile_visible=True)
            .select_related('user')
            .prefetch_related(
                'skills',
                'education',
                'experience',
                'languages',
            )
        )

        jobseeker_filter = JobSeekerFilter(
            data=request.GET,
            queryset=jobseeker_qs,
        )

        filtered_qs = jobseeker_filter.qs

        experience_level = request.GET.get('experience_level', '')
        filtered_qs = self.apply_experience_filter(
            filtered_qs,
            experience_level,
        )

        selected_job, match_scores = self._compute_match_scores(
            request,
            company,
            filtered_qs,
        )

        sort = request.GET.get('sort', '')
        if sort == 'match_score' and match_scores:
            preserved_order = Case(
                *[
                    When(pk=pk, then=Value(score))
                    for pk, score in match_scores.items()
                ],
                default=Value(0),
                output_field=IntegerField(),
            )
            filtered_qs = filtered_qs.annotate(
                match_score_order=preserved_order,
            ).order_by('-match_score_order')

        selected_job_id = request.GET.get('job_id', '')

        paginator = Paginator(filtered_qs, self.paginate_by)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        if match_scores:
            for js in page_obj:
                js.match_score = match_scores.get(js.pk, 0)  # type: ignore[attr-defined] # pyrefly: ignore

        for js in page_obj:
            js.exp_count = js.experience.count()  # type: ignore[attr-defined] # pyrefly: ignore

        context = {
            'page_obj': page_obj,
            'company': company,
            'filter': jobseeker_filter,
            'popular_skills': self._get_popular_skills(),
            'selected_job': selected_job,
            'company_jobs': self._get_company_jobs(company),
            'current_q': request.GET.get('q', ''),
            'current_location': request.GET.get('location', ''),
            'current_sort': request.GET.get('sort', ''),
            'current_education_level': request.GET.get(
                'education_level',
                '',
            ),
            'current_experience_level': experience_level,
            'current_job_id': selected_job_id,
            'current_skills': request.GET.getlist('skills'),
            'sort_choices': self.SORT_CHOICES,
            'experience_choices': self.EXPERIENCE_CHOICES,
            'education_choices': Education.EducationLevelEnum.choices,
        }

        return render(request, self.template_name, context)

    def _compute_match_scores(
        self,
        request: AuthenticatedHtmxRequest,
        company: Company,
        qs: QuerySet[JobSeeker],
    ) -> tuple[Job | None, dict[int, int]]:
        selected_job_id = request.GET.get('job_id', '')
        if not selected_job_id:
            return None, {}

        try:
            selected_job = Job.objects.get(
                pk=int(selected_job_id),
                company=company,
            )
        except (ValueError, Job.DoesNotExist):
            return None, {}

        job_skills = set(selected_job.skills.values_list('id', flat=True))
        if not job_skills:
            return selected_job, {}

        match_scores: dict[int, int] = {}
        for js in qs:
            candidate_skills = set(
                js.skills.values_list('id', flat=True),
            )
            matching = job_skills & candidate_skills
            match_scores[js.pk] = round(
                (len(matching) / len(job_skills)) * 100,
            )
        return selected_job, match_scores

    @staticmethod
    def _get_popular_skills() -> QuerySet[Skill]:
        return Skill.objects.annotate(
            jobseeker_count=Count('jobseekers'),
        ).order_by('-jobseeker_count')[:15]

    @staticmethod
    def _get_company_jobs(company: Company) -> QuerySet[Job]:
        return Job.objects.filter(
            company=company,
            is_active=True,
        ).order_by('-posted_at')
